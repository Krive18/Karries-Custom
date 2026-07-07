import json
import time
from typing import Any

from app.schemas.matrix_plan import MatrixPlanCreate, MatrixPlanFromDraftsCreate


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
                    cursor.execute(
                        """
                        insert into matrix_publish_item (
                            plan_id, user_id, xhs_account_id, content_type,
                            title, body, tag_json, material_json, scheduled_time,
                            status, last_error, create_time, update_time
                        )
                        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, '', %s, %s)
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
                       status, last_error, create_time, update_time
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

    def claim_due_items(self, limit: int, now_time: int) -> list[dict]:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
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
                        i.scheduled_time
                    from matrix_publish_item i
                    join matrix_publish_plan p on p.id = i.plan_id
                    join xhs_account a on a.id = i.xhs_account_id and a.user_id = i.user_id
                    where i.status = 2
                      and i.scheduled_time <= %s
                      and p.status in (3, 4)
                      and a.status = 1
                    order by i.scheduled_time asc, i.id asc
                    limit %s
                    for update skip locked
                    """,
                    (now_time, limit),
                )
                rows = cursor.fetchall()
                if not rows:
                    self.conn.commit()
                    return []

                item_ids = [int(row["id"]) for row in rows]
                plan_ids = sorted({int(row["plan_id"]) for row in rows})
                item_placeholders = ", ".join(["%s"] * len(item_ids))
                plan_placeholders = ", ".join(["%s"] * len(plan_ids))

                cursor.execute(
                    f"""
                    update matrix_publish_item
                    set status = 3, update_time = %s
                    where id in ({item_placeholders})
                    """,
                    (now, *item_ids),
                )
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
            "create_time": row["create_time"],
            "update_time": row["update_time"],
        }

    def _row_to_claimed_item(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "plan_id": row["plan_id"],
            "user_id": row["user_id"],
            "xhs_account_id": row["xhs_account_id"],
            "login_state_path": row["login_state_path"],
            "content_type": row["content_type"],
            "title": row["title"],
            "body": row["body"],
            "tags": self._load_json_list(row["tag_json"]),
            "material": self._load_json_dict(row["material_json"]),
            "scheduled_time": row["scheduled_time"],
        }

    def _draft_item_material(self, draft: dict, account_id: int) -> dict:
        material = dict(draft.get("material") or {})
        material["draft_id"] = draft["id"]
        material["source_content_draft_id"] = draft["id"]
        material["source_product_id"] = draft["product_id"]
        material["target_xhs_account_id"] = account_id
        return material

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
