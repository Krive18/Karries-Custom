import json
import re
import time
from typing import Any

from app.repositories.admin_audit_repository import AdminAuditRepository


_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|secret|authorization)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+[a-z0-9._-]+"),
    re.compile(r"\b(?:sk|ak)-[A-Za-z0-9_-]{8,}\b"),
)


def _redact_text(value: object, limit: int = 1000) -> str:
    text = str(value or "")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text[:limit]


def _safe_detail(value: object) -> object:
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, item in value.items():
            if any(part in key.lower() for part in ("password", "token", "secret", "api_key")):
                result[key] = "[REDACTED]"
            else:
                result[key] = _safe_detail(item)
        return result
    if isinstance(value, list):
        return [_safe_detail(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


class DeveloperAlertRepository:
    _MANAGED_TYPES = (
        "viral_analysis_failed",
        "matrix_publish_failed",
        "video_delivery_overdue",
        "ai_call_failed",
    )

    def __init__(self, conn) -> None:
        self.conn = conn

    def sync(self) -> None:
        now = int(time.time())
        since = now - 86400
        detected: list[dict[str, Any]] = []
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, title, error_message, update_time
                from viral_analysis_job where status = 'failed'
                """
            )
            for row in cursor.fetchall():
                detected.append(
                    self._event(
                        key=f"viral_analysis_failed:{row['id']}",
                        alert_type="viral_analysis_failed",
                        severity="ticket",
                        title=f"爆款解析失败：{row['title']}",
                        summary=row["error_message"],
                        source_type="viral_analysis_job",
                        source_id=row["id"],
                        tenant_id=row["tenant_id"],
                        source_time=row["update_time"],
                    )
                )
            cursor.execute(
                """
                select plan.id, user.tenant_id, plan.plan_name, plan.update_time,
                       coalesce((
                           select item.last_error from matrix_publish_item item
                           where item.plan_id = plan.id and item.last_error <> ''
                           order by item.update_time desc, item.id desc limit 1
                       ), '发布计划执行失败') error_message
                from matrix_publish_plan plan
                join app_user user on user.id = plan.user_id
                where plan.status = 6
                """
            )
            for row in cursor.fetchall():
                detected.append(
                    self._event(
                        key=f"matrix_publish_failed:{row['id']}",
                        alert_type="matrix_publish_failed",
                        severity="page",
                        title=f"矩阵发布失败：{row['plan_name']}",
                        summary=row["error_message"],
                        source_type="matrix_publish_plan",
                        source_id=row["id"],
                        tenant_id=row["tenant_id"],
                        source_time=row["update_time"],
                    )
                )
            cursor.execute(
                """
                select job.id, user.tenant_id, job.job_title, job.expected_delivery_time,
                       job.update_time
                from video_edit_job job
                join app_user user on user.id = job.user_id
                where job.status not in (3, 4, 5)
                  and job.review_status <> 'rejected'
                  and job.expected_delivery_time < %s
                """,
                (now,),
            )
            for row in cursor.fetchall():
                detected.append(
                    self._event(
                        key=f"video_delivery_overdue:{row['id']}",
                        alert_type="video_delivery_overdue",
                        severity="page",
                        title=f"视频交付逾期：{row['job_title']}",
                        summary="任务已超过承诺交付时间",
                        source_type="video_edit_job",
                        source_id=row["id"],
                        tenant_id=row["tenant_id"],
                        source_time=max(int(row["update_time"]), int(row["expected_delivery_time"])),
                    )
                )
            cursor.execute(
                """
                select id, tenant_id, business_type, error_message, create_time
                from ai_usage_log
                where status = 'failed' and create_time >= %s
                """,
                (since,),
            )
            for row in cursor.fetchall():
                detected.append(
                    self._event(
                        key=f"ai_call_failed:{row['id']}",
                        alert_type="ai_call_failed",
                        severity="ticket",
                        title=f"AI 调用失败：{row['business_type']}",
                        summary=row["error_message"],
                        source_type="ai_usage_log",
                        source_id=row["id"],
                        tenant_id=row["tenant_id"],
                        source_time=row["create_time"],
                    )
                )

            for event in detected:
                cursor.execute(
                    """
                    insert into developer_alert_event (
                        alert_key, alert_type, severity, status, title, summary,
                        source_type, source_id, tenant_id, assigned_user_id,
                        detected_time, last_seen_time, acknowledged_by,
                        acknowledged_time, resolved_by, resolved_time, resolution,
                        detail_json, create_time, update_time
                    ) values (
                        %s, %s, %s, 'open', %s, %s, %s, %s, %s, 0,
                        %s, %s, 0, 0, 0, 0, '', %s, %s, %s
                    )
                    on duplicate key update
                        severity = values(severity),
                        title = values(title),
                        summary = values(summary),
                        last_seen_time = values(last_seen_time),
                        detail_json = values(detail_json),
                        acknowledged_by = if(
                            developer_alert_event.status = 'resolved'
                            and values(last_seen_time) > developer_alert_event.resolved_time,
                            0, developer_alert_event.acknowledged_by
                        ),
                        acknowledged_time = if(
                            developer_alert_event.status = 'resolved'
                            and values(last_seen_time) > developer_alert_event.resolved_time,
                            0, developer_alert_event.acknowledged_time
                        ),
                        resolved_by = if(
                            developer_alert_event.status = 'resolved'
                            and values(last_seen_time) > developer_alert_event.resolved_time,
                            0, developer_alert_event.resolved_by
                        ),
                        resolved_time = if(
                            developer_alert_event.status = 'resolved'
                            and values(last_seen_time) > developer_alert_event.resolved_time,
                            0, developer_alert_event.resolved_time
                        ),
                        resolution = if(
                            developer_alert_event.status = 'resolved'
                            and values(last_seen_time) > developer_alert_event.resolved_time,
                            '', developer_alert_event.resolution
                        ),
                        status = if(
                            developer_alert_event.status = 'resolved'
                            and values(last_seen_time) > developer_alert_event.resolved_time,
                            'open', developer_alert_event.status
                        ),
                        update_time = values(update_time)
                    """,
                    (
                        event["alert_key"],
                        event["alert_type"],
                        event["severity"],
                        event["title"],
                        event["summary"],
                        event["source_type"],
                        event["source_id"],
                        event["tenant_id"],
                        event["source_time"],
                        event["source_time"],
                        json.dumps(event["detail"], ensure_ascii=False),
                        now,
                        now,
                    ),
                )

            active_keys = [event["alert_key"] for event in detected]
            placeholders = ", ".join(["%s"] * len(active_keys))
            managed_placeholders = ", ".join(["%s"] * len(self._MANAGED_TYPES))
            inactive_sql = (
                f"and alert_key not in ({placeholders})" if active_keys else ""
            )
            cursor.execute(
                f"""
                update developer_alert_event
                set status = 'resolved', resolved_by = 0, resolved_time = %s,
                    resolution = 'Condition cleared automatically', update_time = %s
                where status in ('open', 'acknowledged')
                  and alert_type in ({managed_placeholders})
                  {inactive_sql}
                """,
                (now, now, *self._MANAGED_TYPES, *active_keys),
            )
        self.conn.commit()

    def list(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None,
        severity: str | None,
        alert_type: str | None,
    ) -> dict:
        clauses: list[str] = []
        params: list[object] = []
        if status:
            clauses.append("event.status = %s")
            params.append(status)
        if severity:
            clauses.append("event.severity = %s")
            params.append(severity)
        if alert_type:
            clauses.append("event.alert_type = %s")
            params.append(alert_type)
        where_sql = f"where {' and '.join(clauses)}" if clauses else ""
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"select count(*) total from developer_alert_event event {where_sql}",
                tuple(params),
            )
            total = int(cursor.fetchone()["total"] or 0)
            cursor.execute(
                f"""
                select event.*,
                       coalesce(nullif(assignee.nickname, ''), assignee.login_name, '') assigned_user_name
                from developer_alert_event event
                left join app_user assignee on assignee.id = event.assigned_user_id
                {where_sql}
                order by field(event.status, 'open', 'acknowledged', 'resolved'),
                         field(event.severity, 'page', 'ticket'),
                         event.last_seen_time desc, event.id desc
                limit %s offset %s
                """,
                (*params, page_size, offset),
            )
            rows = cursor.fetchall()
        return {
            "items": [self._serialize(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def transition(
        self,
        *,
        alert_id: int,
        action: str,
        reason: str,
        developer_id: int,
    ) -> dict | None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                "select * from developer_alert_event where id = %s for update",
                (alert_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            current = str(row["status"])
            if action == "acknowledge" and current != "open":
                return {"error": "Only open alerts can be acknowledged"}
            if action == "resolve" and current not in {"open", "acknowledged"}:
                return {"error": "Alert is already resolved"}
            if action == "acknowledge":
                cursor.execute(
                    """
                    update developer_alert_event
                    set status = 'acknowledged', acknowledged_by = %s,
                        acknowledged_time = %s, assigned_user_id = %s, update_time = %s
                    where id = %s
                    """,
                    (developer_id, now, developer_id, now, alert_id),
                )
            else:
                cursor.execute(
                    """
                    update developer_alert_event
                    set status = 'resolved', resolved_by = %s, resolved_time = %s,
                        resolution = %s, update_time = %s
                    where id = %s
                    """,
                    (developer_id, now, _redact_text(reason), now, alert_id),
                )
            AdminAuditRepository(self.conn).create(
                tenant_id=int(row["tenant_id"]),
                admin_user_id=developer_id,
                action=f"developer.alert.{action}",
                target_type="developer_alert_event",
                target_id=alert_id,
                detail={"reason": _redact_text(reason), "previous_status": current},
                commit=False,
            )
        self.conn.commit()
        return self.get(alert_id)

    def get(self, alert_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select event.*,
                       coalesce(nullif(assignee.nickname, ''), assignee.login_name, '') assigned_user_name
                from developer_alert_event event
                left join app_user assignee on assignee.id = event.assigned_user_id
                where event.id = %s
                """,
                (alert_id,),
            )
            row = cursor.fetchone()
        return self._serialize(row) if row else None

    @staticmethod
    def _event(**values: object) -> dict[str, Any]:
        return {
            **values,
            "alert_key": str(values["key"]),
            "source_id": int(values["source_id"]),
            "tenant_id": int(values["tenant_id"]),
            "source_time": int(values["source_time"]),
            "title": _redact_text(values["title"], 200),
            "summary": _redact_text(values["summary"]),
            "detail": {"detector": str(values["alert_type"])},
        }

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        try:
            detail = json.loads(row["detail_json"])
        except (TypeError, json.JSONDecodeError):
            detail = {}
        return {
            "id": int(row["id"]),
            "alert_type": str(row["alert_type"]),
            "severity": str(row["severity"]),
            "status": str(row["status"]),
            "title": _redact_text(row["title"], 200),
            "summary": _redact_text(row["summary"]),
            "source_type": str(row["source_type"]),
            "source_id": int(row["source_id"]),
            "tenant_id": int(row["tenant_id"]),
            "assigned_user_id": int(row["assigned_user_id"]),
            "assigned_user_name": str(row["assigned_user_name"]),
            "detected_at": int(row["detected_time"]),
            "last_seen_at": int(row["last_seen_time"]),
            "acknowledged_at": int(row["acknowledged_time"]),
            "resolved_at": int(row["resolved_time"]),
            "resolution": _redact_text(row["resolution"]),
            "detail": _safe_detail(detail),
        }
