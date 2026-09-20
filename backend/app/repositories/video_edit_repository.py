import json
import time
from typing import Any

from app.repositories.material_library_repository import (
    MaterialLibraryNotFoundError,
    MaterialLibraryRepository,
)
from app.repositories.wallet_repository import WalletRepository
from app.schemas.video_edit import (
    VideoEditJobClaimRequest,
    VideoEditJobCreate,
    VideoEditJobDeliverRequest,
    VideoEditPublishContentUpdate,
    VideoEditRevisionRequestCreate,
)


STATUS_SUBMITTED = 1
STATUS_IN_PRODUCTION = 2
STATUS_DELIVERED = 3
STATUS_REVISION_REQUESTED = 4
STATUS_RETURNED = 5
VIDEO_PRODUCTION_CREDIT_COST = 160
VIDEO_REVISION_CREDIT_COST = 180
SCHEDULED_PUBLISH_CREDIT_COST = 20
VIDEO_CREATION_CREDIT_COSTS = {
    "standard": VIDEO_PRODUCTION_CREDIT_COST,
    "pro": 180,
}
VIDEO_CREATION_MODE_LABELS = {
    "standard": "标准模式",
    "pro": "AI智能创作 Pro",
}

STATUS_NAMES = {
    STATUS_SUBMITTED: "submitted",
    STATUS_IN_PRODUCTION: "in_production",
    STATUS_DELIVERED: "delivered",
    STATUS_REVISION_REQUESTED: "revision_requested",
    STATUS_RETURNED: "returned",
}

STATUS_TEXT = {
    STATUS_SUBMITTED: "视频待生成",
    STATUS_IN_PRODUCTION: "视频生成中",
    STATUS_DELIVERED: "视频待发布",
    STATUS_REVISION_REQUESTED: "待返修",
    STATUS_RETURNED: "已退回",
}

USER_PROGRESS_TEXT = {
    STATUS_SUBMITTED: "素材与制作要求已提交，预计 24 小时内完成",
    STATUS_IN_PRODUCTION: "视频正在生成，请留意发布计划",
    STATUS_DELIVERED: "视频已生成，可预览并等待自动发布",
    STATUS_REVISION_REQUESTED: "已提交修改意见，正在等待二次剪辑",
    STATUS_RETURNED: "该视频任务已退回，请重新发起视频制作",
}


class VideoEditRepository:
    def __init__(self, conn):
        self.conn = conn

    def create_job(
        self,
        tenant_id: int,
        user_id: int,
        payload: VideoEditJobCreate,
        now_time: int | None = None,
    ) -> dict:
        now = now_time if now_time is not None else int(time.time())
        expected_delivery_time = now + 24 * 60 * 60
        if payload.planned_publish_time > 0:
            expected_delivery_time = min(
                payload.planned_publish_time,
                expected_delivery_time,
            )
        normalized_materials = self._normalize_materials(tenant_id, payload)
        material_json = self._dump_json(normalized_materials)
        creation_mode = self._normalize_creation_mode(payload.creation_mode)
        credit_cost = VIDEO_CREATION_CREDIT_COSTS[creation_mode]
        request_snapshot = {
            "job_title": payload.job_title,
            "post_title": payload.post_title,
            "post_body": payload.post_body,
            "post_tags": payload.post_tags,
            "script_text": payload.script_text,
            "requirement_text": payload.requirement_text,
            "materials": normalized_materials,
            "xhs_account_id": payload.xhs_account_id,
            "planned_publish_time": payload.planned_publish_time,
            "creation_mode": creation_mode,
            "creation_mode_label": VIDEO_CREATION_MODE_LABELS[creation_mode],
            "credit_cost": credit_cost,
            "submitted_at": now,
        }

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into video_edit_job (
                        user_id, job_title, post_title, post_body, post_tag_json,
                        review_status, script_text, requirement_text,
                        material_json, xhs_account_id, planned_publish_time,
                        creation_mode, request_snapshot_json,
                        credit_cost, publish_plan_id, publish_item_id,
                        status, expected_delivery_time,
                        operator_user_id, developer_note, delivery_json,
                        delivered_time, create_time, update_time
                    )
                    values (
                        %s, %s, %s, %s, %s, 'draft', %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        0, 0, %s, %s,
                        0, '', '{}', 0, %s, %s
                    )
                    """,
                    (
                        user_id,
                        payload.job_title,
                        payload.post_title,
                        payload.post_body,
                        self._dump_json(payload.post_tags),
                        payload.script_text,
                        payload.requirement_text,
                        material_json,
                        payload.xhs_account_id,
                        payload.planned_publish_time,
                        creation_mode,
                        self._dump_json(request_snapshot),
                        credit_cost,
                        STATUS_SUBMITTED,
                        expected_delivery_time,
                        now,
                        now,
                    ),
                )
                job_id = int(cursor.lastrowid)
                publish_plan_id = 0
                publish_item_id = 0
                if payload.xhs_account_id > 0 and payload.planned_publish_time > 0:
                    publish_plan_id, publish_item_id = self._create_publish_plan_locked(
                        cursor,
                        user_id=user_id,
                        job_id=job_id,
                        job_title=payload.job_title,
                        post_title=payload.post_title,
                        post_body=payload.post_body,
                        post_tags=payload.post_tags,
                        xhs_account_id=payload.xhs_account_id,
                        planned_publish_time=payload.planned_publish_time,
                        now=now,
                    )
                    cursor.execute(
                        """
                        update video_edit_job
                        set publish_plan_id = %s, publish_item_id = %s
                        where id = %s
                        """,
                        (publish_plan_id, publish_item_id, job_id),
                    )
            WalletRepository(self.conn).ensure_sufficient_credits(
                user_id,
                credit_cost
                + (SCHEDULED_PUBLISH_CREDIT_COST if publish_item_id > 0 else 0),
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        job = self.get_for_user(user_id, job_id)
        if job is None:
            raise RuntimeError("created video edit job is not readable")
        return job

    def _normalize_materials(
        self,
        tenant_id: int,
        payload: VideoEditJobCreate,
    ) -> list[dict]:
        repository = MaterialLibraryRepository(self.conn)
        normalized: list[dict] = []
        for item in payload.materials:
            asset = repository.get_asset(tenant_id, item.material_file_id)
            if asset is None:
                raise MaterialLibraryNotFoundError("material asset not found")
            normalized.append(
                {
                    "material_file_id": int(asset["id"]),
                    "file_name": asset["file_name"],
                    "file_type": (
                        "document"
                        if asset["file_type"] in {"word", "excel", "other"}
                        else asset["file_type"]
                    ),
                    "file_path": asset["file_path"],
                    "mime_type": asset["mime_type"],
                    "file_size": int(asset["file_size"]),
                    "remark": item.remark or "产品知识库素材",
                }
            )
        return normalized

    def list_for_user(self, user_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql()
                + """
                where j.user_id = %s
                order by j.id desc
                """,
                (user_id,),
            )
            return [self._row_to_job(row) for row in cursor.fetchall()]

    def get_for_user(self, user_id: int, job_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql() + "where j.user_id = %s and j.id = %s",
                (user_id, job_id),
            )
            row = cursor.fetchone()
        return self._row_to_job(row) if row else None

    def update_publish_content(
        self,
        user_id: int,
        job_id: int,
        payload: VideoEditPublishContentUpdate,
    ) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, status, review_status, publish_plan_id, publish_item_id
                    from video_edit_job
                    where id = %s and user_id = %s
                    for update
                    """,
                    (job_id, user_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return self._rollback_result(None)

                current_status = int(row["status"])
                if (
                    current_status in {STATUS_REVISION_REQUESTED, STATUS_RETURNED}
                    or row["review_status"] == "rejected"
                ):
                    return self._rollback_result(
                        {"error": "returned video edit job is terminal"}
                    )
                return_video_job = payload.review_status == "rejected"
                next_status = STATUS_RETURNED if return_video_job else current_status

                publish_plan_id = int(row["publish_plan_id"])
                publish_item_id = int(row["publish_item_id"])
                if publish_item_id > 0:
                    cursor.execute(
                        """
                        select status
                        from matrix_publish_item
                        where id = %s
                        for update
                        """,
                        (publish_item_id,),
                    )
                    publish_item = cursor.fetchone()
                    if publish_item is not None and int(publish_item["status"]) > 2:
                        return self._rollback_result(
                            {"error": "publishing has started; content cannot be changed"}
                        )

                cursor.execute(
                    """
                    update video_edit_job
                    set post_title = %s, post_body = %s, post_tag_json = %s,
                        review_status = %s, status = %s, update_time = %s
                    where id = %s and user_id = %s
                    """,
                    (
                        payload.post_title,
                        payload.post_body,
                        self._dump_json(payload.post_tags),
                        payload.review_status,
                        next_status,
                        now,
                        job_id,
                        user_id,
                    ),
                )

                publish_ready = (
                    payload.review_status == "confirmed"
                    and current_status == STATUS_DELIVERED
                )
                publish_item_status = (
                    7
                    if return_video_job
                    else (2 if publish_ready else 1)
                )
                if publish_item_id > 0:
                    cursor.execute(
                        """
                        update matrix_publish_item
                        set title = %s, body = %s, tag_json = %s,
                            status = %s, last_error = '', update_time = %s
                        where id = %s
                        """,
                        (
                            payload.post_title[:20],
                            payload.post_body,
                            self._dump_json(payload.post_tags),
                            publish_item_status,
                            now,
                            publish_item_id,
                        ),
                    )
                if publish_plan_id > 0:
                    cursor.execute(
                        """
                        update matrix_publish_plan
                        set status = %s, update_time = %s
                        where id = %s
                        """,
                        (
                            7 if return_video_job else (3 if publish_ready else 2),
                            now,
                            publish_plan_id,
                        ),
                    )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_for_user(user_id, job_id)

    def request_revision(
        self,
        tenant_id: int,
        user_id: int,
        job_id: int,
        payload: VideoEditRevisionRequestCreate,
    ) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, job_id, feedback
                    from video_edit_revision_request
                    where user_id = %s and client_request_id = %s
                    """,
                    (user_id, payload.client_request_id),
                )
                existing = cursor.fetchone()
                if existing is not None:
                    if (
                        int(existing["job_id"]) != job_id
                        or str(existing["feedback"]) != payload.feedback
                    ):
                        return self._rollback_result(
                            {"error": "client_request_id conflicts with another revision"}
                        )
                    self.conn.rollback()
                    return self.get_for_user(user_id, job_id)

                cursor.execute(
                    """
                    select id, status, review_status, planned_publish_time,
                           publish_plan_id, publish_item_id
                    from video_edit_job
                    where id = %s and user_id = %s
                    for update
                    """,
                    (job_id, user_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return self._rollback_result(None)
                if (
                    int(row["status"]) != STATUS_DELIVERED
                    or str(row["review_status"]) == "rejected"
                ):
                    return self._rollback_result(
                        {"error": "only a delivered video can request revision"}
                    )

                publish_item_id = int(row["publish_item_id"] or 0)
                publish_plan_id = int(row["publish_plan_id"] or 0)
                if publish_item_id > 0:
                    cursor.execute(
                        """
                        select status
                        from matrix_publish_item
                        where id = %s
                        for update
                        """,
                        (publish_item_id,),
                    )
                    publish_item = cursor.fetchone()
                    if publish_item is not None and int(publish_item["status"]) > 2:
                        return self._rollback_result(
                            {"error": "publishing has started; revision cannot be requested"}
                        )

                WalletRepository(self.conn).ensure_sufficient_credits(
                    user_id,
                    VIDEO_REVISION_CREDIT_COST,
                )
                cursor.execute(
                    """
                    select coalesce(max(revision_no), 0) + 1 revision_no
                    from video_edit_revision_request
                    where job_id = %s
                    """,
                    (job_id,),
                )
                revision_no = int(cursor.fetchone()["revision_no"])
                cursor.execute(
                    """
                    insert into video_edit_revision_request (
                        tenant_id, user_id, job_id, revision_no,
                        client_request_id, feedback, credit_cost, status,
                        create_time, update_time
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, 'submitted', %s, %s)
                    """,
                    (
                        tenant_id,
                        user_id,
                        job_id,
                        revision_no,
                        payload.client_request_id,
                        payload.feedback,
                        VIDEO_REVISION_CREDIT_COST,
                        now,
                        now,
                    ),
                )
                revision_request_id = int(cursor.lastrowid)

                if publish_item_id > 0:
                    cursor.execute(
                        """
                        update matrix_publish_item
                        set status = 7, last_error = '', update_time = %s
                        where id = %s
                        """,
                        (now, publish_item_id),
                    )
                if publish_plan_id > 0:
                    cursor.execute(
                        """
                        update matrix_publish_plan
                        set status = 7, update_time = %s
                        where id = %s
                        """,
                        (now, publish_plan_id),
                    )

                next_publish_time = max(
                    int(row["planned_publish_time"]),
                    now + 24 * 60 * 60,
                )
                cursor.execute(
                    """
                    update video_edit_job
                    set status = %s, review_status = 'draft',
                        planned_publish_time = %s,
                        expected_delivery_time = %s,
                        publish_plan_id = 0, publish_item_id = 0,
                        operator_user_id = 0, developer_note = '',
                        update_time = %s
                    where id = %s and user_id = %s
                    """,
                    (
                        STATUS_REVISION_REQUESTED,
                        next_publish_time,
                        now + 24 * 60 * 60,
                        now,
                        job_id,
                        user_id,
                    ),
                )
                WalletRepository(self.conn).adjust_credits(
                    user_id,
                    -VIDEO_REVISION_CREDIT_COST,
                    "video_revision",
                    revision_request_id,
                    "视频返修任务",
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_for_user(user_id, job_id)

    def list_for_developer(
        self,
        status: int | None = None,
        keyword: str = "",
        sla_status: str | None = None,
        tenant_id: int | None = None,
        operator_user_id: int | None = None,
    ) -> list[dict]:
        now = int(time.time())
        conditions: list[str] = []
        params: list[Any] = []
        normalized_keyword = keyword.strip()
        if normalized_keyword:
            like_keyword = f"%{normalized_keyword}%"
            conditions.append(
                """
                (
                    j.job_title like %s
                    or tenant.tenant_name like %s
                    or owner.login_name like %s
                    or owner.nickname like %s
                    or account.display_name like %s
                )
                """
            )
            params.extend([like_keyword] * 5)
        if tenant_id is not None:
            conditions.append("owner.tenant_id = %s")
            params.append(tenant_id)
        if operator_user_id is not None:
            conditions.append("j.operator_user_id = %s")
            params.append(operator_user_id)
        if status == STATUS_REVISION_REQUESTED:
            conditions.append("j.status = 4 and j.review_status <> 'rejected'")
        elif status == STATUS_RETURNED:
            conditions.append("(j.status = 5 or j.review_status = 'rejected')")
        elif status is not None:
            conditions.append("j.status = %s and j.review_status <> 'rejected'")
            params.append(status)
        if sla_status == "completed":
            conditions.append("j.status = 3 and j.review_status <> 'rejected'")
        elif sla_status == "returned":
            conditions.append("(j.status = 5 or j.review_status = 'rejected')")
        elif sla_status == "overdue":
            conditions.append(
                "j.status in (1, 2, 4) and j.review_status <> 'rejected' "
                "and j.expected_delivery_time < %s"
            )
            params.append(now)
        elif sla_status == "due_soon":
            conditions.append(
                """
                j.status in (1, 2, 4)
                and j.review_status <> 'rejected'
                and j.expected_delivery_time >= %s
                and j.expected_delivery_time <= %s
                """
            )
            params.extend([now, now + 3 * 60 * 60])
        elif sla_status == "normal":
            conditions.append(
                "j.status in (1, 2, 4) and j.review_status <> 'rejected' "
                "and j.expected_delivery_time > %s"
            )
            params.append(now + 3 * 60 * 60)

        where_sql = f"where {' and '.join(conditions)}" if conditions else ""

        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql()
                + f"""
                {where_sql}
                order by
                    case
                        when j.status in (1, 2, 4) and j.review_status <> 'rejected'
                             and j.expected_delivery_time < %s then 0
                        when j.status = 4 and j.review_status <> 'rejected' then 1
                        when j.status = 1 then 1
                        when j.status = 2 then 2
                        when j.status = 3 and j.review_status <> 'rejected' then 3
                        else 4
                    end,
                    case when j.status in (1, 2, 4) and j.review_status <> 'rejected'
                        then j.expected_delivery_time else j.update_time end asc,
                    j.id desc
                """,
                (*params, now),
            )
            return [self._row_to_job(row) for row in cursor.fetchall()]

    def get_for_developer(self, job_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(self._select_sql() + "where j.id = %s", (job_id,))
            row = cursor.fetchone()
        return self._row_to_job(row) if row else None

    def get_owner_scope(self, job_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select j.id, j.user_id, u.tenant_id
                from video_edit_job j
                join app_user u on u.id = j.user_id
                where j.id = %s
                """,
                (job_id,),
            )
            return cursor.fetchone()

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
                    select id, status, review_status, operator_user_id
                    from video_edit_job
                    where id = %s
                    for update
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return self._rollback_result(None)
                if (
                    row["review_status"] == "rejected"
                    or int(row["status"])
                    not in {STATUS_SUBMITTED, STATUS_REVISION_REQUESTED}
                ):
                    return self._rollback_result(
                        {"error": "video edit job cannot be claimed"}
                    )
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
        publish_video_path: str | None = None,
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
                    select id, user_id, job_title, post_title, post_body,
                           post_tag_json, review_status, script_text, requirement_text,
                           xhs_account_id, planned_publish_time,
                           publish_plan_id, publish_item_id, status,
                           operator_user_id, delivery_json, credit_cost
                    from video_edit_job
                    where id = %s
                    for update
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return self._rollback_result(None)
                previous_status = int(row["status"])
                if (
                    row["review_status"] == "rejected"
                    or previous_status not in {STATUS_IN_PRODUCTION, STATUS_DELIVERED}
                ):
                    return self._rollback_result(
                        {"error": "video edit job cannot be delivered"}
                    )
                if (
                    int(row["operator_user_id"] or 0) > 0
                    and int(row["operator_user_id"]) != operator_user_id
                ):
                    return self._rollback_result(
                        {
                            "error": (
                                "video edit job is assigned to another developer"
                            )
                        }
                    )

                publish_plan_id = int(row["publish_plan_id"])
                publish_item_id = int(row["publish_item_id"])
                if previous_status == STATUS_DELIVERED and publish_item_id > 0:
                    cursor.execute(
                        """
                        select status
                        from matrix_publish_item
                        where id = %s
                        for update
                        """,
                        (publish_item_id,),
                    )
                    publish_item = cursor.fetchone()
                    if publish_item is not None and int(publish_item["status"]) > 2:
                        return self._rollback_result(
                            {"error": "publishing has started; delivery cannot be replaced"}
                        )
                has_publish_schedule = (
                    int(row["xhs_account_id"] or 0) > 0
                    and int(row["planned_publish_time"] or 0) > 0
                )
                if (
                    has_publish_schedule
                    and (publish_plan_id <= 0 or publish_item_id <= 0)
                ):
                    publish_plan_id, publish_item_id = self._create_publish_plan_locked(
                        cursor,
                        user_id=int(row["user_id"]),
                        job_id=job_id,
                        job_title=str(row["job_title"]),
                        post_title=str(row["post_title"]),
                        post_body=str(row["post_body"]),
                        post_tags=self._load_json_list(row["post_tag_json"]),
                        xhs_account_id=int(row["xhs_account_id"]),
                        planned_publish_time=int(row["planned_publish_time"]),
                        now=now,
                    )

                if publish_plan_id > 0 and publish_item_id > 0:
                    resolved_video_path = (
                        publish_video_path or payload.delivery_file_path
                    ).strip()
                    publish_material = {
                        "video_edit_job_id": job_id,
                        "video_path": resolved_video_path,
                        "delivery_file_name": payload.delivery_file_name,
                        "delivery_url": payload.delivery_url,
                        "awaiting_delivery": False,
                    }
                    publish_ready = str(row["review_status"]) == "confirmed"
                    cursor.execute(
                        """
                        update matrix_publish_item
                        set material_json = %s, scheduled_time = %s,
                            status = %s, last_error = '', update_time = %s
                        where id = %s and plan_id = %s
                        """,
                        (
                            self._dump_json(publish_material),
                            int(row["planned_publish_time"]),
                            2 if publish_ready else 1,
                            now,
                            publish_item_id,
                            publish_plan_id,
                        ),
                    )
                    cursor.execute(
                        """
                        update matrix_publish_plan
                        set status = %s, schedule_start_time = %s,
                            schedule_end_time = %s, update_time = %s
                        where id = %s
                        """,
                        (
                            3 if publish_ready else 2,
                            int(row["planned_publish_time"]),
                            int(row["planned_publish_time"]),
                            now,
                            publish_plan_id,
                        ),
                    )
                previous_delivery = self._load_json_dict(row["delivery_json"])
                previous_resources = previous_delivery.get("resources", [])
                resources = (
                    list(previous_resources)
                    if isinstance(previous_resources, list)
                    else []
                )
                previous_versions = previous_delivery.get("versions", [])
                versions = (
                    list(previous_versions)
                    if isinstance(previous_versions, list)
                    else []
                )
                if not versions and previous_delivery.get("delivery_file_path"):
                    versions.append(
                        {
                            "version": 1,
                            **{
                                key: previous_delivery.get(key)
                                for key in (
                                    "delivery_file_name",
                                    "delivery_file_path",
                                    "delivery_url",
                                    "note",
                                    "operator_user_id",
                                    "delivered_time",
                                )
                            },
                        }
                    )
                version = len(versions) + 1
                version_item = {
                    "version": version,
                    **delivery,
                    "publish_plan_id": publish_plan_id,
                    "publish_item_id": publish_item_id,
                }
                versions.append(version_item)
                delivery.update(
                    {
                        "version": version,
                        "versions": versions,
                        "resources": resources,
                        "publish_plan_id": publish_plan_id,
                        "publish_item_id": publish_item_id,
                    }
                )
                cursor.execute(
                    """
                    update video_edit_job
                    set status = %s, operator_user_id = %s,
                        developer_note = %s, delivery_json = %s,
                        publish_plan_id = %s, publish_item_id = %s,
                        delivered_time = %s, update_time = %s
                    where id = %s
                    """,
                    (
                        STATUS_DELIVERED,
                        operator_user_id,
                        payload.note,
                        self._dump_json(delivery),
                        publish_plan_id,
                        publish_item_id,
                        now,
                        now,
                        job_id,
                    ),
                )
                cursor.execute(
                    """
                    update video_edit_revision_request
                    set status = 'completed', update_time = %s
                    where job_id = %s and status = 'submitted'
                    """,
                    (now, job_id),
                )
            if previous_status != STATUS_DELIVERED:
                wallet = WalletRepository(self.conn)
                if not wallet.has_ledger_entry(
                    int(row["user_id"]),
                    "video_production",
                    job_id,
                ):
                    wallet.adjust_credits(
                        int(row["user_id"]),
                        -int(row["credit_cost"] or VIDEO_PRODUCTION_CREDIT_COST),
                        "video_production",
                        job_id,
                        "视频制作完成",
                        commit=False,
                    )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_for_developer(job_id)

    def add_delivery_resource(
        self,
        job_id: int,
        operator_user_id: int,
        *,
        resource_type: str,
        delivery_file_name: str,
        delivery_file_path: str,
        mime_type: str,
        file_size: int,
        note: str = "",
    ) -> dict | None:
        if resource_type not in {"voiceover", "subtitle"}:
            raise ValueError("unsupported delivery resource type")
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, status, review_status, operator_user_id, delivery_json
                    from video_edit_job
                    where id = %s
                    for update
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return self._rollback_result(None)
                if (
                    str(row["review_status"]) == "rejected"
                    or int(row["status"]) not in {STATUS_IN_PRODUCTION, STATUS_DELIVERED}
                ):
                    return self._rollback_result(
                        {"error": "video edit job cannot receive delivery resources"}
                    )
                assigned_user_id = int(row["operator_user_id"] or 0)
                if assigned_user_id > 0 and assigned_user_id != operator_user_id:
                    return self._rollback_result(
                        {"error": "video edit job is assigned to another developer"}
                    )

                delivery = self._load_json_dict(row["delivery_json"])
                existing_resources = delivery.get("resources", [])
                resources = (
                    list(existing_resources)
                    if isinstance(existing_resources, list)
                    else []
                )
                version = 1 + sum(
                    1
                    for item in resources
                    if isinstance(item, dict)
                    and item.get("resource_type") == resource_type
                )
                resources.append(
                    {
                        "resource_type": resource_type,
                        "version": version,
                        "delivery_file_name": delivery_file_name,
                        "delivery_file_path": delivery_file_path,
                        "mime_type": mime_type,
                        "file_size": int(file_size),
                        "note": note,
                        "operator_user_id": operator_user_id,
                        "delivered_time": now,
                    }
                )
                delivery["resources"] = resources
                cursor.execute(
                    """
                    update video_edit_job
                    set operator_user_id = %s, developer_note = %s,
                        delivery_json = %s, update_time = %s
                    where id = %s
                    """,
                    (
                        operator_user_id,
                        note,
                        self._dump_json(delivery),
                        now,
                        job_id,
                    ),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_for_developer(job_id)

    @staticmethod
    def _select_sql() -> str:
        return """
            select
                j.id,
                owner.tenant_id,
                coalesce(
                    nullif(tenant.tenant_name, ''),
                    concat('团队 #', owner.tenant_id)
                ) tenant_name,
                j.user_id,
                owner.login_name user_login_name,
                owner.nickname user_nickname,
                j.job_title,
                j.post_title,
                j.post_body,
                j.post_tag_json,
                j.review_status,
                j.script_text,
                j.requirement_text,
                j.material_json,
                j.xhs_account_id,
                coalesce(account.display_name, '') xhs_account_name,
                j.planned_publish_time,
                j.creation_mode,
                j.request_snapshot_json,
                j.credit_cost,
                j.publish_plan_id,
                j.publish_item_id,
                j.status,
                j.expected_delivery_time,
                j.operator_user_id,
                coalesce(
                    nullif(operator.nickname, ''),
                    operator.login_name,
                    ''
                ) operator_name,
                j.developer_note,
                j.delivery_json,
                (
                    select count(*)
                    from video_edit_revision_request revision_count_row
                    where revision_count_row.job_id = j.id
                ) revision_count,
                coalesce((
                    select revision_latest.id
                    from video_edit_revision_request revision_latest
                    where revision_latest.job_id = j.id
                    order by revision_latest.revision_no desc
                    limit 1
                ), 0) latest_revision_request_id,
                coalesce((
                    select revision_latest.feedback
                    from video_edit_revision_request revision_latest
                    where revision_latest.job_id = j.id
                    order by revision_latest.revision_no desc
                    limit 1
                ), '') latest_revision_feedback,
                coalesce((
                    select revision_latest.status
                    from video_edit_revision_request revision_latest
                    where revision_latest.job_id = j.id
                    order by revision_latest.revision_no desc
                    limit 1
                ), '') latest_revision_status,
                j.delivered_time,
                j.create_time,
                j.update_time
            from video_edit_job j
            join app_user owner on owner.id = j.user_id
            left join tenant tenant on tenant.id = owner.tenant_id
            left join xhs_account account on account.id = j.xhs_account_id
            left join app_user operator on operator.id = j.operator_user_id
            """

    def _row_to_job(self, row: dict) -> dict:
        persisted_status = int(row["status"])
        status = (
            STATUS_RETURNED
            if persisted_status == STATUS_RETURNED or row["review_status"] == "rejected"
            else persisted_status
        )
        now = int(time.time())
        expected_delivery_time = int(row["expected_delivery_time"])
        seconds_to_delivery = expected_delivery_time - now
        if status == STATUS_DELIVERED:
            sla_status = "completed"
        elif status == STATUS_RETURNED:
            sla_status = "returned"
        elif seconds_to_delivery < 0:
            sla_status = "overdue"
        elif seconds_to_delivery <= 3 * 60 * 60:
            sla_status = "due_soon"
        else:
            sla_status = "normal"
        delivery = self._load_json_dict(row["delivery_json"])
        delivery_versions = delivery.get("versions", [])
        if not isinstance(delivery_versions, list):
            delivery_versions = []
        if not delivery_versions and delivery.get("delivery_file_path"):
            delivery_versions = [
                {
                    "version": 1,
                    **{
                        key: delivery.get(key)
                        for key in (
                            "delivery_file_name",
                            "delivery_file_path",
                            "delivery_url",
                            "note",
                            "operator_user_id",
                            "delivered_time",
                        )
                    },
                }
            ]
        delivery_versions = [
            {
                **item,
                "resource_type": "video",
                "mime_type": (
                    "video/quicktime"
                    if str(item.get("delivery_file_name", "")).lower().endswith(".mov")
                    else "video/mp4"
                ),
                "delivery_url": (
                    f"/api/video-edit/jobs/{int(row['id'])}/delivery/versions/"
                    f"{int(item.get('version', 0))}/content"
                ),
            }
            for item in delivery_versions
            if isinstance(item, dict) and int(item.get("version", 0)) > 0
        ]
        delivery_resources = delivery.get("resources", [])
        if not isinstance(delivery_resources, list):
            delivery_resources = []
        delivery_resources = [
            {
                **item,
                "delivery_url": (
                    f"/api/video-edit/jobs/{int(row['id'])}/delivery/resources/"
                    f"{item.get('resource_type')}/{int(item.get('version', 0))}/content"
                ),
            }
            for item in delivery_resources
            if isinstance(item, dict)
            and item.get("resource_type") in {"voiceover", "subtitle"}
            and int(item.get("version", 0)) > 0
        ]
        delivery_assets = [*delivery_versions, *delivery_resources]
        delivery_resource_counts = {
            resource_type: sum(
                1
                for item in delivery_assets
                if item.get("resource_type") == resource_type
            )
            for resource_type in ("video", "voiceover", "subtitle")
        }
        creation_mode = self._normalize_creation_mode(row.get("creation_mode"))
        current_materials = self._load_json_list(row["material_json"])
        saved_request_snapshot = self._load_json_dict(
            row.get("request_snapshot_json", "")
        )
        request_snapshot = {
            "job_title": row["job_title"],
            "post_title": row["post_title"],
            "post_body": row["post_body"],
            "post_tags": self._load_json_list(row["post_tag_json"]),
            "script_text": row["script_text"],
            "requirement_text": row["requirement_text"],
            "materials": current_materials,
            "xhs_account_id": int(row["xhs_account_id"]),
            "xhs_account_name": row["xhs_account_name"],
            "planned_publish_time": int(row["planned_publish_time"]),
            "creation_mode": creation_mode,
            "creation_mode_label": VIDEO_CREATION_MODE_LABELS[creation_mode],
            "credit_cost": int(row["credit_cost"]),
            "submitted_at": int(row["create_time"]),
            **saved_request_snapshot,
        }
        # Some legacy rows persisted a partial request snapshot with an
        # explicit empty materials list.  That empty value must not hide the
        # real immutable materials still stored on the job row.
        saved_materials = request_snapshot.get("materials")
        if (
            (not isinstance(saved_materials, list) or not saved_materials)
            and current_materials
        ):
            request_snapshot["materials"] = current_materials
        return {
            "id": row["id"],
            "tenant_id": int(row["tenant_id"]),
            "tenant_name": row["tenant_name"],
            "user_id": row["user_id"],
            "user_login_name": row["user_login_name"],
            "user_nickname": row["user_nickname"],
            "job_title": row["job_title"],
            "post_title": row["post_title"],
            "post_body": row["post_body"],
            "post_tags": self._load_json_list(row["post_tag_json"]),
            "review_status": row["review_status"],
            "script_text": row["script_text"],
            "requirement_text": row["requirement_text"],
            "materials": self._load_json_list(row["material_json"]),
            "xhs_account_id": int(row["xhs_account_id"]),
            "xhs_account_name": row["xhs_account_name"],
            "planned_publish_time": int(row["planned_publish_time"]),
            "creation_mode": creation_mode,
            "creation_mode_label": VIDEO_CREATION_MODE_LABELS[creation_mode],
            "request_snapshot": request_snapshot,
            "credit_cost": int(row["credit_cost"]),
            "publish_credit_cost": (
                SCHEDULED_PUBLISH_CREDIT_COST if int(row["publish_item_id"]) > 0 else 0
            ),
            "total_credit_cost": (
                int(row["credit_cost"])
                + (SCHEDULED_PUBLISH_CREDIT_COST if int(row["publish_item_id"]) > 0 else 0)
            ),
            "publish_plan_id": int(row["publish_plan_id"]),
            "publish_item_id": int(row["publish_item_id"]),
            "status": status,
            "status_name": STATUS_NAMES.get(status, "submitted"),
            "status_text": STATUS_TEXT.get(status, "视频待生成"),
            "user_progress_text": USER_PROGRESS_TEXT.get(
                status,
                "视频制作需求已进入处理流程",
            ),
            "expected_delivery_time": expected_delivery_time,
            "sla_status": sla_status,
            "seconds_to_delivery": seconds_to_delivery,
            "operator_user_id": row["operator_user_id"],
            "operator_name": row["operator_name"],
            "developer_note": row["developer_note"],
            "delivery": delivery,
            "delivery_version_count": len(delivery_versions),
            "delivery_versions": delivery_versions,
            "delivery_assets": delivery_assets,
            "delivery_resource_counts": delivery_resource_counts,
            "revision_count": int(row.get("revision_count") or 0),
            "latest_revision_request_id": int(
                row.get("latest_revision_request_id") or 0
            ),
            "latest_revision_feedback": str(
                row.get("latest_revision_feedback") or ""
            ),
            "latest_revision_status": str(
                row.get("latest_revision_status") or ""
            ),
            "delivered_time": row["delivered_time"],
            "create_time": row["create_time"],
            "update_time": row["update_time"],
        }

    def _create_publish_plan_locked(
        self,
        cursor,
        *,
        user_id: int,
        job_id: int,
        job_title: str,
        post_title: str,
        post_body: str,
        post_tags: list[str],
        xhs_account_id: int,
        planned_publish_time: int,
        now: int,
    ) -> tuple[int, int]:
        scheduling_rule = {
            "source": "video_edit_job",
            "video_edit_job_id": job_id,
            "xhs_account_ids": [xhs_account_id],
            "items_per_account": 1,
        }
        cursor.execute(
            """
            insert into matrix_publish_plan (
                user_id, plan_name, source_type, content_type, product_id,
                status, schedule_start_time, schedule_end_time,
                scheduling_rule_json, create_time, update_time
            )
            values (%s, %s, 'video_edit_job', 'video', 0, 2, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                f"{job_title} 发布计划",
                planned_publish_time,
                planned_publish_time,
                self._dump_json(scheduling_rule),
                now,
                now,
            ),
        )
        plan_id = int(cursor.lastrowid)
        material = {
            "video_edit_job_id": job_id,
            "video_path": "",
            "awaiting_delivery": True,
        }
        cursor.execute(
            """
            insert into matrix_publish_item (
                plan_id, user_id, xhs_account_id, content_type,
                title, body, tag_json, material_json, scheduled_time,
                status, last_error, create_time, update_time
            )
            values (%s, %s, %s, 'video', %s, %s, %s, %s, %s, 1, '', %s, %s)
            """,
            (
                plan_id,
                user_id,
                xhs_account_id,
                post_title[:20],
                post_body,
                self._dump_json(post_tags),
                self._dump_json(material),
                planned_publish_time,
                now,
                now,
            ),
        )
        return plan_id, int(cursor.lastrowid)

    @staticmethod
    def _normalize_creation_mode(raw_mode: Any) -> str:
        mode = str(raw_mode or "standard").strip().lower()
        return mode if mode in VIDEO_CREATION_CREDIT_COSTS else "standard"

    @staticmethod
    def _dump_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _load_json_dict(raw_value: str) -> dict:
        if not raw_value:
            return {}
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _load_json_list(raw_value: str) -> list:
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
