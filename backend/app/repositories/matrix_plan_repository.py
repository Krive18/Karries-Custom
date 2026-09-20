import json
import time
from typing import Any
from uuid import uuid4

from app.repositories.wallet_repository import WalletRepository
from app.schemas.matrix_plan import MatrixPlanCreate, MatrixPlanFromDraftsCreate
from app.services.credit_charge_service import CreditChargeService
from app.services.publish_safety_service import (
    CONTENT_DEDUPLICATION_WINDOW_SECONDS,
    build_content_fingerprint,
    business_date,
    next_business_day_retry_time,
)


PLAN_FIELDS = (
    "id",
    "user_id",
    "plan_name",
    "source_type",
    "content_type",
    "product_id",
    "status",
    "schedule_start_time",
    "schedule_end_time",
    "create_time",
    "update_time",
)

WORKER_LEASE_SECONDS = 300
EXPIRED_LEASE_REASON = "发布执行中断，为避免重复发布已转人工确认"


class MatrixPlanRepository:
    def __init__(self, conn):
        self.conn = conn

    def create_plan(
        self,
        user_id: int,
        payload: MatrixPlanCreate,
        schedule: list[tuple[int, int]],
    ) -> tuple[int, int]:
        now = int(time.time())
        scheduling_rule = {
            "xhs_account_ids": payload.xhs_account_ids,
            "items_per_account": payload.items_per_account,
            "min_interval_minutes": payload.min_interval_minutes,
        }

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into matrix_publish_plan (
                        user_id, plan_name, source_type, content_type, product_id,
                        status, schedule_start_time, schedule_end_time,
                        scheduling_rule_json, create_time, update_time
                    )
                    values (%s, %s, %s, %s, %s, 1, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        payload.plan_name,
                        payload.source_type,
                        payload.content_type,
                        payload.product_id,
                        payload.schedule_start_time,
                        payload.schedule_end_time,
                        self._dump_json(scheduling_rule),
                        now,
                        now,
                    ),
                )
                plan_id = int(cursor.lastrowid)
                for account_id, scheduled_time in schedule:
                    cursor.execute(
                        """
                        insert into matrix_publish_item (
                            plan_id, user_id, xhs_account_id, content_type,
                            title, body, tag_json, material_json, scheduled_time,
                            status, last_error, create_time, update_time
                        )
                        values (%s, %s, %s, %s, '', '', '[]', '[]', %s, 1, '', %s, %s)
                        """,
                        (
                            plan_id,
                            user_id,
                            account_id,
                            payload.content_type,
                            scheduled_time,
                            now,
                            now,
                        ),
                    )
            self.conn.commit()
            return plan_id, len(schedule)
        except Exception:
            self.conn.rollback()
            raise

    def create_plan_from_drafts(
        self,
        user_id: int,
        payload: MatrixPlanFromDraftsCreate,
        drafts: list[dict],
        draft_schedule: list[tuple[int, int, int]],
    ) -> tuple[int, int]:
        now = int(time.time())
        drafts_by_id = {int(draft["id"]): draft for draft in drafts}
        scheduling_rule = {
            "source": "content_draft",
            "draft_ids": payload.draft_ids,
            "xhs_account_ids": payload.xhs_account_ids,
            "items_per_account": len(payload.draft_ids),
            "min_interval_minutes": payload.min_interval_minutes,
        }

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into matrix_publish_plan (
                        user_id, plan_name, source_type, content_type, product_id,
                        status, schedule_start_time, schedule_end_time,
                        scheduling_rule_json, create_time, update_time
                    )
                    values (%s, %s, 'content_draft', 'image_text', 0, 2, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        payload.plan_name,
                        payload.schedule_start_time,
                        payload.schedule_end_time,
                        self._dump_json(scheduling_rule),
                        now,
                        now,
                    ),
                )
                plan_id = int(cursor.lastrowid)
                for account_id, draft_id, scheduled_time in draft_schedule:
                    draft = drafts_by_id[draft_id]
                    material = self._draft_item_material(draft, account_id)
                    content_fingerprint = build_content_fingerprint(
                        content_type=draft["content_type"],
                        title=draft["title"],
                        body=draft["body"],
                        tags=list(draft["tags"]),
                        material=material,
                    )
                    cursor.execute(
                        """
                        insert into matrix_publish_item (
                            plan_id, user_id, xhs_account_id, content_type,
                            title, body, tag_json, material_json,
                            content_fingerprint, scheduled_time, status,
                            last_error, create_time, update_time
                        )
                        values (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, 1, '', %s, %s
                        )
                        """,
                        (
                            plan_id,
                            user_id,
                            account_id,
                            draft["content_type"],
                            draft["title"],
                            draft["body"],
                            self._dump_json(draft["tags"]),
                            self._dump_json(material),
                            content_fingerprint,
                            scheduled_time,
                            now,
                            now,
                        ),
                    )
            self.conn.commit()
            return plan_id, len(draft_schedule)
        except Exception:
            self.conn.rollback()
            raise

    def list_plans(self, user_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_plan_sql()
                + """
                where p.user_id = %s
                order by p.id desc
                """,
                (user_id, user_id),
            )
            return [self._row_to_plan(row) for row in cursor.fetchall()]

    def list_items_for_plan(self, user_id: int, plan_id: int) -> list[dict] | None:
        if self.get_plan_for_user(user_id, plan_id) is None:
            return None

        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, plan_id, user_id, xhs_account_id, content_type,
                       title, body, tag_json, material_json, scheduled_time,
                       status, last_error, attempt_count, max_attempts,
                       next_retry_time, submitted_time, publish_result_json,
                       content_fingerprint,
                       create_time, update_time
                from matrix_publish_item
                where user_id = %s and plan_id = %s
                order by scheduled_time asc, id asc
                """,
                (user_id, plan_id),
            )
            return [self._row_to_item(row) for row in cursor.fetchall()]

    def get_plan_for_user(self, user_id: int, plan_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_plan_sql()
                + """
                where p.user_id = %s and p.id = %s
                """,
                (user_id, user_id, plan_id),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_plan(row)

    def confirm_plan(self, user_id: int, plan_id: int) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "select id, status from matrix_publish_plan where user_id = %s and id = %s for update",
                    (user_id, plan_id),
                )
                plan = cursor.fetchone()
                if plan is None:
                    return self._rollback_result(None)
                if int(plan["status"]) != 2:
                    return self._rollback_result(
                        {"error": "plan status does not allow confirmation"}
                    )

                cursor.execute(
                    """
                    select id, title, body, status
                    from matrix_publish_item
                    where user_id = %s and plan_id = %s
                    for update
                    """,
                    (user_id, plan_id),
                )
                rows = cursor.fetchall()
                if not rows:
                    return self._rollback_result({"error": "plan has no publish items"})
                if any(int(row["status"]) != 1 for row in rows):
                    return self._rollback_result(
                        {"error": "publish items are not all pending confirmation"}
                    )
                if any(
                    not str(row["title"]).strip() or not str(row["body"]).strip()
                    for row in rows
                ):
                    return self._rollback_result(
                        {"error": "publish item title and body are required"}
                    )

                cursor.execute(
                    "update matrix_publish_plan set status = 3, update_time = %s where id = %s",
                    (now, plan_id),
                )
                cursor.execute(
                    """
                    update matrix_publish_item
                    set status = 2, update_time = %s
                    where user_id = %s and plan_id = %s and status = 1
                    """,
                    (now, user_id, plan_id),
                )
                item_count = cursor.rowcount
            WalletRepository(self.conn).ensure_sufficient_credits(
                user_id,
                CreditChargeService().estimate("scheduled_publish") * item_count,
            )
            self.conn.commit()
            return {"id": plan_id, "status": 3, "item_count": item_count}
        except Exception:
            self.conn.rollback()
            raise

    def cancel_plan(self, user_id: int, plan_id: int) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "select id, status from matrix_publish_plan where user_id = %s and id = %s for update",
                    (user_id, plan_id),
                )
                plan = cursor.fetchone()
                if plan is None:
                    return self._rollback_result(None)
                if int(plan["status"]) not in {1, 2, 3}:
                    return self._rollback_result(
                        {"error": "plan status does not allow cancellation"}
                    )

                cursor.execute(
                    """
                    select id, status
                    from matrix_publish_item
                    where user_id = %s and plan_id = %s
                    for update
                    """,
                    (user_id, plan_id),
                )
                item_rows = cursor.fetchall()
                if any(int(row["status"]) == 3 for row in item_rows):
                    return self._rollback_result(
                        {"error": "plan has items already submitting"}
                    )

                cursor.execute(
                    "update matrix_publish_plan set status = 7, update_time = %s where id = %s",
                    (now, plan_id),
                )
                cursor.execute(
                    """
                    update matrix_publish_item
                    set status = 7, update_time = %s
                    where user_id = %s and plan_id = %s and status in (1, 2)
                    """,
                    (now, user_id, plan_id),
                )
                cancelled_item_count = cursor.rowcount
            self.conn.commit()
            return {"id": plan_id, "status": 7, "cancelled_item_count": cancelled_item_count}
        except Exception:
            self.conn.rollback()
            raise

    def retry_failed_items(self, user_id: int, plan_id: int) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, status
                    from matrix_publish_plan
                    where user_id = %s and id = %s
                    for update
                    """,
                    (user_id, plan_id),
                )
                plan = cursor.fetchone()
                if plan is None:
                    return self._rollback_result(None)
                if int(plan["status"]) != 6:
                    return self._rollback_result(
                        {"error": "plan status does not allow retry"}
                    )

                cursor.execute(
                    """
                    select i.id, i.xhs_account_id, a.status as account_status,
                           a.login_state_path
                    from matrix_publish_item i
                    join xhs_account a
                      on a.id = i.xhs_account_id and a.user_id = i.user_id
                    where i.user_id = %s and i.plan_id = %s
                      and i.status in (5, 6)
                    for update
                    """,
                    (user_id, plan_id),
                )
                failed_items = cursor.fetchall()
                if not failed_items:
                    return self._rollback_result(
                        {"error": "plan has no failed publish items"}
                    )
                if any(
                    int(row["account_status"]) != 1
                    or not str(row["login_state_path"] or "").strip()
                    for row in failed_items
                ):
                    return self._rollback_result(
                        {"error": "小红书账号登录状态不可用，请先到账号管理重新扫码登录"}
                    )

                cursor.execute(
                    """
                    update matrix_publish_item
                    set status = 2,
                        scheduled_time = %s,
                        last_error = '',
                        attempt_count = 0,
                        lease_token = '',
                        lease_expires_time = 0,
                        next_retry_time = 0,
                        submitted_time = 0,
                        publish_result_json = '',
                        update_time = %s
                    where user_id = %s and plan_id = %s
                      and status in (5, 6)
                    """,
                    (now, now, user_id, plan_id),
                )
                retried_item_count = cursor.rowcount
                cursor.execute(
                    """
                    update matrix_publish_plan
                    set status = 3, update_time = %s
                    where user_id = %s and id = %s
                    """,
                    (now, user_id, plan_id),
                )
            self.conn.commit()
            return {
                "id": plan_id,
                "status": 3,
                "retried_item_count": retried_item_count,
            }
        except Exception:
            self.conn.rollback()
            raise

    def claim_due_items(self, limit: int, now_time: int) -> list[dict]:
        now = int(time.time())
        current_business_date = business_date(now_time)
        try:
            with self.conn.cursor() as cursor:
                self._recover_expired_leases_locked(cursor, now_time, now)
                cursor.execute(
                    """
                    select
                        i.id,
                        i.plan_id,
                        i.user_id,
                        i.xhs_account_id,
                        a.login_state_path,
                        i.content_type,
                        i.title,
                        i.body,
                        i.tag_json,
                        i.material_json,
                        i.content_fingerprint,
                        i.scheduled_time,
                        i.attempt_count,
                        i.max_attempts
                    from matrix_publish_item i
                    join matrix_publish_plan p on p.id = i.plan_id
                    join xhs_account a on a.id = i.xhs_account_id and a.user_id = i.user_id
                    where i.status = 2
                      and i.scheduled_time <= %s
                      and i.next_retry_time <= %s
                      and p.status in (3, 4)
                      and a.status = 1
                      and not exists (
                          select 1
                          from matrix_publish_item active_item
                          where active_item.xhs_account_id = i.xhs_account_id
                            and active_item.status = 3
                      )
                    order by i.scheduled_time asc, i.id asc
                    limit %s
                    for update skip locked
                    """,
                    (now_time, now_time, max(limit * 4, limit)),
                )
                candidate_rows = cursor.fetchall()
                if not candidate_rows:
                    self.conn.commit()
                    return []

                rows: list[dict] = []
                claimed_account_ids: set[int] = set()
                for row in candidate_rows:
                    if len(rows) >= limit:
                        break
                    account_id = int(row["xhs_account_id"])
                    if account_id in claimed_account_ids:
                        continue
                    cursor.execute(
                        """
                        select id, user_id, daily_limit, min_interval_minutes,
                               last_publish_time, today_publish_count,
                               publish_count_date
                        from xhs_account
                        where id = %s and user_id = %s and status = 1
                        for update
                        """,
                        (account_id, int(row["user_id"])),
                    )
                    account = cursor.fetchone()
                    if account is None:
                        continue
                    cursor.execute(
                        """
                        select id
                        from matrix_publish_item
                        where xhs_account_id = %s and status = 3
                        limit 1
                        """,
                        (account_id,),
                    )
                    if cursor.fetchone() is not None:
                        continue

                    content_fingerprint = str(
                        row.get("content_fingerprint") or ""
                    ).strip()
                    if not content_fingerprint:
                        content_fingerprint = build_content_fingerprint(
                            content_type=str(row["content_type"]),
                            title=str(row["title"]),
                            body=str(row["body"]),
                            tags=self._load_json_list(row["tag_json"]),
                            material=self._load_json_dict(row["material_json"]),
                        )
                        cursor.execute(
                            """
                            update matrix_publish_item
                            set content_fingerprint = %s, update_time = %s
                            where id = %s
                            """,
                            (content_fingerprint, now, int(row["id"])),
                        )
                        row["content_fingerprint"] = content_fingerprint

                    effective_publish_count = (
                        int(account["today_publish_count"])
                        if str(account["publish_count_date"] or "")
                        == current_business_date
                        else 0
                    )
                    if str(account["publish_count_date"] or "") != current_business_date:
                        cursor.execute(
                            """
                            update xhs_account
                            set today_publish_count = 0,
                                publish_count_date = %s,
                                update_time = %s
                            where id = %s
                            """,
                            (current_business_date, now, account_id),
                        )

                    if effective_publish_count >= int(account["daily_limit"]):
                        retry_time = next_business_day_retry_time(now_time)
                        self._defer_item_locked(
                            cursor,
                            row,
                            retry_time=retry_time,
                            reason="账号已达到今日发布上限，任务已自动顺延至次日",
                            event_type="daily_limit_deferred",
                            now=now,
                        )
                        continue

                    next_interval_time = int(account["last_publish_time"]) + (
                        int(account["min_interval_minutes"]) * 60
                    )
                    if int(account["last_publish_time"]) > 0 and next_interval_time > now_time:
                        self._defer_item_locked(
                            cursor,
                            row,
                            retry_time=next_interval_time,
                            reason="账号仍在最小发布间隔保护期，任务已自动顺延",
                            event_type="publish_interval_deferred",
                            now=now,
                        )
                        continue

                    cursor.execute(
                        """
                        select id
                        from matrix_publish_item
                        where xhs_account_id = %s
                          and content_fingerprint = %s
                          and content_fingerprint <> ''
                          and status = 4
                          and submitted_time >= %s
                          and id <> %s
                        limit 1
                        """,
                        (
                            account_id,
                            content_fingerprint,
                            max(
                                now_time - CONTENT_DEDUPLICATION_WINDOW_SECONDS,
                                0,
                            ),
                            int(row["id"]),
                        ),
                    )
                    duplicate_item = cursor.fetchone()
                    if duplicate_item is not None:
                        reason = "检测到同账号近 7 天已发布相同内容，已拦截重复提交"
                        cursor.execute(
                            """
                            update matrix_publish_item
                            set status = 6, last_error = %s, update_time = %s
                            where id = %s and status = 2
                            """,
                            (reason, now, int(row["id"])),
                        )
                        cursor.execute(
                            """
                            update matrix_publish_plan
                            set status = 6, update_time = %s
                            where id = %s
                            """,
                            (now, int(row["plan_id"])),
                        )
                        self._insert_event_locked(
                            cursor,
                            plan_id=int(row["plan_id"]),
                            item_id=int(row["id"]),
                            user_id=int(row["user_id"]),
                            xhs_account_id=account_id,
                            event_type="duplicate_content_blocked",
                            message=reason,
                            detail={"duplicate_item_id": int(duplicate_item["id"])},
                            now=now,
                        )
                        continue

                    lease_token = uuid4().hex
                    lease_expires_time = now_time + WORKER_LEASE_SECONDS
                    cursor.execute(
                        """
                        update matrix_publish_item
                        set status = 3,
                            attempt_count = attempt_count + 1,
                            lease_token = %s,
                            lease_expires_time = %s,
                            next_retry_time = 0,
                            update_time = %s
                        where id = %s and status = 2
                        """,
                        (
                            lease_token,
                            lease_expires_time,
                            now,
                            int(row["id"]),
                        ),
                    )
                    row["lease_token"] = lease_token
                    row["lease_expires_time"] = lease_expires_time
                    row["attempt_count"] = int(row["attempt_count"]) + 1
                    self._insert_event_locked(
                        cursor,
                        plan_id=int(row["plan_id"]),
                        item_id=int(row["id"]),
                        user_id=int(row["user_id"]),
                        xhs_account_id=account_id,
                        event_type="claim_acquired",
                        message="发布执行器已领取任务",
                        detail={
                            "lease_expires_time": lease_expires_time,
                            "attempt_count": row["attempt_count"],
                        },
                        now=now,
                    )
                    claimed_account_ids.add(account_id)
                    rows.append(row)

                if rows:
                    plan_ids = sorted({int(row["plan_id"]) for row in rows})
                    plan_placeholders = ", ".join(["%s"] * len(plan_ids))
                    cursor.execute(
                        f"""
                        update matrix_publish_plan
                        set status = 4, update_time = %s
                        where id in ({plan_placeholders})
                        """,
                        (now, *plan_ids),
                    )
            self.conn.commit()
            return [self._row_to_claimed_item(row) for row in rows]
        except Exception:
            self.conn.rollback()
            raise

    def mark_item_success(
        self,
        item_id: int,
        lease_token: str,
        message: str,
        result_data: dict[str, Any] | None = None,
    ) -> dict | None:
        return self._mark_worker_item(
            item_id,
            lease_token=lease_token,
            target_status=4,
            last_error="",
            plan_failure=False,
            success_message=message,
            result_data=result_data,
        )

    def mark_item_failed(
        self,
        item_id: int,
        lease_token: str,
        error_message: str,
        *,
        retryable: bool = False,
        retry_delay_seconds: int = 60,
    ) -> dict | None:
        return self._mark_worker_item(
            item_id,
            lease_token=lease_token,
            target_status=5,
            last_error=error_message,
            plan_failure=True,
            retryable=retryable,
            retry_delay_seconds=retry_delay_seconds,
        )

    def mark_item_manual_takeover(
        self,
        item_id: int,
        lease_token: str,
        reason: str,
        *,
        invalidate_account_login: bool = False,
        mark_account_risk: bool = False,
    ) -> dict | None:
        return self._mark_worker_item(
            item_id,
            lease_token=lease_token,
            target_status=6,
            last_error=reason,
            plan_failure=True,
            invalidate_account_login=invalidate_account_login,
            mark_account_risk=mark_account_risk,
        )

    def validate_product_for_user(self, user_id: int, product_id: int) -> bool:
        with self.conn.cursor() as cursor:
            cursor.execute(
                "select id from product where user_id = %s and id = %s",
                (user_id, product_id),
            )
            return cursor.fetchone() is not None

    def validate_accounts_for_user(self, user_id: int, account_ids: list[int]) -> bool:
        unique_account_ids = sorted(set(account_ids))
        if not unique_account_ids:
            return False

        placeholders = ", ".join(["%s"] * len(unique_account_ids))
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select count(*) as total
                from xhs_account
                where user_id = %s and id in ({placeholders})
                """,
                (user_id, *unique_account_ids),
            )
            row = cursor.fetchone()
        return row is not None and int(row["total"]) == len(unique_account_ids)

    def _select_plan_sql(self) -> str:
        return """
            select
                p.id,
                p.user_id,
                p.plan_name,
                p.source_type,
                p.content_type,
                p.product_id,
                p.status,
                p.schedule_start_time,
                p.schedule_end_time,
                p.scheduling_rule_json,
                p.create_time,
                p.update_time,
                coalesce(item_counts.item_count, 0) as item_count
            from matrix_publish_plan p
            left join (
                select plan_id, count(*) as item_count
                from matrix_publish_item
                where user_id = %s
                group by plan_id
            ) item_counts on item_counts.plan_id = p.id
            """

    def _row_to_plan(self, row: dict) -> dict:
        plan = {field: row[field] for field in PLAN_FIELDS}
        plan["scheduling_rule"] = self._load_json_dict(row["scheduling_rule_json"])
        plan["item_count"] = int(row["item_count"])
        return plan

    def _row_to_item(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "plan_id": row["plan_id"],
            "user_id": row["user_id"],
            "xhs_account_id": row["xhs_account_id"],
            "content_type": row["content_type"],
            "title": row["title"],
            "body": row["body"],
            "tags": self._load_json_list(row["tag_json"]),
            "material": self._load_json_dict(row["material_json"]),
            "scheduled_time": row["scheduled_time"],
            "status": row["status"],
            "last_error": row["last_error"],
            "attempt_count": row["attempt_count"],
            "max_attempts": row["max_attempts"],
            "next_retry_time": row["next_retry_time"],
            "submitted_time": row["submitted_time"],
            "publish_result": self._load_json_dict(row["publish_result_json"]),
            "content_fingerprint": row["content_fingerprint"],
            "create_time": row["create_time"],
            "update_time": row["update_time"],
        }

    def _row_to_claimed_item(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "plan_id": row["plan_id"],
            "user_id": row["user_id"],
            "xhs_account_id": row["xhs_account_id"],
            "lease_token": row["lease_token"],
            "lease_expires_time": row["lease_expires_time"],
            "attempt_count": row["attempt_count"],
            "max_attempts": row["max_attempts"],
            "login_state_path": row["login_state_path"],
            "content_type": row["content_type"],
            "title": row["title"],
            "body": row["body"],
            "tags": self._load_json_list(row["tag_json"]),
            "material": self._load_json_dict(row["material_json"]),
            "scheduled_time": row["scheduled_time"],
        }

    def _mark_worker_item(
        self,
        item_id: int,
        lease_token: str,
        target_status: int,
        last_error: str,
        plan_failure: bool,
        invalidate_account_login: bool = False,
        mark_account_risk: bool = False,
        retryable: bool = False,
        retry_delay_seconds: int = 60,
        success_message: str = "",
        result_data: dict[str, Any] | None = None,
    ) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select plan_id, user_id, xhs_account_id
                    from matrix_publish_item
                    where id = %s
                    """,
                    (item_id,),
                )
                item_plan = cursor.fetchone()
                if item_plan is None:
                    return self._rollback_result(None)

                plan_id = int(item_plan["plan_id"])
                account_login_invalidated = False
                account_marked_risk = False
                cursor.execute(
                    """
                    select id
                    from matrix_publish_plan
                    where id = %s
                    for update
                    """,
                    (plan_id,),
                )
                plan = cursor.fetchone()
                if plan is None:
                    return self._rollback_result(None)

                cursor.execute(
                    """
                    select id, plan_id, status, lease_token,
                           attempt_count, max_attempts
                    from matrix_publish_item
                    where id = %s
                    for update
                    """,
                    (item_id,),
                )
                item = cursor.fetchone()
                if item is None:
                    return self._rollback_result(None)
                if int(item["status"]) != 3:
                    return self._rollback_result({"error": "publish item is not submitting"})
                if str(item["lease_token"]) != lease_token:
                    return self._rollback_result({"error": "publish item lease has expired"})

                if target_status == 4:
                    wallet = WalletRepository(self.conn)
                    already_charged = (
                        wallet.has_ledger_entry(
                            int(item_plan["user_id"]),
                            "scheduled_publish",
                            item_id,
                            reason_prefix="内容发布成功",
                        )
                        or wallet.has_ledger_entry(
                            int(item_plan["user_id"]),
                            "scheduled_publish",
                            item_id,
                            reason_prefix="视频定时发布任务",
                        )
                        or wallet.has_ledger_entry(
                            int(item_plan["user_id"]),
                            "scheduled_publish",
                            plan_id,
                            reason_prefix="定时发布计划",
                        )
                    )
                    if not already_charged:
                        wallet.adjust_credits(
                            int(item_plan["user_id"]),
                            -CreditChargeService().estimate("scheduled_publish"),
                            "scheduled_publish",
                            item_id,
                            "内容发布成功",
                            commit=False,
                        )

                retry_scheduled = (
                    retryable
                    and int(item["attempt_count"]) < int(item["max_attempts"])
                )
                next_retry_time = now + retry_delay_seconds if retry_scheduled else 0
                if retry_scheduled:
                    target_status = 2
                    plan_failure = False

                publish_result = None
                submitted_time = 0
                if target_status == 4:
                    publish_result = dict(result_data or {})
                    if success_message:
                        publish_result.setdefault("message", success_message)
                    submitted_time = now

                cursor.execute(
                    """
                    update matrix_publish_item
                    set status = %s,
                        last_error = %s,
                        lease_token = '',
                        lease_expires_time = 0,
                        next_retry_time = %s,
                        submitted_time = %s,
                        publish_result_json = %s,
                        update_time = %s
                    where id = %s
                    """,
                    (
                        target_status,
                        last_error,
                        next_retry_time,
                        submitted_time,
                        self._dump_json(publish_result) if publish_result else "",
                        now,
                        item_id,
                    ),
                )
                if invalidate_account_login:
                    cursor.execute(
                        """
                        update xhs_account
                        set status = 2, update_time = %s
                        where id = %s and user_id = %s
                        """,
                        (
                            now,
                            int(item_plan["xhs_account_id"]),
                            int(item_plan["user_id"]),
                        ),
                    )
                    account_login_invalidated = cursor.rowcount > 0
                elif mark_account_risk:
                    cursor.execute(
                        """
                        update xhs_account
                        set status = 4, update_time = %s
                        where id = %s and user_id = %s
                        """,
                        (
                            now,
                            int(item_plan["xhs_account_id"]),
                            int(item_plan["user_id"]),
                        ),
                    )
                    account_marked_risk = cursor.rowcount > 0
                if target_status == 4:
                    count_date = business_date(now)
                    cursor.execute(
                        """
                        update xhs_account
                        set last_publish_time = %s,
                            today_publish_count = case
                                when publish_count_date = %s
                                    then today_publish_count + 1
                                else 1
                            end,
                            publish_count_date = %s,
                            update_time = %s
                        where id = %s and user_id = %s
                        """,
                        (
                            now,
                            count_date,
                            count_date,
                            now,
                            int(item_plan["xhs_account_id"]),
                            int(item_plan["user_id"]),
                        ),
                    )
                event_type = self._worker_event_type(
                    target_status=target_status,
                    retry_scheduled=retry_scheduled,
                )
                self._insert_event_locked(
                    cursor,
                    plan_id=plan_id,
                    item_id=item_id,
                    user_id=int(item_plan["user_id"]),
                    xhs_account_id=int(item_plan["xhs_account_id"]),
                    event_type=event_type,
                    message=success_message if target_status == 4 else last_error,
                    detail={
                        "retry_scheduled": retry_scheduled,
                        "next_retry_time": next_retry_time,
                        "account_login_invalidated": account_login_invalidated,
                        "account_marked_risk": account_marked_risk,
                    },
                    now=now,
                )
                if target_status in (5, 6):
                    self._insert_issue_notification_locked(
                        cursor,
                        item_id=item_id,
                        user_id=int(item_plan["user_id"]),
                        message=last_error,
                        account_marked_risk=account_marked_risk,
                        account_login_invalidated=account_login_invalidated,
                        now=now,
                    )
                if plan_failure:
                    cursor.execute(
                        """
                        update matrix_publish_plan
                        set status = 6, update_time = %s
                        where id = %s
                        """,
                        (now, plan_id),
                    )
                    plan_status = 6
                else:
                    plan_status = self._refresh_plan_status_locked(cursor, plan_id, now)
            self.conn.commit()
            return {
                "id": item_id,
                "plan_id": plan_id,
                "status": target_status,
                "plan_status": plan_status,
                "retry_scheduled": retry_scheduled,
                "next_retry_time": next_retry_time,
                "account_login_invalidated": account_login_invalidated,
                "account_marked_risk": account_marked_risk,
            }
        except Exception:
            self.conn.rollback()
            raise

    def _recover_expired_leases_locked(self, cursor, now_time: int, now: int) -> None:
        cursor.execute(
            """
            select id, plan_id
            from matrix_publish_item
            where status = 3
              and (
                    (lease_expires_time > 0 and lease_expires_time <= %s)
                    or
                    (lease_expires_time = 0 and update_time <= %s)
                  )
            for update skip locked
            """,
            (now_time, max(now_time - WORKER_LEASE_SECONDS, 0)),
        )
        expired_items = cursor.fetchall()
        if not expired_items:
            return

        item_ids = [int(row["id"]) for row in expired_items]
        plan_ids = sorted({int(row["plan_id"]) for row in expired_items})
        item_placeholders = ", ".join(["%s"] * len(item_ids))
        plan_placeholders = ", ".join(["%s"] * len(plan_ids))
        cursor.execute(
            f"""
            update matrix_publish_item
            set status = 6,
                last_error = %s,
                lease_token = '',
                lease_expires_time = 0,
                update_time = %s
            where id in ({item_placeholders})
              and status = 3
            """,
            (EXPIRED_LEASE_REASON, now, *item_ids),
        )
        cursor.execute(
            f"""
            update matrix_publish_plan
            set status = 6, update_time = %s
            where id in ({plan_placeholders})
            """,
            (now, *plan_ids),
        )

    def _draft_item_material(self, draft: dict, account_id: int) -> dict:
        material = dict(draft.get("material") or {})
        material["draft_id"] = draft["id"]
        material["source_content_draft_id"] = draft["id"]
        material["source_product_id"] = draft["product_id"]
        material["target_xhs_account_id"] = account_id
        return material

    def _insert_event_locked(
        self,
        cursor,
        *,
        plan_id: int,
        item_id: int,
        user_id: int,
        xhs_account_id: int,
        event_type: str,
        message: str,
        detail: dict[str, Any],
        now: int,
    ) -> None:
        cursor.execute(
            """
            insert into matrix_publish_event_log (
                tenant_id, plan_id, item_id, user_id, xhs_account_id,
                event_type, message, detail_json, create_time
            )
            select
                u.tenant_id, %s, %s, %s, %s,
                %s, %s, %s, %s
            from app_user u
            where u.id = %s
            """,
            (
                plan_id,
                item_id,
                user_id,
                xhs_account_id,
                event_type,
                message[:1000],
                self._dump_json(detail),
                now,
                user_id,
            ),
        )

    def _insert_issue_notification_locked(
        self,
        cursor,
        *,
        item_id: int,
        user_id: int,
        message: str,
        account_marked_risk: bool,
        account_login_invalidated: bool,
        now: int,
    ) -> None:
        if account_marked_risk:
            title = "小红书账号需要人工检查"
            priority = 3
        elif account_login_invalidated:
            title = "小红书账号登录已失效"
            priority = 3
        else:
            title = "小红书发布任务需要处理"
            priority = 2
        cursor.execute(
            """
            insert into user_notification (
                tenant_id, recipient_user_id, sender_user_id,
                notification_type, title, content, priority,
                action_path, business_type, business_id,
                deadline_time, read_time, status, create_time, update_time
            )
            select
                u.tenant_id, u.id, 0,
                'system', %s, %s, %s,
                'schedule', 'matrix_publish_item_issue', %s,
                0, 0, 1, %s, %s
            from app_user u
            where u.id = %s
            """,
            (
                title,
                message[:2000],
                priority,
                item_id,
                now,
                now,
                user_id,
            ),
        )

    def _defer_item_locked(
        self,
        cursor,
        row: dict,
        *,
        retry_time: int,
        reason: str,
        event_type: str,
        now: int,
    ) -> None:
        cursor.execute(
            """
            update matrix_publish_item
            set next_retry_time = %s,
                last_error = %s,
                update_time = %s
            where id = %s and status = 2
            """,
            (retry_time, reason, now, int(row["id"])),
        )
        self._insert_event_locked(
            cursor,
            plan_id=int(row["plan_id"]),
            item_id=int(row["id"]),
            user_id=int(row["user_id"]),
            xhs_account_id=int(row["xhs_account_id"]),
            event_type=event_type,
            message=reason,
            detail={"next_retry_time": retry_time},
            now=now,
        )

    def _worker_event_type(
        self,
        *,
        target_status: int,
        retry_scheduled: bool,
    ) -> str:
        if retry_scheduled:
            return "publish_retry_scheduled"
        return {
            4: "publish_succeeded",
            5: "publish_failed",
            6: "manual_takeover",
        }.get(target_status, "publish_status_changed")

    def _refresh_plan_status_locked(self, cursor, plan_id: int, now: int) -> int:
        cursor.execute(
            """
            select status
            from matrix_publish_item
            where plan_id = %s and status <> 7
            for update
            """,
            (plan_id,),
        )
        statuses = [int(row["status"]) for row in cursor.fetchall()]
        if any(status in {5, 6} for status in statuses):
            status = 6
        elif statuses and all(status == 4 for status in statuses):
            status = 5
        else:
            status = 4

        cursor.execute(
            """
            update matrix_publish_plan
            set status = %s, update_time = %s
            where id = %s
            """,
            (status, now, plan_id),
        )
        return status

    def _dump_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _load_json_dict(self, raw_value: str) -> dict:
        if not raw_value:
            return {}
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return {}
        if isinstance(parsed, dict):
            return parsed
        return {}

    def _load_json_list(self, raw_value: str) -> list:
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return []
        if isinstance(parsed, list):
            return parsed
        return []

    def _rollback_result(self, result):
        self.conn.rollback()
        return result
