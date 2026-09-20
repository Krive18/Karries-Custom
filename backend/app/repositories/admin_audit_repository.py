import json
import re
import time
from typing import Any


_SENSITIVE_KEY_PARTS = ("password", "token", "secret", "api_key", "authorization")
_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|secret|authorization)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+[a-z0-9._-]+"),
    re.compile(r"\b(?:sk|ak)-[A-Za-z0-9_-]{8,}\b"),
)


def _redact_text(value: str) -> str:
    result = value
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result[:2000]


def _safe_detail(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if any(part in str(key).lower() for part in _SENSITIVE_KEY_PARTS)
                else _safe_detail(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe_detail(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


class AdminAuditRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def create(
        self,
        tenant_id: int,
        admin_user_id: int,
        action: str,
        target_type: str,
        target_id: int,
        detail: dict[str, Any],
        commit: bool = True,
    ) -> int:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into admin_audit_log (
                    tenant_id, admin_user_id, action, target_type,
                    target_id, detail_json, create_time
                )
                values (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_id,
                    admin_user_id,
                    action,
                    target_type,
                    target_id,
                    json.dumps(detail, ensure_ascii=False),
                    int(time.time()),
                ),
            )
            audit_id = int(cursor.lastrowid)
        if commit:
            self.conn.commit()
        return audit_id

    def list_for_target(
        self,
        target_type: str,
        target_id: int,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select
                    log.id,
                    log.tenant_id,
                    log.admin_user_id,
                    log.action,
                    log.target_type,
                    log.target_id,
                    log.detail_json,
                    log.create_time,
                    coalesce(nullif(user.nickname, ''), user.login_name, '') operator_name
                from admin_audit_log log
                left join app_user user on user.id = log.admin_user_id
                where log.target_type = %s and log.target_id = %s
                order by log.id desc
                limit %s
                """,
                (target_type, target_id, max(1, min(limit, 200))),
            )
            rows = cursor.fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            detail: dict[str, Any] = {}
            try:
                parsed = json.loads(row["detail_json"])
                if isinstance(parsed, dict):
                    detail = parsed
            except (TypeError, json.JSONDecodeError):
                pass
            result.append(
                {
                    "id": int(row["id"]),
                    "tenant_id": int(row["tenant_id"]),
                    "admin_user_id": int(row["admin_user_id"]),
                    "operator_name": str(row["operator_name"]),
                    "action": str(row["action"]),
                    "target_type": str(row["target_type"]),
                    "target_id": int(row["target_id"]),
                    "detail": _safe_detail(detail),
                    "create_time": int(row["create_time"]),
                }
            )
        return result

    def list_global(
        self,
        *,
        page: int,
        page_size: int,
        action: str | None,
        target_type: str | None,
        operator_id: int | None,
        tenant_id: int | None,
        keyword: str,
        start_time: int | None,
        end_time: int | None,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[object] = []
        if action:
            clauses.append("log.action = %s")
            params.append(action)
        if target_type:
            clauses.append("log.target_type = %s")
            params.append(target_type)
        if operator_id is not None:
            clauses.append("log.admin_user_id = %s")
            params.append(operator_id)
        if tenant_id is not None:
            clauses.append("log.tenant_id = %s")
            params.append(tenant_id)
        if start_time is not None:
            clauses.append("log.create_time >= %s")
            params.append(start_time)
        if end_time is not None:
            clauses.append("log.create_time <= %s")
            params.append(end_time)
        if keyword:
            clauses.append(
                "(log.action like %s or log.target_type like %s "
                "or user.login_name like %s or user.nickname like %s)"
            )
            pattern = f"%{keyword}%"
            params.extend([pattern, pattern, pattern, pattern])
        where_sql = f"where {' and '.join(clauses)}" if clauses else ""
        offset = (page - 1) * page_size
        join_sql = "left join app_user user on user.id = log.admin_user_id"
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select count(*) total
                from admin_audit_log log
                {join_sql}
                {where_sql}
                """,
                tuple(params),
            )
            total = int(cursor.fetchone()["total"] or 0)
            cursor.execute(
                f"""
                select log.id, log.tenant_id, log.admin_user_id, log.action,
                       log.target_type, log.target_id, log.detail_json, log.create_time,
                       coalesce(nullif(user.nickname, ''), user.login_name, '') operator_name,
                       coalesce(user.login_name, '') operator_login_name
                from admin_audit_log log
                {join_sql}
                {where_sql}
                order by log.id desc
                limit %s offset %s
                """,
                (*params, page_size, offset),
            )
            rows = cursor.fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            try:
                parsed = json.loads(row["detail_json"])
                detail = parsed if isinstance(parsed, dict) else {}
            except (TypeError, json.JSONDecodeError):
                detail = {}
            items.append(
                {
                    "id": int(row["id"]),
                    "tenant_id": int(row["tenant_id"]),
                    "admin_user_id": int(row["admin_user_id"]),
                    "operator_name": str(row["operator_name"]),
                    "operator_login_name": str(row["operator_login_name"]),
                    "action": str(row["action"]),
                    "target_type": str(row["target_type"]),
                    "target_id": int(row["target_id"]),
                    "detail": _safe_detail(detail),
                    "created_at": int(row["create_time"]),
                }
            )
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
        }
