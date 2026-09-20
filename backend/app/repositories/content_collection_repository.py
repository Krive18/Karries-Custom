import json
import time
from typing import Any

import pymysql

from app.schemas.content_collection import ContentCollectionUpdateRequest


class ContentCollectionRepository:
    EDITABLE_COLUMNS = (
        "title",
        "hook_summary",
        "structure_summary",
        "shot_rhythm",
        "script_breakdown",
        "selling_points",
        "reuse_suggestions",
        "rewritten_script",
        "setting_analysis",
        "lighting_analysis",
        "visual_style",
        "timeline_visual_analysis",
        "visual_evidence",
        "tags",
    )

    def __init__(self, conn):
        self.conn = conn

    def create_from_viral_analysis(
        self,
        *,
        tenant_id: int,
        user_id: int,
        job: dict[str, Any],
    ) -> tuple[dict, bool]:
        result = job["result"]
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into content_collection (
                        tenant_id, user_id, source_type, source_id, title,
                        hook_summary, structure_summary, shot_rhythm,
                        script_breakdown, original_transcript, transcript_analysis,
                        selling_points, reuse_suggestions,
                        rewritten_script, setting_analysis, lighting_analysis,
                        visual_style, timeline_visual_analysis_json,
                        visual_evidence_json, tags, source_context_json,
                        create_time, update_time
                    )
                    values (
                        %s, %s, 'viral_analysis', %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        tenant_id,
                        user_id,
                        job["id"],
                        job["title"].strip(),
                        result["hook_summary"],
                        result["structure_summary"],
                        result["shot_rhythm"],
                        result["script_breakdown"],
                        result.get("original_transcript", ""),
                        result.get("transcript_analysis", ""),
                        result["selling_points"],
                        result["reuse_suggestions"],
                        result["rewritten_script"],
                        result.get("setting_analysis", ""),
                        result.get("lighting_analysis", ""),
                        result.get("visual_style", ""),
                        self._dump_json(result.get("timeline_visual_analysis", [])),
                        self._dump_json(result.get("visual_evidence", [])),
                        self._dump_json(result["tags"]),
                        self._dump_json(
                            {
                                "analysis_goal": job["analysis_goal"],
                                "source_type": job["source_type"],
                                "source_url": job["source_url"],
                            }
                        ),
                        now,
                        now,
                    ),
                )
                collection_id = int(cursor.lastrowid)
            self.conn.commit()
            item = self.get_for_user(tenant_id, user_id, collection_id)
            if item is None:
                raise RuntimeError("created content collection could not be loaded")
            return item, True
        except pymysql.err.IntegrityError:
            self.conn.rollback()
            existing = self.get_by_source(
                tenant_id,
                user_id,
                "viral_analysis",
                int(job["id"]),
            )
            if existing is not None:
                return existing, False
            raise
        except Exception:
            self.conn.rollback()
            raise

    def create_from_inspiration_message(
        self,
        *,
        tenant_id: int,
        user_id: int,
        message: dict[str, Any],
        title: str,
    ) -> tuple[dict, bool]:
        """Persist an AI Agent answer in the editable content collection.

        The source tuple is unique, so retrying the action is idempotent and never
        creates a content-review draft.
        """
        now = int(time.time())
        source_id = int(message["id"])
        content = str(message.get("content") or "").strip()
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into content_collection (
                        tenant_id, user_id, source_type, source_id, title,
                        hook_summary, structure_summary, shot_rhythm,
                        script_breakdown, original_transcript, transcript_analysis,
                        selling_points, reuse_suggestions,
                        rewritten_script, setting_analysis, lighting_analysis,
                        visual_style, timeline_visual_analysis_json,
                        visual_evidence_json, tags, source_context_json,
                        create_time, update_time
                    )
                    values (
                        %s, %s, 'inspiration', %s, %s,
                        '', '', '', '', '', '', '', '', %s, '', '', '',
                        '[]', '[]', '[]', %s, %s, %s
                    )
                    """,
                    (
                        tenant_id,
                        user_id,
                        source_id,
                        title.strip(),
                        content,
                        self._dump_json(
                            {
                                "session_id": int(message.get("session_id") or 0),
                                "ai_provider": str(message.get("ai_provider") or ""),
                                "ai_model": str(message.get("ai_model") or ""),
                                "context": message.get("context") or {},
                            }
                        ),
                        now,
                        now,
                    ),
                )
                collection_id = int(cursor.lastrowid)
            self.conn.commit()
            item = self.get_for_user(tenant_id, user_id, collection_id)
            if item is None:
                raise RuntimeError("created content collection could not be loaded")
            return item, True
        except pymysql.err.IntegrityError:
            self.conn.rollback()
            existing = self.get_by_source(
                tenant_id,
                user_id,
                "inspiration",
                source_id,
            )
            if existing is not None:
                return existing, False
            raise
        except Exception:
            self.conn.rollback()
            raise

    def list_for_user(
        self,
        tenant_id: int,
        user_id: int,
        *,
        page: int,
        page_size: int,
        keyword: str | None,
    ) -> dict:
        clauses = ["tenant_id = %s", "user_id = %s"]
        params: list[Any] = [tenant_id, user_id]
        if keyword:
            like_value = f"%{keyword.strip()}%"
            clauses.append(
                "(title like %s or rewritten_script like %s "
                "or script_breakdown like %s or original_transcript like %s "
                "or transcript_analysis like %s or tags like %s)"
            )
            params.extend([like_value] * 6)
        where_sql = " where " + " and ".join(clauses)
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                "select count(*) as total from content_collection" + where_sql,
                tuple(params),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                self._select_sql()
                + where_sql
                + " order by update_time desc, id desc limit %s offset %s",
                (*params, page_size, offset),
            )
            items = [self._row_to_item(row) for row in cursor.fetchall()]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def get_for_user(self, tenant_id: int, user_id: int, collection_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql()
                + " where tenant_id = %s and user_id = %s and id = %s",
                (tenant_id, user_id, collection_id),
            )
            row = cursor.fetchone()
        return self._row_to_item(row) if row is not None else None

    def get_by_source(
        self,
        tenant_id: int,
        user_id: int,
        source_type: str,
        source_id: int,
    ) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql()
                + " where tenant_id = %s and user_id = %s "
                "and source_type = %s and source_id = %s",
                (tenant_id, user_id, source_type, source_id),
            )
            row = cursor.fetchone()
        return self._row_to_item(row) if row is not None else None

    def update_for_user(
        self,
        tenant_id: int,
        user_id: int,
        collection_id: int,
        payload: ContentCollectionUpdateRequest,
    ) -> dict | None:
        provided = payload.model_fields_set.intersection(self.EDITABLE_COLUMNS)
        if not provided:
            return self.get_for_user(tenant_id, user_id, collection_id)

        assignments: list[str] = []
        params: list[Any] = []
        for column in self.EDITABLE_COLUMNS:
            if column not in provided:
                continue
            value = getattr(payload, column)
            db_column = column
            if column in {"tags", "timeline_visual_analysis", "visual_evidence"}:
                if value and hasattr(value[0], "model_dump"):
                    value = [item.model_dump() for item in value]
                value = self._dump_json(value or [])
                if column != "tags":
                    db_column = f"{column}_json"
            elif isinstance(value, str):
                value = value.strip()
            assignments.append(f"{db_column} = %s")
            params.append(value)
        assignments.append("update_time = %s")
        params.append(int(time.time()))
        params.extend([tenant_id, user_id, collection_id])

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "update content_collection set "
                    + ", ".join(assignments)
                    + " where tenant_id = %s and user_id = %s and id = %s",
                    tuple(params),
                )
                if cursor.rowcount == 0:
                    existing = self.get_for_user(tenant_id, user_id, collection_id)
                    if existing is None:
                        self.conn.rollback()
                        return None
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_for_user(tenant_id, user_id, collection_id)

    def delete_for_user(
        self,
        tenant_id: int,
        user_id: int,
        collection_id: int,
    ) -> bool:
        """Delete only the user's saved collection copy.

        Source AI conversations, viral-analysis tasks, and uploaded materials are
        intentionally outside this operation.
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "delete from content_collection "
                    "where tenant_id = %s and user_id = %s and id = %s",
                    (tenant_id, user_id, collection_id),
                )
                deleted = cursor.rowcount == 1
            if deleted:
                self.conn.commit()
            else:
                self.conn.rollback()
            return deleted
        except Exception:
            self.conn.rollback()
            raise

    @staticmethod
    def _select_sql() -> str:
        return """
            select id, tenant_id, user_id, source_type, source_id, title,
                   hook_summary, structure_summary, shot_rhythm,
                   script_breakdown, selling_points, reuse_suggestions,
                   coalesce(original_transcript, '') as original_transcript,
                   coalesce(transcript_analysis, '') as transcript_analysis,
                   rewritten_script,
                   coalesce(setting_analysis, '') as setting_analysis,
                   coalesce(lighting_analysis, '') as lighting_analysis,
                   coalesce(visual_style, '') as visual_style,
                   coalesce(timeline_visual_analysis_json, '[]')
                       as timeline_visual_analysis_json,
                   coalesce(visual_evidence_json, '[]') as visual_evidence_json,
                   tags, source_context_json,
                   create_time, update_time
            from content_collection
            """

    def _row_to_item(self, row: dict) -> dict:
        item = dict(row)
        item["tags"] = self._load_json_list(item.pop("tags"))
        item["timeline_visual_analysis"] = self._load_json_list(
            item.pop("timeline_visual_analysis_json")
        )
        item["visual_evidence"] = self._load_json_list(
            item.pop("visual_evidence_json")
        )
        item["source_context"] = self._load_json_dict(item.pop("source_context_json"))
        return item

    @staticmethod
    def _dump_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _load_json_list(raw: str) -> list:
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return []
        return value if isinstance(value, list) else []

    @staticmethod
    def _load_json_dict(raw: str) -> dict:
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}
