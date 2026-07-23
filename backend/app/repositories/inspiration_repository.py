import json
import time
from typing import Any

from app.schemas.inspiration import InspirationSessionCreate


class InspirationSessionNotFoundError(LookupError):
    pass


class InspirationSessionStateError(ValueError):
    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(f"inspiration session is {status}")


class InspirationRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def create_session(
        self, tenant_id: int, user_id: int, payload: InspirationSessionCreate
    ) -> dict:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into inspiration_session (
                    tenant_id, user_id, title, linked_product_id,
                    linked_xhs_account_id, goal_type, tone, extra_requirement,
                    create_time, update_time
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    user_id,
                    payload.title,
                    payload.linked_product_id,
                    payload.linked_xhs_account_id,
                    payload.goal_type,
                    payload.tone,
                    payload.extra_requirement,
                    now,
                    now,
                ),
            )
            session_id = int(cursor.lastrowid)
        self.conn.commit()
        session = self.get_session_for_user(tenant_id, user_id, session_id)
        if session is None:
            raise RuntimeError("created inspiration session was not found")
        return session

    def list_sessions_for_user(
        self, tenant_id: int, user_id: int, page: int, page_size: int
    ) -> dict:
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select count(*) as total
                from inspiration_session
                where tenant_id = %s and user_id = %s
                """,
                (tenant_id, user_id),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                self._session_select_sql()
                + """
                where tenant_id = %s and user_id = %s
                order by update_time desc, id desc
                limit %s offset %s
                """,
                (tenant_id, user_id, page_size, offset),
            )
            items = [self._session_from_row(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def list_sessions_for_admin(self, tenant_id: int, page: int, page_size: int) -> dict:
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                "select count(*) as total from inspiration_session where tenant_id = %s",
                (tenant_id,),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                self._session_select_sql()
                + """
                where tenant_id = %s
                order by update_time desc, id desc
                limit %s offset %s
                """,
                (tenant_id, page_size, offset),
            )
            items = [self._session_from_row(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def get_session_for_user(
        self, tenant_id: int, user_id: int, session_id: int
    ) -> dict | None:
        return self._get_session_for_user(tenant_id, user_id, session_id)

    def _get_session_for_user(
        self, tenant_id: int, user_id: int, session_id: int, lock: bool = False
    ) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._session_select_sql()
                + "where tenant_id = %s and user_id = %s and id = %s"
                + (" for update" if lock else ""),
                (tenant_id, user_id, session_id),
            )
            row = cursor.fetchone()
        return self._session_from_row(row) if row is not None else None

    def get_session_for_admin(self, tenant_id: int, session_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._session_select_sql() + "where tenant_id = %s and id = %s",
                (tenant_id, session_id),
            )
            row = cursor.fetchone()
        return self._session_from_row(row) if row is not None else None

    def claim_and_store_user_message(
        self,
        tenant_id: int,
        user_id: int,
        session_id: int,
        content: str,
        context: dict,
    ) -> tuple[dict, dict]:
        session = self.get_session_for_user(tenant_id, user_id, session_id)
        if session is None:
            raise InspirationSessionNotFoundError
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update inspiration_session
                set status = 'generating', update_time = %s
                where tenant_id = %s and user_id = %s and id = %s and status = 'active'
                """,
                (now, tenant_id, user_id, session_id),
            )
            if cursor.rowcount != 1:
                current = self._get_session_for_user(
                    tenant_id, user_id, session_id, lock=True
                )
                raise InspirationSessionStateError(
                    current["status"] if current is not None else "archived"
                )
            cursor.execute(
                """
                insert into inspiration_message (
                    tenant_id, session_id, user_id, role, content, context_json,
                    ai_provider, ai_model, credit_cost, latency_ms, status,
                    error_message, create_time
                )
                values (%s, %s, %s, 'user', %s, %s, '', '', 0, 0, 'success', '', %s)
                """,
                (tenant_id, session_id, user_id, content, self._dump_json(context), now),
            )
            message_id = int(cursor.lastrowid)
            cursor.execute(
                """
                update inspiration_session
                set message_count = message_count + 1
                where tenant_id = %s and user_id = %s and id = %s and status = 'generating'
                """,
                (tenant_id, user_id, session_id),
            )
        session["status"] = "generating"
        return session, {
            "id": message_id,
            "role": "user",
            "content": content,
            "context": context,
            "status": "success",
        }

    def finalize_generation(
        self,
        tenant_id: int,
        user_id: int,
        session_id: int,
        content: str,
        context: dict,
        ai_provider: str,
        ai_model: str,
        credit_cost: int,
        latency_ms: int,
        status: str,
        error_message: str = "",
    ) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into inspiration_message (
                    tenant_id, session_id, user_id, role, content, context_json,
                    ai_provider, ai_model, credit_cost, latency_ms, status,
                    error_message, create_time
                )
                values (%s, %s, %s, 'assistant', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    session_id,
                    user_id,
                    content,
                    self._dump_json(context),
                    ai_provider,
                    ai_model,
                    credit_cost,
                    latency_ms,
                    status,
                    error_message,
                    now,
                ),
            )
            message_id = int(cursor.lastrowid)
            cursor.execute(
                """
                update inspiration_session
                set status = 'active',
                    message_count = message_count + 1,
                    total_credit_cost = total_credit_cost + %s,
                    update_time = %s
                where tenant_id = %s and user_id = %s and id = %s and status = 'generating'
                """,
                (credit_cost, now, tenant_id, user_id, session_id),
            )
            if cursor.rowcount != 1:
                current = self._get_session_for_user(
                    tenant_id, user_id, session_id, lock=True
                )
                raise InspirationSessionStateError(
                    current["status"] if current is not None else "archived"
                )
        return message_id

    def archive_active_session(
        self, tenant_id: int, user_id: int, session_id: int
    ) -> dict:
        session = self.get_session_for_user(tenant_id, user_id, session_id)
        if session is None:
            raise InspirationSessionNotFoundError
        if session["status"] != "active":
            raise InspirationSessionStateError(session["status"])
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update inspiration_session
                set status = 'archived', update_time = %s
                where tenant_id = %s and user_id = %s and id = %s and status = 'active'
                """,
                (now, tenant_id, user_id, session_id),
            )
            if cursor.rowcount != 1:
                raise InspirationSessionStateError("generating")
        self.conn.commit()
        session["status"] = "archived"
        session["update_time"] = now
        return session

    def list_messages_for_user(
        self, tenant_id: int, user_id: int, session_id: int
    ) -> list[dict]:
        return self._list_messages(
            "where tenant_id = %s and user_id = %s and session_id = %s",
            (tenant_id, user_id, session_id),
        )

    def list_messages_for_admin(self, tenant_id: int, session_id: int) -> list[dict]:
        return self._list_messages(
            "where tenant_id = %s and session_id = %s", (tenant_id, session_id)
        )

    def list_successful_history(
        self, tenant_id: int, user_id: int, session_id: int
    ) -> list[tuple[str, str]]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select role, content
                from inspiration_message
                where tenant_id = %s and user_id = %s and session_id = %s
                  and status = 'success'
                order by id desc
                limit 20
                """,
                (tenant_id, user_id, session_id),
            )
            rows = list(reversed(cursor.fetchall()))
        return [(row["role"], row["content"]) for row in rows]

    def get_message_for_user(
        self, tenant_id: int, user_id: int, message_id: int
    ) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._message_select_sql()
                + "where tenant_id = %s and user_id = %s and id = %s",
                (tenant_id, user_id, message_id),
            )
            row = cursor.fetchone()
        return self._message_from_row(row) if row is not None else None

    def _list_messages(self, where_sql: str, params: tuple) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._message_select_sql() + where_sql + " order by id asc", params
            )
            return [self._message_from_row(row) for row in cursor.fetchall()]

    def _session_select_sql(self) -> str:
        return """
            select id, tenant_id, user_id, title, linked_product_id,
                   linked_xhs_account_id, goal_type, tone, extra_requirement,
                   status, message_count, total_credit_cost, create_time, update_time
            from inspiration_session
            """

    def _message_select_sql(self) -> str:
        return """
            select id, tenant_id, session_id, user_id, role, content, context_json,
                   ai_provider, ai_model, credit_cost, latency_ms, status,
                   error_message, create_time
            from inspiration_message
            """

    def _session_from_row(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "linked_product_id": row["linked_product_id"],
            "linked_xhs_account_id": row["linked_xhs_account_id"],
            "goal_type": row["goal_type"],
            "tone": row["tone"],
            "extra_requirement": row["extra_requirement"],
            "status": row["status"],
            "message_count": row["message_count"],
            "total_credit_cost": row["total_credit_cost"],
            "create_time": row["create_time"],
            "update_time": row["update_time"],
        }

    def _message_from_row(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"],
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "role": row["role"],
            "content": row["content"],
            "context": self._load_json(row["context_json"]),
            "ai_provider": row["ai_provider"],
            "ai_model": row["ai_model"],
            "credit_cost": row["credit_cost"],
            "latency_ms": row["latency_ms"],
            "status": row["status"],
            "error_message": row["error_message"],
            "create_time": row["create_time"],
        }

    def _dump_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _load_json(self, raw_value: str) -> dict:
        try:
            value = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}
