import json
import time
import uuid
from datetime import datetime, timedelta, timezone

from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.wallet_repository import WalletRepository


BUSINESS_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


class MembershipUpgradeNotFoundError(LookupError):
    pass


class MembershipUpgradeConflictError(ValueError):
    pass


class MembershipUpgradeRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def create_order(
        self,
        manager: dict,
        *,
        plan_id: int,
        duration_months: int,
        payment_channel: str,
    ) -> dict:
        tenant_id = int(manager["tenant_id"])
        manager_id = int(manager["id"])
        current_membership = WalletRepository(self.conn).get_current_membership(
            tenant_id,
            manager_id,
        )
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, plan_code, plan_name, price_cent, summary,
                       feature_json, monthly_credits, daily_checkin_credits,
                       storage_gb, status, sort_order, create_time, update_time
                from membership_plan
                where id = %s and status = 1
                """,
                (plan_id,),
            )
            plan = cursor.fetchone()
            if plan is None:
                raise MembershipUpgradeNotFoundError("会员套餐不存在")
            current_plan = current_membership["plan"]
            if int(plan["price_cent"] or 0) <= 0:
                raise MembershipUpgradeConflictError(
                    "免费版会员无需创建支付订单"
                )
            if int(plan["sort_order"]) <= int(current_plan["sort_order"]):
                raise MembershipUpgradeConflictError(
                    "只能购买更高级别的会员套餐"
                )
            cursor.execute(
                """
                select id
                from membership_upgrade_order
                where tenant_id = %s and status in (1, 2)
                limit 1
                """,
                (tenant_id,),
            )
            if cursor.fetchone() is not None:
                raise MembershipUpgradeConflictError(
                    "已有一笔会员订单待付款或待审核"
                )
            order_no = (
                f"MU{datetime.now(BUSINESS_TIMEZONE):%Y%m%d%H%M%S}"
                f"{uuid.uuid4().hex[:8].upper()}"
            )
            amount_cent = int(plan["price_cent"]) * duration_months
            cursor.execute(
                """
                insert into membership_upgrade_order (
                    order_no, tenant_id, applicant_user_id, plan_id,
                    duration_months, amount_cent, payment_channel, status,
                    paid_time, reviewed_by_developer_id, reviewed_time,
                    affected_user_count, remark, create_time, update_time
                )
                values (%s, %s, %s, %s, %s, %s, %s, 1,
                        0, 0, 0, 0, '', %s, %s)
                """,
                (
                    order_no,
                    tenant_id,
                    manager_id,
                    plan_id,
                    duration_months,
                    amount_cent,
                    payment_channel,
                    now,
                    now,
                ),
            )
            order_id = int(cursor.lastrowid)
            AdminAuditRepository(self.conn).create(
                tenant_id=tenant_id,
                admin_user_id=manager_id,
                action="billing.membership_order_create",
                target_type="membership_upgrade_order",
                target_id=order_id,
                detail={
                    "plan_code": plan["plan_code"],
                    "duration_months": duration_months,
                    "amount_cent": amount_cent,
                    "payment_channel": payment_channel,
                },
                commit=False,
            )
        self.conn.commit()
        result = self.get_order(order_id, tenant_id=tenant_id)
        if result is None:
            raise RuntimeError("created membership order was not found")
        return result

    def list_manager_orders(
        self,
        tenant_id: int,
        *,
        page: int,
        page_size: int,
        status: int | None,
    ) -> dict:
        return self._list_orders(
            page=page,
            page_size=page_size,
            status=status,
            tenant_id=tenant_id,
        )

    def confirm_payment(self, manager: dict, order_id: int) -> dict:
        tenant_id = int(manager["tenant_id"])
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, status
                    from membership_upgrade_order
                    where id = %s and tenant_id = %s
                    for update
                    """,
                    (order_id, tenant_id),
                )
                order = cursor.fetchone()
                if order is None:
                    raise MembershipUpgradeNotFoundError(
                        "会员订单不存在"
                    )
                status = int(order["status"])
                if status in {2, 3}:
                    self.conn.commit()
                    result = self.get_order(order_id, tenant_id=tenant_id)
                    if result is None:
                        raise RuntimeError("membership order was not found")
                    return result
                if status != 1:
                    raise MembershipUpgradeConflictError(
                        "已驳回的会员订单不能确认付款"
                    )
                cursor.execute(
                    """
                    update membership_upgrade_order
                    set status = 2, paid_time = %s, update_time = %s
                    where id = %s and tenant_id = %s and status = 1
                    """,
                    (now, now, order_id, tenant_id),
                )
                AdminAuditRepository(self.conn).create(
                    tenant_id=tenant_id,
                    admin_user_id=int(manager["id"]),
                    action="billing.membership_order_mark_paid",
                    target_type="membership_upgrade_order",
                    target_id=order_id,
                    detail={"next_status": 2},
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        result = self.get_order(order_id, tenant_id=tenant_id)
        if result is None:
            raise RuntimeError("confirmed membership order was not found")
        return result

    def cancel_by_manager(self, manager: dict, order_id: int) -> dict:
        tenant_id = int(manager["tenant_id"])
        manager_id = int(manager["id"])
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, tenant_id, status
                    from membership_upgrade_order
                    where id = %s and tenant_id = %s
                    for update
                    """,
                    (order_id, tenant_id),
                )
                order = cursor.fetchone()
                if order is None:
                    raise MembershipUpgradeNotFoundError(
                        "会员订单不存在"
                    )
                status = int(order["status"])
                if status == 5:
                    self.conn.commit()
                    result = self.get_order(order_id, tenant_id=tenant_id)
                    if result is None:
                        raise RuntimeError("membership order was not found")
                    return result
                if status not in (1, 2):
                    raise MembershipUpgradeConflictError(
                        "只有待付款或待审核的会员订单可以取消"
                    )
                cursor.execute(
                    """
                    update membership_upgrade_order
                    set status = 5, remark = '管理员取消申请', update_time = %s
                    where id = %s and tenant_id = %s and status in (1, 2)
                    """,
                    (now, order_id, tenant_id),
                )
                if cursor.rowcount != 1:
                    raise MembershipUpgradeConflictError(
                        "会员订单状态已变更，请刷新后重试"
                    )
                AdminAuditRepository(self.conn).create(
                    tenant_id=tenant_id,
                    admin_user_id=manager_id,
                    action="billing.membership_order_cancel",
                    target_type="membership_upgrade_order",
                    target_id=order_id,
                    detail={"previous_status": status},
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        result = self.get_order(order_id, tenant_id=tenant_id)
        if result is None:
            raise RuntimeError("cancelled membership order was not found")
        return result

    def list_developer_orders(
        self,
        *,
        page: int,
        page_size: int,
        status: int | None,
    ) -> dict:
        return self._list_orders(
            page=page,
            page_size=page_size,
            status=status,
            tenant_id=None,
        )

    def approve(self, developer: dict, order_id: int) -> dict:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    self._order_select_sql()
                    + " where o.id = %s for update",
                    (order_id,),
                )
                order = cursor.fetchone()
                if order is None:
                    raise MembershipUpgradeNotFoundError(
                        "会员订单不存在"
                    )
                status = int(order["status"])
                if status == 3:
                    self.conn.commit()
                    return self._normalize_order(order)
                if status != 2:
                    raise MembershipUpgradeConflictError(
                        "只有已付款的会员订单可以审核通过"
                    )
                tenant_id = int(order["tenant_id"])
                cursor.execute(
                    """
                    select id
                    from app_user
                    where tenant_id = %s and status = 1
                      and user_role in ('customer', 'client_owner')
                    order by id
                    for update
                    """,
                    (tenant_id,),
                )
                user_ids = [int(row["id"]) for row in cursor.fetchall()]
                expire_time = int(
                    (
                        datetime.now(BUSINESS_TIMEZONE)
                        + timedelta(days=30 * int(order["duration_months"]))
                    ).timestamp()
                )
                for user_id in user_ids:
                    cursor.execute(
                        """
                        insert into user_membership (
                            tenant_id, user_id, plan_id, status, start_time,
                            expire_time, auto_renew, create_time, update_time
                        ) values (%s, %s, %s, 1, %s, %s, 0, %s, %s)
                        on duplicate key update
                            plan_id = values(plan_id), status = 1,
                            start_time = values(start_time),
                            expire_time = values(expire_time), auto_renew = 0,
                            update_time = values(update_time)
                        """,
                        (
                            tenant_id,
                            user_id,
                            int(order["plan_id"]),
                            now,
                            expire_time,
                            now,
                            now,
                        ),
                    )
                cursor.execute(
                    """
                    update membership_upgrade_order
                    set status = 3, reviewed_by_developer_id = %s,
                        reviewed_time = %s, affected_user_count = %s,
                        remark = '', update_time = %s
                    where id = %s and status = 2
                    """,
                    (int(developer["id"]), now, len(user_ids), now, order_id),
                )
                if cursor.rowcount != 1:
                    raise MembershipUpgradeConflictError(
                        "会员订单状态已变更，请刷新后重试"
                    )
                AdminAuditRepository(self.conn).create(
                    tenant_id=tenant_id,
                    admin_user_id=int(developer["id"]),
                    action="developer.billing.membership_order_approve",
                    target_type="membership_upgrade_order",
                    target_id=order_id,
                    detail={
                        "plan_code": order["plan_code"],
                        "affected_user_count": len(user_ids),
                    },
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        result = self.get_order(order_id)
        if result is None:
            raise RuntimeError("approved membership order was not found")
        return result

    def reject(self, developer: dict, order_id: int, reason: str) -> dict:
        reason = reason.strip()
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, tenant_id, status
                    from membership_upgrade_order
                    where id = %s
                    for update
                    """,
                    (order_id,),
                )
                order = cursor.fetchone()
                if order is None:
                    raise MembershipUpgradeNotFoundError(
                        "会员订单不存在"
                    )
                status = int(order["status"])
                if status == 4:
                    self.conn.commit()
                    result = self.get_order(order_id)
                    if result is None:
                        raise RuntimeError("membership order was not found")
                    return result
                if status != 2:
                    raise MembershipUpgradeConflictError(
                        "只有待审核的会员订单可以驳回"
                    )
                cursor.execute(
                    """
                    update membership_upgrade_order
                    set status = 4, reviewed_by_developer_id = %s,
                        reviewed_time = %s, remark = %s, update_time = %s
                    where id = %s and status = 2
                    """,
                    (int(developer["id"]), now, reason, now, order_id),
                )
                AdminAuditRepository(self.conn).create(
                    tenant_id=int(order["tenant_id"]),
                    admin_user_id=int(developer["id"]),
                    action="developer.billing.membership_order_reject",
                    target_type="membership_upgrade_order",
                    target_id=order_id,
                    detail={"reason": reason},
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        result = self.get_order(order_id)
        if result is None:
            raise RuntimeError("rejected membership order was not found")
        return result

    def get_order(self, order_id: int, *, tenant_id: int | None = None) -> dict | None:
        where = ["o.id = %s"]
        params: list[object] = [order_id]
        if tenant_id is not None:
            where.append("o.tenant_id = %s")
            params.append(tenant_id)
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._order_select_sql() + " where " + " and ".join(where),
                tuple(params),
            )
            row = cursor.fetchone()
        return None if row is None else self._normalize_order(row)

    def _list_orders(
        self,
        *,
        page: int,
        page_size: int,
        status: int | None,
        tenant_id: int | None,
    ) -> dict:
        where: list[str] = []
        params: list[object] = []
        if tenant_id is not None:
            where.append("o.tenant_id = %s")
            params.append(tenant_id)
        if status is not None:
            where.append("o.status = %s")
            params.append(status)
        where_sql = " and ".join(where) if where else "1 = 1"
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"select count(*) as total from membership_upgrade_order o where {where_sql}",
                tuple(params),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                self._order_select_sql()
                + f" where {where_sql} order by o.update_time desc, o.id desc limit %s offset %s",
                (*params, page_size, offset),
            )
            items = [self._normalize_order(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    @staticmethod
    def _order_select_sql() -> str:
        return """
            select o.id, o.order_no, o.tenant_id, o.applicant_user_id,
                   o.plan_id, o.duration_months, o.amount_cent,
                   o.payment_channel, o.status, o.paid_time,
                   o.reviewed_by_developer_id, o.reviewed_time,
                   o.affected_user_count, o.remark, o.create_time,
                   o.update_time, p.plan_code, p.plan_name, p.price_cent,
                   p.summary, p.feature_json, p.monthly_credits,
                   p.daily_checkin_credits, p.storage_gb,
                   p.status as plan_status, p.sort_order,
                   p.create_time as plan_create_time,
                   p.update_time as plan_update_time,
                   u.nickname as applicant_name,
                   u.login_name as applicant_login,
                   coalesce(t.tenant_name, '') as tenant_name
            from membership_upgrade_order o
            join membership_plan p on p.id = o.plan_id
            join app_user u on u.id = o.applicant_user_id
            left join tenant t on t.id = o.tenant_id
        """

    @staticmethod
    def _normalize_order(row: dict) -> dict:
        result = dict(row)
        for key in (
            "id",
            "tenant_id",
            "applicant_user_id",
            "plan_id",
            "duration_months",
            "amount_cent",
            "status",
            "paid_time",
            "reviewed_by_developer_id",
            "reviewed_time",
            "affected_user_count",
            "create_time",
            "update_time",
        ):
            result[key] = int(result[key] or 0)
        result["plan"] = {
            "id": result["plan_id"],
            "plan_code": result.pop("plan_code"),
            "plan_name": result.pop("plan_name"),
            "price_cent": int(result.pop("price_cent") or 0),
            "summary": result.pop("summary"),
            "features": json.loads(result.pop("feature_json") or "[]"),
            "monthly_credits": int(result.pop("monthly_credits") or 0),
            "daily_checkin_credits": int(
                result.pop("daily_checkin_credits") or 0
            ),
            "storage_gb": int(result.pop("storage_gb") or 0),
            "status": int(result.pop("plan_status") or 0),
            "sort_order": int(result.pop("sort_order") or 0),
            "create_time": int(result.pop("plan_create_time") or 0),
            "update_time": int(result.pop("plan_update_time") or 0),
        }
        return result
