import json
import time
from typing import Any

from app.schemas.content_draft import ContentDraftGenerateRequest, ContentDraftUpdateRequest


STATUS_TO_CODE = {"draft": 1, "confirmed": 2, "rejected": 3}
CODE_TO_STATUS = {value: key for key, value in STATUS_TO_CODE.items()}


class ContentDraftRepository:
    def __init__(self, conn):
        self.conn = conn

    def create_draft(
        self,
        user_id: int,
        payload: ContentDraftGenerateRequest,
        generated: dict[str, Any],
    ) -> int:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into content_draft (
                        user_id, product_id, xhs_account_id, source_type,
                        content_type, title, body, tag_json, material_json,
                        status, ai_provider, model_name, prompt_json,
                        create_time, update_time
                    )
                    values (%s, %s, %s, 'product', 'image_text', %s, %s, %s, %s,
                            1, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        payload.product_id,
                        payload.xhs_account_id,
                        generated["title"],
                        generated["body"],
                        self._dump_json(generated["tags"]),
                        self._dump_json(generated["material"]),
                        generated["ai_provider"],
                        generated["model_name"],
                        self._dump_json(generated["prompt"]),
                        now,
                        now,
                    ),
                )
                draft_id = int(cursor.lastrowid)
            self.conn.commit()
            return draft_id
        except Exception:
            self.conn.rollback()
            raise

    def create_from_ai_text(
        self,
        user_id: int,
        source_type: str,
        source_id: int,
        title: str,
        body: str,
        ai_provider: str,
        model_name: str,
        context: dict,
    ) -> int:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id
                from content_draft
                where user_id = %s and source_type = %s
                  and cast(json_unquote(json_extract(material_json, '$.source_id')) as unsigned) = %s
                limit 1
                """,
                (user_id, source_type, source_id),
            )
            existing = cursor.fetchone()
        if existing is not None:
            return int(existing["id"])

        now = int(time.time())
        material = {"source_id": source_id, "context": context}
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into content_draft (
                        user_id, product_id, xhs_account_id, source_type,
                        content_type, title, body, tag_json, material_json,
                        status, ai_provider, model_name, prompt_json,
                        create_time, update_time
                    )
                    values (%s, %s, %s, %s, 'image_text', %s, %s, '[]', %s,
                            1, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        int(context.get("linked_product_id", 0)),
                        int(context.get("linked_xhs_account_id", 0)),
                        source_type,
                        title,
                        body,
                        self._dump_json(material),
                        ai_provider,
                        model_name,
                        self._dump_json(context),
                        now,
                        now,
                    ),
                )
                draft_id = int(cursor.lastrowid)
            self.conn.commit()
            return draft_id
        except Exception:
            self.conn.rollback()
            raise

    def get_for_user(self, user_id: int, draft_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql()
                + """
                where user_id = %s and id = %s
                """,
                (user_id, draft_id),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_draft(row)

    def list_for_user_by_ids(self, user_id: int, draft_ids: list[int]) -> list[dict]:
        if not draft_ids:
            return []

        placeholders = ", ".join(["%s"] * len(draft_ids))
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql()
                + f"""
                where user_id = %s and id in ({placeholders})
                """,
                (user_id, *draft_ids),
            )
            rows = cursor.fetchall()

        drafts_by_id = {int(row["id"]): self._row_to_draft(row) for row in rows}
        return [drafts_by_id[draft_id] for draft_id in draft_ids if draft_id in drafts_by_id]

    def list_by_user(
        self,
        user_id: int,
        product_id: int | None = None,
        status: str | None = None,
    ) -> list[dict]:
        clauses = ["user_id = %s"]
        params: list[Any] = [user_id]
        if product_id is not None:
            clauses.append("product_id = %s")
            params.append(product_id)
        if status is not None:
            clauses.append("status = %s")
            params.append(STATUS_TO_CODE[status])

        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql()
                + f"""
                where {' and '.join(clauses)}
                order by id desc
                """,
                tuple(params),
            )
            return [self._row_to_draft(row) for row in cursor.fetchall()]

    def update_for_user(
        self,
        user_id: int,
        draft_id: int,
        payload: ContentDraftUpdateRequest,
    ) -> dict | None:
        existing = self.get_for_user(user_id, draft_id)
        if existing is None:
            return None

        title = payload.title if payload.title is not None else existing["title"]
        body = payload.body if payload.body is not None else existing["body"]
        tags = payload.tags if payload.tags is not None else existing["tags"]
        status = payload.status if payload.status is not None else existing["status"]
        now = int(time.time())

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    update content_draft
                    set title = %s,
                        body = %s,
                        tag_json = %s,
                        status = %s,
                        update_time = %s
                    where user_id = %s and id = %s
                    """,
                    (
                        title,
                        body,
                        self._dump_json(tags),
                        STATUS_TO_CODE[status],
                        now,
                        user_id,
                        draft_id,
                    ),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        return self.get_for_user(user_id, draft_id)

    def _select_sql(self) -> str:
        return """
            select id, user_id, product_id, xhs_account_id, source_type,
                   content_type, title, body, tag_json, material_json, status,
                   ai_provider, model_name, prompt_json, create_time, update_time
            from content_draft
            """

    def _row_to_draft(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "product_id": row["product_id"],
            "xhs_account_id": row["xhs_account_id"],
            "source_type": row["source_type"],
            "content_type": row["content_type"],
            "title": row["title"],
            "body": row["body"],
            "tags": self._load_json_list(row["tag_json"]),
            "material": self._load_json_dict(row["material_json"]),
            "status": CODE_TO_STATUS.get(row["status"], "draft"),
            "ai_provider": row["ai_provider"],
            "model_name": row["model_name"],
            "prompt": self._load_json_dict(row["prompt_json"]),
            "create_time": row["create_time"],
            "update_time": row["update_time"],
        }

    def _dump_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _load_json_list(self, raw_value: str) -> list:
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return []
        return parsed if isinstance(parsed, list) else []

    def _load_json_dict(self, raw_value: str) -> dict:
        if not raw_value:
            return {}
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
