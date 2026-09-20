import time
from datetime import datetime, timedelta, timezone

from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.admin_billing import (
    AdminMembershipActivate,
    AdminRechargeOrderCreate,
)


BUSINESS_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


class AdminBillingNotFoundError(LookupError):
    pass


class AdminBillingConflictError(ValueError):
    pass


class AdminBillingRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def overview(self, tenant_id: int, manager_user_id: int, days: int = 30) -> dict:
        membership = WalletRepository(self.conn).get_current_membership(
            tenant_id,
            manager_user_id,
        )
        start_time = int(time.time()) - days * 86400
        month_start = datetime.now(BUSINESS_TIMEZONE).replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        month_start_time = int(month_start.timestamp())

        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select
                    count(*) as employee_count,
                    coalesce(sum(w.balance), 0) as balance,
                    coalesce(sum(w.total_recharged), 0) as total_recharged,
                    coalesce(sum(w.total_consumed), 0) as total_consumed
                from app_user u
                left join credit_wallet w on w.user_id = u.id
                where u.tenant_id = %s
                  and u.user_role = 'customer'
                  and u.status = 1
                """,
                (tenant_id,),
            )
            wallet = cursor.fetchone()

            cursor.execute(
                """
                select
                    count(*) as order_count,
                    coalesce(sum(case when status = 1 then 1 else 0 end), 0)
                        as pending_order_count,
                    coalesce(sum(case when status = 3 then amount_cent else 0 end), 0)
                        as completed_amount_cent,
                    coalesce(sum(case when status = 3 then requested_credits else 0 end), 0)
                        as completed_credits
                from recharge_order
                where tenant_id = %s
                  and create_time >= %s
                """,
                (tenant_id, month_start_time),
            )
            orders = cursor.fetchone()

            cursor.execute(
                """
                select
                    date_format(
                        from_unixtime(min(l.create_time)),
                        '%%m-%%d'
                    ) as label,
                    coalesce(sum(case when l.change_amount > 0 then l.change_amount else 0 end), 0)
                        as income,
                    coalesce(sum(case when l.change_amount < 0 then -l.change_amount else 0 end), 0)
                        as expense
                from credit_ledger l
                join app_user u on u.id = l.user_id
                where u.tenant_id = %s
                  and u.user_role = 'customer'
                  and l.create_time >= %s
                group by date(from_unixtime(l.create_time))
                order by date(from_unixtime(l.create_time))
                """,
                (tenant_id, start_time),
            )
            trend = [
                {
                    "label": row["label"],
                    "income": int(row["income"] or 0),
                    "expense": int(row["expense"] or 0),
                }
                for row in cursor.fetchall()
            ]

            cursor.execute(
                """
                select
                    u.id as employee_id,
                    u.nickname as employee_name,
                    u.login_name as employee_login,
                    coalesce(w.balance, 0) as balance,
                    coalesce(w.total_recharged, 0) as total_recharged,
                    coalesce(w.total_consumed, 0) as total_consumed
                from app_user u
                left join credit_wallet w on w.user_id = u.id
                where u.tenant_id = %s
                  and u.user_role = 'customer'
                  and u.status = 1
                order by total_consumed desc, u.id asc
                limit 10
                """,
                (tenant_id,),
            )
            employees = [
                {
                    **row,
                    "employee_id": int(row["employee_id"]),
                    "balance": int(row["balance"] or 0),
                    "total_recharged": int(row["total_recharged"] or 0),
                    "total_consumed": int(row["total_consumed"] or 0),
                }
                for row in cursor.fetchall()
            ]

        return {
            "membership": membership,
            "wallet": {
                "employee_count": int(wallet["employee_count"] or 0),
                "balance": int(wallet["balance"] or 0),
                "total_recharged": int(wallet["total_recharged"] or 0),
                "total_consumed": int(wallet["total_consumed"] or 0),
            },
            "month_orders": {
                key: int(value or 0)
                for key, value in orders.items()
            },
            "credit_trend": trend,
            "employee_wallets": employees,
        }

    def activate_membership(
        self,
        manager: dict,
        payload: AdminMembershipActivate,
    ) -> dict:
        tenant_id = int(manager["tenant_id"])
        now = int(time.time())
        expire_time = int(
            (
                datetime.now(BUSINESS_TIMEZONE)
                + timedelta(days=30 * payload.duration_months)
            ).timestamp()
        )
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, plan_code, plan_name, price_cent, summary,
                           feature_json, monthly_credits, daily_checkin_credits,
                           storage_gb, status, sort_order, create_time, update_time
                    from membership_plan
                    where id = %s and status = 1
                    """,
                    (payload.plan_id,),
                )
                plan = cursor.fetchone()
                if plan is None:
                    raise AdminBillingNotFoundError("membership plan not found")

                cursor.execute(
                    """
                    select id
                    from app_user
                    where tenant_id = %s
                      and status = 1
                      and user_role in ('customer', 'client_owner')
                    """,
                    (tenant_id,),
                )
                user_ids = [int(row["id"]) for row in cursor.fetchall()]
                for user_id in user_ids:
                    cursor.execute(
                        """
                        insert into user_membership (
                            tenant_id, user_id, plan_id, status, start_time,
                            expire_time, auto_renew, create_time, update_time
                        )
                        values (%s, %s, %s, 1, %s, %s, %s, %s, %s)
                        on duplicate key update
                            plan_id = values(plan_id),
                            status = 1,
                            start_time = values(start_time),
                            expire_time = values(expire_time),
                            auto_renew = values(auto_renew),
                            update_time = values(update_time)
                        """,
                        (
                            tenant_id,
                            user_id,
                            payload.plan_id,
                            now,
                            expire_time,
                            payload.auto_renew,
                            now,
                            now,
                        ),
                    )

                AdminAuditRepository(self.conn).create(
                    tenant_id=tenant_id,
                    admin_user_id=int(manager["id"]),
                    action="billing.membership_activate",
                    target_type="membership_plan",
                    target_id=payload.plan_id,
                    detail={
                        "plan_code": plan["plan_code"],
                        "duration_months": payload.duration_months,
                        "auto_renew": payload.auto_renew,
                        "affected_user_count": len(user_ids),
                    },
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        membership = WalletRepository(self.conn).get_current_membership(
            tenant_id,
            int(manager["id"]),
        )
        return {
            "membership": membership,
            "affected_user_count": len(user_ids),
        }

    def create_recharge_order(
        self,
        manager: dict,
        payload: AdminRechargeOrderCreate,
    ) -> dict:
        employee = self._get_employee(
            int(manager["tenant_id"]),
            payload.employee_id,
        )
        if employee is None:
            raise AdminBillingNotFoundError("employee not found")
        order = WalletRepository(self.conn).create_recharge_order(
            int(manager["tenant_id"]),
            payload.employee_id,
            payload,
        )
        AdminAuditRepository(self.conn).create(
            tenant_id=int(manager["tenant_id"]),
            admin_user_id=int(manager["id"]),
            action="billing.recharge_order_create",
            target_type="recharge_order",
            target_id=int(order["id"]),
            detail={
                "employee_user_id": payload.employee_id,
                "amount_cent": int(order["amount_cent"]),
                "requested_credits": int(order["requested_credits"]),
            },
        )
        return {**order, "employee_name": employee["nickname"]}

    def confirm_recharge_order(self, manager: dict, order_id: int) -> dict:
        tenant_id = int(manager["tenant_id"])
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select o.id, o.order_no, o.tenant_id, o.user_id,
                           o.recharge_type, o.package_id, o.amount_cent,
                           o.requested_credits, o.payment_channel, o.status,
                           o.payer_note, o.proof_file_path, o.proof_file_name,
                           o.proof_mime_type, o.proof_file_size,
                           o.proof_submit_time,
                           o.remark, o.paid_time, o.completed_time,
                           o.create_time, o.update_time,
                           u.nickname as employee_name,
                           u.login_name as employee_login,
                           coalesce(p.package_name, '') as package_name
                    from recharge_order o
                    join app_user u on u.id = o.user_id
                    left join recharge_package p on p.id = o.package_id
                    where o.id = %s
                      and o.tenant_id = %s
                      and u.user_role = 'customer'
                    for update
                    """,
                    (order_id, tenant_id),
                )
                order = cursor.fetchone()
                if order is None:
                    raise AdminBillingNotFoundError("recharge order not found")
                if int(order["status"]) in {3, 6}:
                    self.conn.commit()
                    return self._normalize_order(order)
                if int(order["status"]) in {4, 5}:
                    raise AdminBillingConflictError(
                        "cancelled or failed recharge order cannot be confirmed"
                    )
                if order["payment_channel"] in {"alipay", "wechat"} and (
                    int(order["status"]) != 2 or not order["proof_file_path"]
                ):
                    raise AdminBillingConflictError(
                        "payment proof must be submitted before confirmation"
                    )

                cursor.execute(
                    """
                    update recharge_order
                    set status = 6,
                        paid_time = case when paid_time = 0 then %s else paid_time end,
                        update_time = %s
                    where id = %s and tenant_id = %s
                    """,
                    (now, now, order_id, tenant_id),
                )
                AdminAuditRepository(self.conn).create(
                    tenant_id=tenant_id,
                    admin_user_id=int(manager["id"]),
                    action="billing.recharge_order_mark_paid",
                    target_type="recharge_order",
                    target_id=order_id,
                    detail={
                        "employee_user_id": int(order["user_id"]),
                        "credits": int(order["requested_credits"]),
                        "next_status": 6,
                    },
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        result = self.get_recharge_order(tenant_id, order_id)
        if result is None:
            raise RuntimeError("paid recharge order was not found")
        return result

    def reject_recharge_order(
        self,
        manager: dict,
        order_id: int,
        reason: str,
    ) -> dict:
        tenant_id = int(manager["tenant_id"])
        reason = reason.strip()
        if len(reason) < 2:
            raise ValueError("rejection reason is required")
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select o.id, o.status, o.payment_channel
                    from recharge_order o
                    join app_user u on u.id = o.user_id
                    where o.id = %s
                      and o.tenant_id = %s
                      and u.user_role = 'customer'
                    for update
                    """,
                    (order_id, tenant_id),
                )
                order = cursor.fetchone()
                if order is None:
                    raise AdminBillingNotFoundError("recharge order not found")
                if int(order["status"]) != 2:
                    raise AdminBillingConflictError(
                        "only recharge orders awaiting verification can be rejected"
                    )
                if order["payment_channel"] not in {"alipay", "wechat"}:
                    raise AdminBillingConflictError(
                        "manual recharge orders do not accept payment proof rejection"
                    )
                cursor.execute(
                    """
                    update recharge_order
                    set status = 5,
                        remark = %s,
                        update_time = %s
                    where id = %s
                      and tenant_id = %s
                    """,
                    (reason, now, order_id, tenant_id),
                )
                AdminAuditRepository(self.conn).create(
                    tenant_id=tenant_id,
                    admin_user_id=int(manager["id"]),
                    action="billing.recharge_order_reject",
                    target_type="recharge_order",
                    target_id=order_id,
                    detail={"reason": reason},
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        result = self.get_recharge_order(tenant_id, order_id)
        if result is None:
            raise RuntimeError("rejected recharge order was not found")
        return result

    def list_recharge_orders(
        self,
        tenant_id: int,
        *,
        page: int,
        page_size: int,
        employee_id: int | None,
        status: int | None,
        keyword: str,
    ) -> dict:
        where = ["o.tenant_id = %s", "u.user_role = 'customer'"]
        params: list[object] = [tenant_id]
        if employee_id is not None:
            where.append("o.user_id = %s")
            params.append(employee_id)
        if status is not None:
            where.append("o.status = %s")
            params.append(status)
        if keyword:
            where.append(
                "(o.order_no like %s or u.nickname like %s or u.login_name like %s)"
            )
            like = f"%{keyword}%"
            params.extend([like, like, like])
        where_sql = " and ".join(where)
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select count(*) as total
                from recharge_order o
                join app_user u on u.id = o.user_id
                where {where_sql}
                """,
                tuple(params),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                f"""
                {self._order_select_sql()}
                where {where_sql}
                order by o.create_time desc, o.id desc
                limit %s offset %s
                """,
                (*params, page_size, offset),
            )
            items = [self._normalize_order(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def get_recharge_order(self, tenant_id: int, order_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._order_select_sql()
                + """
                  where o.tenant_id = %s and o.id = %s
                    and u.user_role = 'customer'
                """,
                (tenant_id, order_id),
            )
            row = cursor.fetchone()
        return None if row is None else self._normalize_order(row)

    def get_recharge_payment_proof(
        self,
        tenant_id: int,
        order_id: int,
    ) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select o.id, o.proof_file_path, o.proof_file_name,
                       o.proof_mime_type
                from recharge_order o
                join app_user u on u.id = o.user_id
                where o.tenant_id = %s
                  and o.id = %s
                  and u.user_role = 'customer'
                  and o.proof_file_path <> ''
                """,
                (tenant_id, order_id),
            )
            return cursor.fetchone()

    def list_ledger(
        self,
        tenant_id: int,
        *,
        page: int,
        page_size: int,
        employee_id: int | None,
        business_type: str,
        direction: str,
        start_time: int | None,
        end_time: int | None,
        keyword: str,
    ) -> dict:
        where = ["u.tenant_id = %s", "u.user_role = 'customer'"]
        params: list[object] = [tenant_id]
        if employee_id is not None:
            where.append("l.user_id = %s")
            params.append(employee_id)
        if business_type:
            where.append("l.business_type = %s")
            params.append(business_type)
        if direction == "income":
            where.append("l.change_amount > 0")
        elif direction == "expense":
            where.append("l.change_amount < 0")
        if start_time is not None:
            where.append("l.create_time >= %s")
            params.append(start_time)
        if end_time is not None:
            where.append("l.create_time <= %s")
            params.append(end_time)
        if keyword:
            where.append(
                "(l.reason like %s or u.nickname like %s or u.login_name like %s)"
            )
            like = f"%{keyword}%"
            params.extend([like, like, like])
        where_sql = " and ".join(where)
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select
                    count(*) as total,
                    coalesce(sum(case when l.change_amount > 0 then l.change_amount else 0 end), 0)
                        as income,
                    coalesce(sum(case when l.change_amount < 0 then -l.change_amount else 0 end), 0)
                        as expense
                from credit_ledger l
                join app_user u on u.id = l.user_id
                where {where_sql}
                """,
                tuple(params),
            )
            summary = cursor.fetchone()
            cursor.execute(
                f"""
                select l.id, l.user_id, l.business_type, l.business_id,
                       l.before_balance, l.change_amount, l.after_balance,
                       l.reason, l.create_time,
                       u.nickname as employee_name,
                       u.login_name as employee_login
                from credit_ledger l
                join app_user u on u.id = l.user_id
                where {where_sql}
                order by l.create_time desc, l.id desc
                limit %s offset %s
                """,
                (*params, page_size, offset),
            )
            items = [self._normalize_ledger(row) for row in cursor.fetchall()]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": int(summary["total"]),
            "summary": {
                "income": int(summary["income"] or 0),
                "expense": int(summary["expense"] or 0),
            },
        }

    def _get_employee(self, tenant_id: int, employee_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, nickname, login_name, status
                from app_user
                where id = %s
                  and tenant_id = %s
                  and user_role = 'customer'
                """,
                (employee_id, tenant_id),
            )
            return cursor.fetchone()

    @staticmethod
    def _order_select_sql() -> str:
        return """
            select o.id, o.order_no, o.tenant_id, o.user_id,
                   o.recharge_type, o.package_id, o.amount_cent,
                   o.requested_credits, o.payment_channel, o.status,
                   o.payer_note, o.proof_file_path, o.proof_file_name,
                   o.proof_mime_type, o.proof_file_size,
                   o.proof_submit_time,
                   o.remark, o.paid_time, o.completed_time,
                   o.create_time, o.update_time,
                   u.nickname as employee_name,
                   u.login_name as employee_login,
                   coalesce(p.package_name, '') as package_name
            from recharge_order o
            join app_user u on u.id = o.user_id
            left join recharge_package p on p.id = o.package_id
        """

    @staticmethod
    def _normalize_order(row: dict) -> dict:
        result = dict(row)
        for key in (
            "id",
            "tenant_id",
            "user_id",
            "package_id",
            "amount_cent",
            "requested_credits",
            "status",
            "proof_file_size",
            "proof_submit_time",
            "paid_time",
            "completed_time",
            "create_time",
            "update_time",
        ):
            result[key] = int(result[key] or 0)
        result["has_payment_proof"] = bool(result.get("proof_file_name"))
        result.pop("proof_file_path", None)
        return result

    @staticmethod
    def _normalize_ledger(row: dict) -> dict:
        result = dict(row)
        for key in (
            "id",
            "user_id",
            "business_id",
            "before_balance",
            "change_amount",
            "after_balance",
            "create_time",
        ):
            result[key] = int(result[key] or 0)
        return result
