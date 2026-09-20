import time
from datetime import datetime, timedelta

from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.wallet_repository import BUSINESS_TIMEZONE, WalletRepository


class DeveloperBillingNotFoundError(ValueError):
    pass


class DeveloperBillingConflictError(ValueError):
    pass


class DeveloperBillingRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def list_customers(self, keyword: str = "") -> list[dict]:
        where = ["u.status = 1", "u.user_role = 'customer'"]
        params: list[object] = []
        if keyword:
            where.append(
                "(u.nickname like %s or u.login_name like %s or t.tenant_name like %s)"
            )
            like = f"%{keyword}%"
            params.extend([like, like, like])
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select u.id, u.tenant_id, u.login_name, u.nickname,
                       coalesce(t.tenant_name, '') as tenant_name,
                       coalesce(w.balance, 0) as balance
                from app_user u
                left join tenant t on t.id = u.tenant_id
                left join credit_wallet w on w.user_id = u.id
                where {" and ".join(where)}
                order by t.tenant_name asc, u.nickname asc, u.id asc
                limit 500
                """,
                tuple(params),
            )
            rows = cursor.fetchall()
        return [
            {
                **row,
                "id": int(row["id"]),
                "tenant_id": int(row["tenant_id"]),
                "balance": int(row["balance"] or 0),
            }
            for row in rows
        ]

    def get_tenant_membership(self, tenant_id: int) -> dict:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select tenant_name
                from tenant
                where id = %s
                """,
                (tenant_id,),
            )
            tenant = cursor.fetchone()
            cursor.execute(
                """
                select count(*) as total
                from app_user
                where tenant_id = %s
                """,
                (tenant_id,),
            )
            if tenant is None and int(cursor.fetchone()["total"]) == 0:
                raise DeveloperBillingNotFoundError("tenant not found")
            cursor.execute(
                """
                select id
                from app_user
                where tenant_id = %s and status = 1
                  and user_role in ('customer', 'client_owner')
                order by id
                """,
                (tenant_id,),
            )
            user_ids = [int(row["id"]) for row in cursor.fetchall()]
            membership = None
            if user_ids:
                cursor.execute(
                    """
                    select m.id, m.plan_id, m.status, m.start_time,
                           m.expire_time, m.auto_renew,
                           p.id as plan_row_id, p.plan_code, p.plan_name,
                           p.monthly_credits, p.daily_checkin_credits,
                           p.storage_gb
                    from user_membership m
                    inner join membership_plan p on p.id = m.plan_id
                    where m.user_id = %s
                    """,
                    (user_ids[0],),
                )
                membership_row = cursor.fetchone()
                if membership_row is not None:
                    membership = self._normalize_tenant_membership(membership_row)
            cursor.execute(
                """
                select id, plan_code, plan_name, monthly_credits,
                       daily_checkin_credits, storage_gb
                from membership_plan
                where status = 1
                order by sort_order asc, id asc
                """
            )
            plans = [
                self._normalize_membership_plan(row)
                for row in cursor.fetchall()
            ]
        return {
            "tenant_id": tenant_id,
            "tenant_name": str(tenant["tenant_name"]) if tenant else "",
            "affected_user_count": len(user_ids),
            "membership": membership,
            "plans": plans,
        }

    def adjust_tenant_membership(
        self,
        developer: dict,
        tenant_id: int,
        *,
        plan_id: int,
        duration_months: int,
    ) -> dict:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id
                    from tenant
                    where id = %s
                    """,
                    (tenant_id,),
                )
                tenant = cursor.fetchone()
                cursor.execute(
                    """
                    select count(*) as total
                    from app_user
                    where tenant_id = %s
                    """,
                    (tenant_id,),
                )
                if tenant is None and int(cursor.fetchone()["total"]) == 0:
                    raise DeveloperBillingNotFoundError("tenant not found")
                cursor.execute(
                    """
                    select id, plan_code, status
                    from membership_plan
                    where id = %s
                    """,
                    (plan_id,),
                )
                plan = cursor.fetchone()
                if plan is None:
                    raise DeveloperBillingNotFoundError("membership plan not found")
                if int(plan["status"]) != 1:
                    raise DeveloperBillingConflictError(
                        "membership plan is disabled"
                    )
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
                if duration_months <= 0:
                    expire_time = 0
                else:
                    expire_time = int(
                        (
                            datetime.now(BUSINESS_TIMEZONE)
                            + timedelta(days=30 * duration_months)
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
                            plan_id,
                            now,
                            expire_time,
                            now,
                            now,
                        ),
                    )
                AdminAuditRepository(self.conn).create(
                    tenant_id=tenant_id,
                    admin_user_id=int(developer["id"]),
                    action="developer.billing.membership_adjust",
                    target_type="tenant",
                    target_id=tenant_id,
                    detail={
                        "plan_code": plan["plan_code"],
                        "duration_months": duration_months,
                        "affected_user_count": len(user_ids),
                    },
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_tenant_membership(tenant_id)

    def list_recharge_orders(
        self,
        *,
        page: int,
        page_size: int,
        status: int | None,
        keyword: str,
    ) -> dict:
        where = ["u.user_role = 'customer'"]
        params: list[object] = []
        if status is not None:
            where.append("o.status = %s")
            params.append(status)
        if keyword:
            where.append(
                "(o.order_no like %s or u.nickname like %s or "
                "u.login_name like %s or t.tenant_name like %s)"
            )
            like = f"%{keyword}%"
            params.extend([like, like, like, like])
        where_sql = " and ".join(where)
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select count(*) as total
                from recharge_order o
                join app_user u on u.id = o.user_id
                left join tenant t on t.id = o.tenant_id
                where {where_sql}
                """,
                tuple(params),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                f"""
                {self._order_select_sql()}
                where {where_sql}
                order by o.update_time desc, o.id desc
                limit %s offset %s
                """,
                (*params, page_size, offset),
            )
            items = [self._normalize_order(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def grant_recharge_order(self, developer: dict, order_id: int) -> dict:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    self._order_select_sql()
                    + """
                    where o.id = %s and u.user_role = 'customer'
                    for update
                    """,
                    (order_id,),
                )
                order = cursor.fetchone()
                if order is None:
                    raise DeveloperBillingNotFoundError("recharge order not found")
                status = int(order["status"])
                if status == 3:
                    self.conn.commit()
                    return self._normalize_order(order)
                if status != 6:
                    raise DeveloperBillingConflictError(
                        "only paid recharge orders can be granted"
                    )

                before_balance, after_balance = self._increase_wallet(
                    cursor,
                    int(order["user_id"]),
                    int(order["requested_credits"]),
                    now,
                )
                cursor.execute(
                    """
                    insert into credit_ledger (
                        user_id, business_type, business_id, before_balance,
                        change_amount, after_balance, reason, create_time
                    )
                    values (%s, 'recharge', %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        int(order["user_id"]),
                        order_id,
                        before_balance,
                        int(order["requested_credits"]),
                        after_balance,
                        f"充值订单发放：{order['order_no']}",
                        now,
                    ),
                )
                cursor.execute(
                    """
                    update recharge_order
                    set status = 3, completed_time = %s, update_time = %s
                    where id = %s and status = 6
                    """,
                    (now, now, order_id),
                )
                if cursor.rowcount != 1:
                    raise DeveloperBillingConflictError(
                        "recharge order status changed, please refresh"
                    )
                AdminAuditRepository(self.conn).create(
                    tenant_id=int(order["tenant_id"]),
                    admin_user_id=int(developer["id"]),
                    action="developer.billing.recharge_order_grant",
                    target_type="recharge_order",
                    target_id=order_id,
                    detail={
                        "employee_user_id": int(order["user_id"]),
                        "credits": int(order["requested_credits"]),
                        "before_balance": before_balance,
                        "after_balance": after_balance,
                    },
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        result = self.get_recharge_order(order_id)
        if result is None:
            raise RuntimeError("granted recharge order was not found")
        return result

    def grant_credits(
        self,
        developer: dict,
        *,
        user_id: int,
        credits: int,
        reason: str,
    ) -> dict:
        now = int(time.time())
        reason = reason.strip()
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select u.id, u.tenant_id, u.login_name, u.nickname,
                           coalesce(t.tenant_name, '') as tenant_name
                    from app_user u
                    left join tenant t on t.id = u.tenant_id
                    where u.id = %s and u.status = 1
                      and u.user_role = 'customer'
                    for update
                    """,
                    (user_id,),
                )
                user = cursor.fetchone()
                if user is None:
                    raise DeveloperBillingNotFoundError("customer not found")
                before_balance, after_balance = self._increase_wallet(
                    cursor, user_id, credits, now
                )
                cursor.execute(
                    """
                    insert into credit_ledger (
                        user_id, business_type, business_id, before_balance,
                        change_amount, after_balance, reason, create_time
                    )
                    values (%s, 'manual_grant', 0, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        before_balance,
                        credits,
                        after_balance,
                        reason,
                        now,
                    ),
                )
                ledger_id = int(cursor.lastrowid)
                AdminAuditRepository(self.conn).create(
                    tenant_id=int(user["tenant_id"]),
                    admin_user_id=int(developer["id"]),
                    action="developer.billing.manual_credit_grant",
                    target_type="credit_ledger",
                    target_id=ledger_id,
                    detail={
                        "employee_user_id": user_id,
                        "credits": credits,
                        "before_balance": before_balance,
                        "after_balance": after_balance,
                        "reason": reason,
                    },
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return {
            "ledger_id": ledger_id,
            "user_id": user_id,
            "employee_name": user["nickname"],
            "employee_login": user["login_name"],
            "tenant_name": user["tenant_name"],
            "before_balance": before_balance,
            "change_amount": credits,
            "after_balance": after_balance,
            "reason": reason,
            "create_time": now,
        }

    def adjust_credits(
        self,
        developer: dict,
        *,
        user_id: int,
        change_amount: int,
        reason: str,
    ) -> dict:
        reason = reason.strip()
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select user.id, user.tenant_id, user.login_name,
                       user.nickname,
                       coalesce(tenant.tenant_name, '') as tenant_name,
                       coalesce(wallet.balance, 0) as before_balance
                from app_user user
                left join tenant on tenant.id = user.tenant_id
                left join credit_wallet wallet on wallet.user_id = user.id
                where user.id = %s and user.user_role = 'customer'
                """,
                (user_id,),
            )
            user = cursor.fetchone()
        if user is None:
            raise DeveloperBillingNotFoundError("customer not found")
        ledger_id = WalletRepository(self.conn).adjust_credits(
            user_id,
            change_amount,
            "developer_adjustment",
            0,
            reason,
            commit=False,
        )
        try:
            AdminAuditRepository(self.conn).create(
                tenant_id=int(user["tenant_id"]),
                admin_user_id=int(developer["id"]),
                action="developer.billing.credit_adjustment",
                target_type="credit_ledger",
                target_id=ledger_id,
                detail={
                    "employee_user_id": user_id,
                    "change_amount": change_amount,
                    "reason": reason,
                },
                commit=False,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select before_balance, change_amount, after_balance, create_time
                from credit_ledger where id = %s
                """,
                (ledger_id,),
            )
            ledger = cursor.fetchone()
        return {
            "ledger_id": ledger_id,
            "user_id": user_id,
            "employee_name": user["nickname"],
            "employee_login": user["login_name"],
            "tenant_name": user["tenant_name"],
            "before_balance": int(ledger["before_balance"]),
            "change_amount": int(ledger["change_amount"]),
            "after_balance": int(ledger["after_balance"]),
            "reason": reason,
            "create_time": int(ledger["create_time"] or now),
        }

    def list_ledger(
        self,
        *,
        page: int,
        page_size: int,
        user_id: int | None,
        keyword: str,
    ) -> dict:
        where = ["u.user_role = 'customer'"]
        params: list[object] = []
        if user_id is not None:
            where.append("l.user_id = %s")
            params.append(user_id)
        if keyword:
            where.append(
                "(l.reason like %s or u.nickname like %s or "
                "u.login_name like %s or t.tenant_name like %s)"
            )
            like = f"%{keyword}%"
            params.extend([like, like, like, like])
        where_sql = " and ".join(where)
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select count(*) as total
                from credit_ledger l
                join app_user u on u.id = l.user_id
                left join tenant t on t.id = u.tenant_id
                where {where_sql}
                """,
                tuple(params),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                f"""
                select l.id, l.user_id, l.business_type, l.business_id,
                       l.before_balance, l.change_amount, l.after_balance,
                       l.reason, l.create_time, u.nickname as employee_name,
                       u.login_name as employee_login,
                       coalesce(t.tenant_name, '') as tenant_name
                from credit_ledger l
                join app_user u on u.id = l.user_id
                left join tenant t on t.id = u.tenant_id
                where {where_sql}
                order by l.create_time desc, l.id desc
                limit %s offset %s
                """,
                (*params, page_size, offset),
            )
            items = [self._normalize_ledger(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def list_payment_records(
        self,
        *,
        page: int,
        page_size: int,
    ) -> dict:
        offset = (page - 1) * page_size
        payment_records_sql = self._payment_records_sql()
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"select count(*) as total from ({payment_records_sql}) records"
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                f"""
                select *
                from ({payment_records_sql}) records
                order by sort_time desc, record_type asc, order_id desc
                limit %s offset %s
                """,
                (page_size, offset),
            )
            items = [
                self._normalize_payment_record(row)
                for row in cursor.fetchall()
            ]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def get_recharge_order(self, order_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._order_select_sql()
                + """
                where o.id = %s and u.user_role = 'customer'
                """,
                (order_id,),
            )
            row = cursor.fetchone()
        return None if row is None else self._normalize_order(row)

    @staticmethod
    def _increase_wallet(cursor, user_id: int, credits: int, now: int) -> tuple[int, int]:
        cursor.execute(
            """
            insert into credit_wallet (
                user_id, balance, total_recharged, total_consumed,
                create_time, update_time
            )
            values (%s, 0, 0, 0, %s, %s)
            on duplicate key update update_time = update_time
            """,
            (user_id, now, now),
        )
        cursor.execute(
            """
            select balance
            from credit_wallet
            where user_id = %s
            for update
            """,
            (user_id,),
        )
        wallet = cursor.fetchone()
        before_balance = int(wallet["balance"])
        after_balance = before_balance + credits
        cursor.execute(
            """
            update credit_wallet
            set balance = %s,
                total_recharged = total_recharged + %s,
                update_time = %s
            where user_id = %s
            """,
            (after_balance, credits, now, user_id),
        )
        return before_balance, after_balance

    @staticmethod
    def _order_select_sql() -> str:
        return """
            select o.id, o.order_no, o.tenant_id, o.user_id,
                   o.recharge_type, o.package_id, o.amount_cent,
                   o.requested_credits, o.payment_channel, o.status,
                   o.payer_note, o.proof_file_name, o.proof_mime_type,
                   o.proof_file_size, o.proof_submit_time, o.remark,
                   o.paid_time, o.completed_time, o.create_time, o.update_time,
                   u.nickname as employee_name, u.login_name as employee_login,
                   coalesce(t.tenant_name, '') as tenant_name,
                   coalesce(p.package_name, '') as package_name
            from recharge_order o
            join app_user u on u.id = o.user_id
            left join tenant t on t.id = o.tenant_id
            left join recharge_package p on p.id = o.package_id
        """

    @staticmethod
    def _payment_records_sql() -> str:
        return """
            select concat('credit_recharge:', o.id) as record_key,
                   'credit_recharge' as record_type,
                   '算力充值' as record_type_text,
                   o.id as order_id, o.order_no, o.tenant_id,
                   coalesce(t.tenant_name, '') as tenant_name,
                   o.user_id, u.nickname as customer_name,
                   u.login_name as customer_login,
                   coalesce(nullif(p.package_name, ''), '自定义算力充值') as description,
                   o.amount_cent, o.requested_credits as credits,
                   o.payment_channel, o.status,
                   case o.status
                       when 1 then '待付款'
                       when 2 then '待核验'
                       when 3 then '已到账'
                       when 4 then '已取消'
                       when 5 then '核验未通过'
                       when 6 then '已付款待发放'
                       else '未知状态'
                   end as status_text,
                   o.paid_time, o.create_time, o.update_time,
                   greatest(o.paid_time, o.update_time) as sort_time
            from recharge_order o
            join app_user u on u.id = o.user_id
            left join tenant t on t.id = o.tenant_id
            left join recharge_package p on p.id = o.package_id
            union all
            select concat('membership_purchase:', o.id) as record_key,
                   'membership_purchase' as record_type,
                   '会员购买' as record_type_text,
                   o.id as order_id, o.order_no, o.tenant_id,
                   coalesce(t.tenant_name, '') as tenant_name,
                   o.applicant_user_id as user_id,
                   u.nickname as customer_name,
                   u.login_name as customer_login,
                   concat(p.plan_name, ' · ', o.duration_months, ' 个月') as description,
                   o.amount_cent, 0 as credits,
                   o.payment_channel, o.status,
                   case o.status
                       when 1 then '待付款'
                       when 2 then '待审核'
                       when 3 then '已开通'
                       when 4 then '已驳回'
                       when 5 then '已取消'
                       else '未知状态'
                   end as status_text,
                   o.paid_time, o.create_time, o.update_time,
                   greatest(o.paid_time, o.update_time) as sort_time
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
        return result

    @staticmethod
    def _normalize_tenant_membership(row: dict) -> dict:
        return {
            "id": int(row["id"]),
            "plan_id": int(row["plan_id"]),
            "status": int(row["status"]),
            "start_time": int(row["start_time"] or 0),
            "expire_time": int(row["expire_time"] or 0),
            "auto_renew": int(row["auto_renew"] or 0),
            "plan": {
                "id": int(row["plan_row_id"]),
                "plan_code": str(row["plan_code"]),
                "plan_name": str(row["plan_name"]),
                "monthly_credits": int(row["monthly_credits"] or 0),
                "daily_checkin_credits": int(row["daily_checkin_credits"] or 0),
                "storage_gb": int(row["storage_gb"] or 0),
            },
        }

    @staticmethod
    def _normalize_membership_plan(row: dict) -> dict:
        return {
            "id": int(row["id"]),
            "plan_code": str(row["plan_code"]),
            "plan_name": str(row["plan_name"]),
            "monthly_credits": int(row["monthly_credits"] or 0),
            "daily_checkin_credits": int(row["daily_checkin_credits"] or 0),
            "storage_gb": int(row["storage_gb"] or 0),
        }

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

    @staticmethod
    def _normalize_payment_record(row: dict) -> dict:
        result = dict(row)
        for key in (
            "order_id",
            "tenant_id",
            "user_id",
            "amount_cent",
            "credits",
            "status",
            "paid_time",
            "create_time",
            "update_time",
        ):
            result[key] = int(result[key] or 0)
        result.pop("sort_time", None)
        return result
