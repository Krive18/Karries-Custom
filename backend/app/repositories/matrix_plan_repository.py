import json
import time

from app.schemas.matrix_plan import MatrixPlanCreate


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

    def _dump_json(self, value: dict) -> str:
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
