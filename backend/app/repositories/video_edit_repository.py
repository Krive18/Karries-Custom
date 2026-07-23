import json
import time
from typing import Any

from app.schemas.video_edit import (
    VideoEditJobClaimRequest,
    VideoEditJobCreate,
    VideoEditJobDeliverRequest,
)


STATUS_SUBMITTED = 1
STATUS_IN_PRODUCTION = 2
STATUS_DELIVERED = 3
STATUS_REVISION_REQUESTED = 4
STATUS_CANCELLED = 5

STATUS_NAMES = {
    STATUS_SUBMITTED: "submitted",
    STATUS_IN_PRODUCTION: "in_production",
    STATUS_DELIVERED: "delivered",
    STATUS_REVISION_REQUESTED: "revision_requested",
    STATUS_CANCELLED: "cancelled",
}

STATUS_TEXT = {
    STATUS_SUBMITTED: "待生成视频",
    STATUS_IN_PRODUCTION: "智能剪辑生成中",
    STATUS_DELIVERED: "视频已生成",
    STATUS_REVISION_REQUESTED: "等待修正",
    STATUS_CANCELLED: "已取消",
}

USER_PROGRESS_TEXT = {
    STATUS_SUBMITTED: "素材和脚本已提交，预计 24 小时内生成完毕",
    STATUS_IN_PRODUCTION: "智能剪辑生成中，预计 24 小时内完成",
    STATUS_DELIVERED: "视频已生成，请查看交付文件",
    STATUS_REVISION_REQUESTED: "视频正在根据反馈继续优化",
    STATUS_CANCELLED: "该剪辑需求已取消",
}


class VideoEditRepository:
    def __init__(self, conn):
        self.conn = conn

    def create_job(
        self,
        user_id: int,
        payload: VideoEditJobCreate,
        now_time: int | None = None,
    ) -> dict:
        now = now_time if now_time is not None else int(time.time())
        expected_delivery_time = now + 24 * 60 * 60
        material_json = self._dump_json([item.model_dump() for item in payload.materials])

        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into video_edit_job (
                    user_id, job_title, script_text, requirement_text,
                    material_json, status, expected_delivery_time,
                    operator_user_id, developer_note, delivery_json,
                    delivered_time, create_time, update_time
                )
                values (%s, %s, %s, %s, %s, %s, %s, 0, '', '{}', 0, %s, %s)
                """,
                (
                    user_id,
                    payload.job_title,
                    payload.script_text,
                    payload.requirement_text,
                    material_json,
                    STATUS_SUBMITTED,
                    expected_delivery_time,
                    now,
                    now,
                ),
            )
            job_id = int(cursor.lastrowid)
        self.conn.commit()
        job = self.get_for_user(user_id, job_id)
        if job is None:
            raise RuntimeError("created video edit job is not readable")
        return job

    def list_for_user(self, user_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql()
                + """
                where user_id = %s
                order by id desc
                """,
                (user_id,),
            )
            return [self._row_to_job(row) for row in cursor.fetchall()]

    def get_for_user(self, user_id: int, job_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql()
                + """
                where user_id = %s and id = %s
                """,
                (user_id, job_id),
            )
            row = cursor.fetchone()
        return self._row_to_job(row) if row else None

    def list_for_developer(self, status: int | None = None) -> list[dict]:
        params: tuple[Any, ...] = ()
        where_sql = ""
        if status is not None:
            where_sql = "where status = %s"
            params = (status,)

        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql()
                + f"""
                {where_sql}
                order by
                    case status
                        when 1 then 1
                        when 2 then 2
                        when 4 then 3
                        when 3 then 4
                        else 5
                    end,
                    id desc
                """,
                params,
            )
            return [self._row_to_job(row) for row in cursor.fetchall()]

    def get_for_developer(self, job_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(self._select_sql() + "where id = %s", (job_id,))
            row = cursor.fetchone()
        return self._row_to_job(row) if row else None

    def claim_job(
        self,
        job_id: int,
        operator_user_id: int,
        payload: VideoEditJobClaimRequest,
    ) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, status
                    from video_edit_job
                    where id = %s
                    for update
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return self._rollback_result(None)
                if int(row["status"]) not in {STATUS_SUBMITTED, STATUS_REVISION_REQUESTED}:
                    return self._rollback_result({"error": "video edit job cannot be claimed"})

                cursor.execute(
                    """
                    update video_edit_job
                    set status = %s, operator_user_id = %s,
                        developer_note = %s, update_time = %s
                    where id = %s
                    """,
                    (
                        STATUS_IN_PRODUCTION,
                        operator_user_id,
                        payload.note,
                        now,
                        job_id,
                    ),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_for_developer(job_id)

    def deliver_job(
        self,
        job_id: int,
        operator_user_id: int,
        payload: VideoEditJobDeliverRequest,
    ) -> dict | None:
        now = int(time.time())
        delivery = {
            "delivery_file_name": payload.delivery_file_name,
            "delivery_file_path": payload.delivery_file_path,
            "delivery_url": payload.delivery_url,
            "note": payload.note,
            "operator_user_id": operator_user_id,
            "delivered_time": now,
        }
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, status
                    from video_edit_job
                    where id = %s
                    for update
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return self._rollback_result(None)
                if int(row["status"]) != STATUS_IN_PRODUCTION:
                    return self._rollback_result({"error": "video edit job is not in production"})

                cursor.execute(
                    """
                    update video_edit_job
                    set status = %s, operator_user_id = %s,
                        developer_note = %s, delivery_json = %s,
                        delivered_time = %s, update_time = %s
                    where id = %s
                    """,
                    (
                        STATUS_DELIVERED,
                        operator_user_id,
                        payload.note,
                        self._dump_json(delivery),
                        now,
                        now,
                        job_id,
                    ),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_for_developer(job_id)

    def _select_sql(self) -> str:
        return """
            select id, user_id, job_title, script_text, requirement_text,
                   material_json, status, expected_delivery_time,
                   operator_user_id, developer_note, delivery_json,
                   delivered_time, create_time, update_time
            from video_edit_job
            """

    def _row_to_job(self, row: dict) -> dict:
        status = int(row["status"])
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "job_title": row["job_title"],
            "script_text": row["script_text"],
            "requirement_text": row["requirement_text"],
            "materials": self._load_json_list(row["material_json"]),
            "status": status,
            "status_name": STATUS_NAMES.get(status, "submitted"),
            "status_text": STATUS_TEXT.get(status, "待生成视频"),
            "user_progress_text": USER_PROGRESS_TEXT.get(
                status,
                "剪辑需求已进入处理流程",
            ),
            "expected_delivery_time": row["expected_delivery_time"],
            "operator_user_id": row["operator_user_id"],
            "developer_note": row["developer_note"],
            "delivery": self._load_json_dict(row["delivery_json"]),
            "delivered_time": row["delivered_time"],
            "create_time": row["create_time"],
            "update_time": row["update_time"],
        }

    def _dump_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _load_json_dict(self, raw_value: str) -> dict:
        if not raw_value:
            return {}
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _load_json_list(self, raw_value: str) -> list:
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return []
        return parsed if isinstance(parsed, list) else []

    def _rollback_result(self, result):
        self.conn.rollback()
        return result
