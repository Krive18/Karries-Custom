import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from app.schemas.wallet import RechargeOrderCreate
from app.services.upload_storage_service import StoredUpload


BUSINESS_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")

logger = logging.getLogger(__name__)


class RechargeOrderNotFoundError(LookupError):
    pass


class RechargeOrderConflictError(ValueError):
    pass


class WalletRepository:
    def __init__(self, conn):
        self.conn = conn

    def create_wallet(
        self,
        user_id: int,
        initial_credits: int,
        reason: str,
        *,
        commit: bool = True,
    ) -> int:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into credit_wallet (
                        user_id, balance, total_recharged, total_consumed, create_time, update_time
                    )
                    values (%s, 0, 0, 0, %s, %s)
                    """,
                    (user_id, now, now),
                )
                wallet_id = int(cursor.lastrowid)

                if initial_credits > 0:
                    cursor.execute(
                        """
                        update credit_wallet
                        set balance = %s,
                            total_recharged = total_recharged + %s,
                            update_time = %s
                        where user_id = %s
                        """,
                        (initial_credits, initial_credits, now, user_id),
                    )
                    cursor.execute(
                        """
                        insert into credit_ledger (
                            user_id, business_type, business_id, before_balance,
                            change_amount, after_balance, reason, create_time
                        )
                        values (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            user_id,
                            "invite_bonus",
                            wallet_id,
                            0,
                            initial_credits,
                            initial_credits,
                            reason,
                            now,
                        ),
                    )
            if commit:
                self.conn.commit()
            return wallet_id
        except Exception:
            self.conn.rollback()
            raise

    def get_wallet(self, user_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, user_id, balance, total_recharged, total_consumed, create_time, update_time
                from credit_wallet
                where user_id = %s
                """,
                (user_id,),
            )
            return cursor.fetchone()

    def adjust_credits(
        self,
        user_id: int,
        change_amount: int,
        business_type: str,
        business_id: int,
        reason: str,
        *,
        commit: bool = True,
    ) -> int:
        try:
            now = int(time.time())
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, user_id, balance, total_recharged, total_consumed, create_time, update_time
                    from credit_wallet
                    where user_id = %s
                    for update
                    """,
                    (user_id,),
                )
                wallet = cursor.fetchone()
                if wallet is None:
                    raise ValueError(f"wallet does not exist: {user_id}")

                before = self._expire_previous_monthly_credits(
                    cursor,
                    user_id=user_id,
                    balance=int(wallet["balance"]),
                    now=now,
                )
                after = before + change_amount
                if after < 0:
                    raise ValueError("insufficient credits")

                total_recharged_delta = change_amount if change_amount > 0 else 0
                total_consumed_delta = -change_amount if change_amount < 0 else 0
                cursor.execute(
                    """
                    update credit_wallet
                    set balance = %s,
                        total_recharged = total_recharged + %s,
                        total_consumed = total_consumed + %s,
                        update_time = %s
                    where user_id = %s
                    """,
                    (after, total_recharged_delta, total_consumed_delta, now, user_id),
                )
                if change_amount < 0:
                    self._consume_current_monthly_credits(
                        cursor,
                        user_id=user_id,
                        amount=-change_amount,
                    )
                cursor.execute(
                    """
                    insert into credit_ledger (
                        user_id, business_type, business_id, before_balance,
                        change_amount, after_balance, reason, create_time
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, business_type, business_id, before, change_amount, after, reason, now),
                )
                ledger_id = int(cursor.lastrowid)
            if commit:
                self.conn.commit()
            return ledger_id
        except Exception:
            self.conn.rollback()
            raise

    def has_ledger_entry(
        self,
        user_id: int,
        business_type: str,
        business_id: int,
        *,
        reason_prefix: str = "",
    ) -> bool:
        sql = """
            select id
            from credit_ledger
            where user_id = %s
              and business_type = %s
              and business_id = %s
        """
        params: list[object] = [user_id, business_type, business_id]
        if reason_prefix:
            sql += " and reason like %s"
            params.append(f"{reason_prefix}%")
        sql += " limit 1"
        with self.conn.cursor() as cursor:
            cursor.execute(sql, tuple(params))
            return cursor.fetchone() is not None

    def ensure_sufficient_credits(self, user_id: int, required_amount: int) -> None:
        if required_amount <= 0:
            return
        with self.conn.cursor() as cursor:
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
        if wallet is None:
            raise ValueError(f"wallet does not exist: {user_id}")
        if int(wallet["balance"]) < required_amount:
            raise ValueError("insufficient credits")

    def list_ledger(self, user_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, user_id, business_type, business_id, before_balance,
                       change_amount, after_balance, reason, create_time
                from credit_ledger
                where user_id = %s
                order by id desc
                """,
                (user_id,),
            )
            return list(cursor.fetchall())

    def list_membership_plans(self) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, plan_code, plan_name, price_cent, summary,
                       feature_json, monthly_credits, daily_checkin_credits,
                       storage_gb, status, sort_order, create_time, update_time
                from membership_plan
                where status = 1
                order by sort_order asc, id asc
                """
            )
            rows = list(cursor.fetchall())
        return [self._serialize_plan(row) for row in rows]

    def get_current_membership(self, tenant_id: int, user_id: int) -> dict:
        membership = self._find_current_membership(user_id)
        if membership is None:
            membership = self._create_default_membership(tenant_id, user_id)
        else:
            membership = self._revert_expired_membership(membership)
        self._expire_previous_monthly_credits_for_user(user_id)
        self._ensure_monthly_credit_grant(tenant_id, user_id, membership)
        membership["plan"] = self._serialize_plan(membership["plan"])
        return membership

    def get_checkin_status(self, tenant_id: int, user_id: int) -> dict:
        membership = self.get_current_membership(tenant_id, user_id)
        checkin_date = self._business_date()
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, credits
                from user_daily_checkin
                where user_id = %s
                  and checkin_date = %s
                """,
                (user_id, checkin_date),
            )
            checkin = cursor.fetchone()
        wallet = self.get_wallet(user_id)
        return {
            "checked_in": checkin is not None,
            "checkin_date": checkin_date,
            "credits": int(
                checkin["credits"]
                if checkin is not None
                else membership["plan"]["daily_checkin_credits"]
            ),
            "balance": int(wallet["balance"]) if wallet else 0,
        }

    def check_in(self, tenant_id: int, user_id: int) -> dict:
        membership = self.get_current_membership(tenant_id, user_id)
        checkin_date = self._business_date()
        credits = int(membership["plan"]["daily_checkin_credits"])
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert ignore into user_daily_checkin (
                        tenant_id, user_id, membership_id, checkin_date,
                        credits, create_time
                    )
                    values (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        tenant_id,
                        user_id,
                        membership["id"],
                        checkin_date,
                        credits,
                        now,
                    ),
                )
                created = cursor.rowcount == 1
                if created and credits > 0:
                    checkin_id = int(cursor.lastrowid)
                    self._apply_positive_credit_change(
                        cursor,
                        user_id=user_id,
                        change_amount=credits,
                        business_type="daily_checkin",
                        business_id=checkin_id,
                        reason=f"{checkin_date} 每日签到奖励",
                        now=now,
                    )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        wallet = self.get_wallet(user_id)
        return {
            "checked_in": True,
            "already_checked_in": not created,
            "checkin_date": checkin_date,
            "credits": credits,
            "balance": int(wallet["balance"]) if wallet else 0,
        }

    def list_recharge_packages(self) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, package_name, base_credits, credits, price_cent, is_hot,
                       status, sort_order, create_time, update_time
                from recharge_package
                where status = 1
                order by sort_order asc, id asc
                """
            )
            return list(cursor.fetchall())

    def create_recharge_order(
        self,
        tenant_id: int,
        user_id: int,
        payload: RechargeOrderCreate,
    ) -> dict:
        package_id = 0
        amount_cent = payload.amount_cent
        requested_credits = amount_cent // 5
        remark = f"自定义充值申请，预计到账 {requested_credits} 算力"

        if payload.recharge_type == "package":
            package = self._get_recharge_package(payload.package_id)
            if package is None:
                raise ValueError("recharge package not found")
            package_id = int(package["id"])
            requested_credits = int(package["credits"])
            amount_cent = int(package["price_cent"])
            remark = (
                f"{package['package_name']}充值申请，"
                f"实际到账 {requested_credits} 算力"
            )
        elif amount_cent < 1000:
            raise ValueError("online recharge amount must be at least 10 yuan")

        now = int(time.time())
        order_no = f"RC{now}{uuid.uuid4().hex[:8].upper()}"
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into recharge_order (
                        order_no, tenant_id, user_id, recharge_type, package_id,
                        amount_cent, requested_credits, payment_channel, status,
                        remark, paid_time, completed_time, create_time, update_time
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, 0, 0, %s, %s)
                    """,
                    (
                        order_no,
                        tenant_id,
                        user_id,
                        payload.recharge_type,
                        package_id,
                        amount_cent,
                        requested_credits,
                        payload.payment_channel,
                        remark,
                        now,
                        now,
                    ),
                )
                order_id = int(cursor.lastrowid)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        order = self.get_recharge_order(user_id, order_id)
        if order is None:
            raise RuntimeError("recharge order creation failed")
        return order

    def get_recharge_order(self, user_id: int, order_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select recharge_order.id, recharge_order.order_no,
                       recharge_order.tenant_id, recharge_order.user_id,
                       recharge_order.recharge_type, recharge_order.package_id,
                       recharge_order.amount_cent, recharge_order.requested_credits,
                       recharge_order.payment_channel, recharge_order.status,
                       recharge_order.payer_note, recharge_order.proof_file_name,
                       recharge_order.proof_mime_type, recharge_order.proof_file_size,
                       recharge_order.proof_submit_time,
                       recharge_order.remark, recharge_order.paid_time,
                       recharge_order.completed_time, recharge_order.create_time,
                       recharge_order.update_time,
                       coalesce(recharge_package.package_name, '') as package_name
                from recharge_order
                left join recharge_package
                  on recharge_package.id = recharge_order.package_id
                where recharge_order.id = %s
                  and recharge_order.user_id = %s
                """,
                (order_id, user_id),
            )
            row = cursor.fetchone()
        return None if row is None else self._normalize_recharge_order(row)

    def list_recharge_orders(self, user_id: int, limit: int = 20) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select recharge_order.id, recharge_order.order_no,
                       recharge_order.tenant_id, recharge_order.user_id,
                       recharge_order.recharge_type, recharge_order.package_id,
                       recharge_order.amount_cent, recharge_order.requested_credits,
                       recharge_order.payment_channel, recharge_order.status,
                       recharge_order.payer_note, recharge_order.proof_file_name,
                       recharge_order.proof_mime_type, recharge_order.proof_file_size,
                       recharge_order.proof_submit_time,
                       recharge_order.remark, recharge_order.paid_time,
                       recharge_order.completed_time, recharge_order.create_time,
                       recharge_order.update_time,
                       coalesce(recharge_package.package_name, '') as package_name
                from recharge_order
                left join recharge_package
                  on recharge_package.id = recharge_order.package_id
                where recharge_order.user_id = %s
                order by recharge_order.id desc
                limit %s
                """,
                (user_id, limit),
            )
            return [
                self._normalize_recharge_order(row)
                for row in cursor.fetchall()
            ]

    def submit_recharge_payment_proof(
        self,
        tenant_id: int,
        user_id: int,
        order_id: int,
        payer_note: str,
        stored: StoredUpload,
    ) -> tuple[dict, str]:
        now = int(time.time())
        previous_storage_path = ""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, status, payment_channel, proof_file_path
                    from recharge_order
                    where id = %s
                      and tenant_id = %s
                      and user_id = %s
                    for update
                    """,
                    (order_id, tenant_id, user_id),
                )
                order = cursor.fetchone()
                if order is None:
                    raise RechargeOrderNotFoundError("recharge order not found")
                if order["payment_channel"] not in {"alipay", "wechat"}:
                    raise RechargeOrderConflictError(
                        "this recharge order does not accept payment proof"
                    )
                if int(order["status"]) not in {1, 2, 5}:
                    raise RechargeOrderConflictError(
                        "payment proof cannot be submitted for this order"
                    )

                previous_storage_path = str(order["proof_file_path"] or "")
                cursor.execute(
                    """
                    update recharge_order
                    set payer_note = %s,
                        proof_file_path = %s,
                        proof_file_name = %s,
                        proof_mime_type = %s,
                        proof_file_size = %s,
                        proof_submit_time = %s,
                        paid_time = %s,
                        status = 2,
                        remark = '',
                        update_time = %s
                    where id = %s
                      and tenant_id = %s
                      and user_id = %s
                    """,
                    (
                        payer_note,
                        stored.storage_path,
                        stored.file_name,
                        stored.mime_type,
                        stored.file_size,
                        now,
                        now,
                        now,
                        order_id,
                        tenant_id,
                        user_id,
                    ),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        result = self.get_recharge_order(user_id, order_id)
        if result is None:
            raise RuntimeError("recharge order disappeared after proof submission")
        return result, previous_storage_path

    def get_recharge_payment_proof(
        self,
        tenant_id: int,
        user_id: int,
        order_id: int,
    ) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, proof_file_path, proof_file_name, proof_mime_type
                from recharge_order
                where id = %s
                  and tenant_id = %s
                  and user_id = %s
                  and proof_file_path <> ''
                """,
                (order_id, tenant_id, user_id),
            )
            return cursor.fetchone()

    @staticmethod
    def _normalize_recharge_order(row: dict) -> dict:
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
            result[key] = int(result.get(key) or 0)
        result["has_payment_proof"] = bool(result.get("proof_file_name"))
        return result

    def _find_current_membership(self, user_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select user_membership.id, user_membership.tenant_id,
                       user_membership.user_id, user_membership.plan_id,
                       user_membership.status, user_membership.start_time,
                       user_membership.expire_time, user_membership.auto_renew,
                       user_membership.create_time, user_membership.update_time,
                       membership_plan.id as plan_row_id,
                       membership_plan.plan_code, membership_plan.plan_name,
                       membership_plan.price_cent, membership_plan.summary,
                       membership_plan.feature_json,
                       membership_plan.monthly_credits,
                       membership_plan.daily_checkin_credits,
                       membership_plan.storage_gb,
                       membership_plan.status as plan_status,
                       membership_plan.sort_order,
                       membership_plan.create_time as plan_create_time,
                       membership_plan.update_time as plan_update_time
                from user_membership
                inner join membership_plan
                  on membership_plan.id = user_membership.plan_id
                where user_membership.user_id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return self._membership_from_row(row)

    def _create_default_membership(self, tenant_id: int, user_id: int) -> dict:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id
                    from membership_plan
                    where plan_code = 'pro'
                      and status = 1
                    limit 1
                    """
                )
                plan = cursor.fetchone()
                if plan is None:
                    raise RuntimeError("default membership plan is not configured")
                cursor.execute(
                    """
                    insert into user_membership (
                        tenant_id, user_id, plan_id, status, start_time,
                        expire_time, auto_renew, create_time, update_time
                    )
                    values (%s, %s, %s, 1, %s, 0, 0, %s, %s)
                    on duplicate key update
                        plan_id = plan_id,
                        update_time = update_time
                    """,
                    (tenant_id, user_id, plan["id"], now, now, now),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        membership = self._find_current_membership(user_id)
        if membership is None:
            raise RuntimeError("default membership creation failed")
        return membership

    def _revert_expired_membership(self, membership: dict) -> dict:
        expire_time = int(membership["expire_time"] or 0)
        status = int(membership["status"])
        if status == 1 and (expire_time <= 0 or expire_time > int(time.time())):
            return membership
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id
                    from membership_plan
                    where plan_code = 'pro'
                      and status = 1
                    limit 1
                    """
                )
                default_plan = cursor.fetchone()
                if default_plan is None:
                    raise RuntimeError("default membership plan is not configured")
                if int(membership["plan_id"]) == int(default_plan["id"]):
                    cursor.execute(
                        """
                        update user_membership
                        set status = 1, expire_time = 0, update_time = %s
                        where id = %s
                        """,
                        (now, int(membership["id"])),
                    )
                else:
                    cursor.execute(
                        """
                        update user_membership
                        set plan_id = %s, status = 1, start_time = %s,
                            expire_time = 0, auto_renew = 0, update_time = %s
                        where id = %s
                        """,
                        (int(default_plan["id"]), now, now, int(membership["id"])),
                    )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        logger.info(
            "membership expired and reverted to default plan: "
            "user_id=%s plan_code=%s expire_time=%s",
            membership["user_id"],
            membership["plan"]["plan_code"],
            expire_time,
        )
        reverted = self._find_current_membership(int(membership["user_id"]))
        if reverted is None:
            raise RuntimeError("membership revert failed")
        return reverted

    def _get_recharge_package(self, package_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, package_name, base_credits, credits, price_cent, is_hot,
                       status, sort_order, create_time, update_time
                from recharge_package
                where id = %s
                  and status = 1
                """,
                (package_id,),
            )
            return cursor.fetchone()

    @staticmethod
    def _serialize_plan(plan: dict) -> dict:
        result = dict(plan)
        result["features"] = json.loads(result.pop("feature_json") or "[]")
        return result

    @staticmethod
    def _membership_from_row(row: dict) -> dict:
        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"],
            "user_id": row["user_id"],
            "plan_id": row["plan_id"],
            "status": row["status"],
            "start_time": row["start_time"],
            "expire_time": row["expire_time"],
            "auto_renew": row["auto_renew"],
            "create_time": row["create_time"],
            "update_time": row["update_time"],
            "plan": {
                "id": row["plan_row_id"],
                "plan_code": row["plan_code"],
                "plan_name": row["plan_name"],
                "price_cent": row["price_cent"],
                "summary": row["summary"],
                "feature_json": row["feature_json"],
                "monthly_credits": row["monthly_credits"],
                "daily_checkin_credits": row["daily_checkin_credits"],
                "storage_gb": row["storage_gb"],
                "status": row["plan_status"],
                "sort_order": row["sort_order"],
                "create_time": row["plan_create_time"],
                "update_time": row["plan_update_time"],
            },
        }

    def _ensure_monthly_credit_grant(
        self,
        tenant_id: int,
        user_id: int,
        membership: dict,
    ) -> None:
        credits = int(membership["plan"]["monthly_credits"])
        if credits <= 0:
            return

        grant_month = datetime.now(BUSINESS_TIMEZONE).strftime("%Y-%m")
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert ignore into membership_monthly_credit_grant (
                        tenant_id, user_id, membership_id, grant_month,
                        credits, remaining_credits, expired_credits,
                        expired_time, create_time
                    )
                    values (%s, %s, %s, %s, %s, %s, 0, 0, %s)
                    """,
                    (
                        tenant_id,
                        user_id,
                        membership["id"],
                        grant_month,
                        credits,
                        credits,
                        now,
                    ),
                )
                if cursor.rowcount == 1:
                    grant_id = int(cursor.lastrowid)
                    self._apply_positive_credit_change(
                        cursor,
                        user_id=user_id,
                        change_amount=credits,
                        business_type="membership_monthly",
                        business_id=grant_id,
                        reason=(
                            f"{grant_month} "
                            f"{membership['plan']['plan_name']}月度算力发放"
                        ),
                        now=now,
                    )
                else:
                    cursor.execute(
                        """
                        select id, credits, remaining_credits, create_time
                        from membership_monthly_credit_grant
                        where user_id = %s and grant_month = %s
                        for update
                        """,
                        (user_id, grant_month),
                    )
                    existing_grant = cursor.fetchone()
                    if (
                        existing_grant is not None
                        and existing_grant["remaining_credits"] is None
                    ):
                        remaining = self._legacy_grant_remaining(
                            cursor,
                            user_id,
                            existing_grant,
                        )
                        cursor.execute(
                            """
                            update membership_monthly_credit_grant
                            set remaining_credits = %s
                            where id = %s
                            """,
                            (remaining, int(existing_grant["id"])),
                        )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _expire_previous_monthly_credits_for_user(self, user_id: int) -> None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
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
                if wallet is None:
                    return
                self._expire_previous_monthly_credits(
                    cursor,
                    user_id=user_id,
                    balance=int(wallet["balance"]),
                    now=now,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _expire_previous_monthly_credits(
        self,
        cursor,
        *,
        user_id: int,
        balance: int,
        now: int,
    ) -> int:
        current_month = datetime.now(BUSINESS_TIMEZONE).strftime("%Y-%m")
        cursor.execute(
            """
            select id, credits, remaining_credits, create_time
            from membership_monthly_credit_grant
            where user_id = %s
              and grant_month < %s
              and expired_time = 0
            order by grant_month asc, id asc
            for update
            """,
            (user_id, current_month),
        )
        grants = list(cursor.fetchall())
        for grant in grants:
            remaining = grant["remaining_credits"]
            if remaining is None:
                remaining = self._legacy_grant_remaining(cursor, user_id, grant)
            expired = min(int(remaining or 0), balance)
            before_balance = balance
            balance -= expired
            cursor.execute(
                """
                update membership_monthly_credit_grant
                set remaining_credits = 0,
                    expired_credits = %s,
                    expired_time = %s
                where id = %s
                """,
                (expired, now, grant["id"]),
            )
            if expired <= 0:
                continue
            cursor.execute(
                """
                update credit_wallet
                set balance = %s, update_time = %s
                where user_id = %s
                """,
                (balance, now, user_id),
            )
            cursor.execute(
                """
                insert into credit_ledger (
                    user_id, business_type, business_id, before_balance,
                    change_amount, after_balance, reason, create_time
                )
                values (%s, 'membership_expiry', %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    int(grant["id"]),
                    before_balance,
                    -expired,
                    balance,
                    "会员月度赠送算力到期清零",
                    now,
                ),
            )
        return balance

    @staticmethod
    def _legacy_grant_remaining(cursor, user_id: int, grant: dict) -> int:
        cursor.execute(
            """
            select min(create_time) as next_grant_time
            from membership_monthly_credit_grant
            where user_id = %s and create_time > %s
            """,
            (user_id, int(grant["create_time"])),
        )
        next_row = cursor.fetchone()
        next_grant_time = int(next_row["next_grant_time"] or 0)
        sql = """
            select coalesce(sum(-change_amount), 0) as consumed
            from credit_ledger
            where user_id = %s
              and change_amount < 0
              and create_time >= %s
        """
        params: list[object] = [user_id, int(grant["create_time"])]
        if next_grant_time > 0:
            sql += " and create_time < %s"
            params.append(next_grant_time)
        cursor.execute(sql, tuple(params))
        consumed = int(cursor.fetchone()["consumed"] or 0)
        return max(int(grant["credits"]) - consumed, 0)

    @staticmethod
    def _consume_current_monthly_credits(cursor, *, user_id: int, amount: int) -> None:
        if amount <= 0:
            return
        current_month = datetime.now(BUSINESS_TIMEZONE).strftime("%Y-%m")
        cursor.execute(
            """
            select id, remaining_credits
            from membership_monthly_credit_grant
            where user_id = %s
              and grant_month = %s
              and expired_time = 0
            for update
            """,
            (user_id, current_month),
        )
        grant = cursor.fetchone()
        if grant is None or grant["remaining_credits"] is None:
            return
        consumed = min(int(grant["remaining_credits"]), amount)
        if consumed <= 0:
            return
        cursor.execute(
            """
            update membership_monthly_credit_grant
            set remaining_credits = remaining_credits - %s
            where id = %s
            """,
            (consumed, int(grant["id"])),
        )

    @staticmethod
    def _business_date() -> str:
        return datetime.now(BUSINESS_TIMEZONE).date().isoformat()

    @staticmethod
    def _apply_positive_credit_change(
        cursor,
        *,
        user_id: int,
        change_amount: int,
        business_type: str,
        business_id: int,
        reason: str,
        now: int,
    ) -> None:
        cursor.execute(
            """
            insert into credit_wallet (
                user_id, balance, total_recharged, total_consumed,
                create_time, update_time
            )
            values (%s, 0, 0, 0, %s, %s)
            on duplicate key update
                update_time = update_time
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
        after_balance = before_balance + change_amount
        cursor.execute(
            """
            update credit_wallet
            set balance = %s,
                total_recharged = total_recharged + %s,
                update_time = %s
            where user_id = %s
            """,
            (after_balance, change_amount, now, user_id),
        )
        cursor.execute(
            """
            insert into credit_ledger (
                user_id, business_type, business_id, before_balance,
                change_amount, after_balance, reason, create_time
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                business_type,
                business_id,
                before_balance,
                change_amount,
                after_balance,
                reason,
                now,
            ),
        )
