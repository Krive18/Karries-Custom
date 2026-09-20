from io import BytesIO
from types import SimpleNamespace

from starlette.datastructures import Headers, UploadFile

from app.api import video_edit as video_edit_api
from app.repositories.video_edit_repository import VideoEditRepository
from app.schemas.video_edit import VideoEditPublishContentUpdate


MP4_BYTES = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64


class _BatchDeliveryRepository:
    def __init__(self) -> None:
        self.delivered_names: list[str] = []

    def get_owner_scope(self, _job_id: int) -> dict:
        return {"tenant_id": 7, "user_id": 9}

    def deliver_job(self, job_id: int, _developer_id: int, payload, **_kwargs) -> dict:
        self.delivered_names.append(payload.delivery_file_name)
        return {
            "id": job_id,
            "status": 3,
            "delivery_version_count": len(self.delivered_names),
        }


class _ReviewTransitionCursor:
    def __init__(self, connection) -> None:
        self.connection = connection
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, sql: str, params=()) -> None:
        normalized = " ".join(sql.split())
        self.connection.executions.append((normalized, params))
        if normalized.startswith("select id, status, review_status, publish_plan_id"):
            self.row = {
                "id": 31,
                "status": self.connection.job_status,
                "review_status": "draft",
                "publish_plan_id": 81,
                "publish_item_id": 91,
            }
        elif normalized.startswith("select status from matrix_publish_item"):
            self.row = {"status": 1}
        else:
            self.row = None

    def fetchone(self):
        return self.row


class _ReviewTransitionConnection:
    def __init__(self, job_status: int = 1) -> None:
        self.job_status = job_status
        self.executions: list[tuple[str, tuple]] = []
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return _ReviewTransitionCursor(self)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def _video_upload(name: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(MP4_BYTES),
        filename=name,
        headers=Headers({"content-type": "video/mp4"}),
    )


def test_batch_delivery_upload_persists_every_video(monkeypatch, tmp_path) -> None:
    repository = _BatchDeliveryRepository()
    monkeypatch.setattr(
        video_edit_api,
        "VideoEditRepository",
        lambda _conn: repository,
    )
    monkeypatch.setattr(video_edit_api, "_write_video_job_audit", lambda *_args: None)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(config=SimpleNamespace(data_dir=tmp_path)))
    )

    response = video_edit_api.upload_internal_video_edit_delivery(
        job_id=31,
        request=request,
        files=[_video_upload("first.mp4"), _video_upload("second.mp4")],
        file=None,
        note="batch delivery",
        developer={"id": 12},
        conn=object(),
    )

    assert response["success"] is True
    assert response["data"]["delivery_version_count"] == 2
    assert repository.delivered_names == ["first.mp4", "second.mp4"]


def test_rejecting_an_unclaimed_video_job_cancels_all_pending_queues(monkeypatch) -> None:
    connection = _ReviewTransitionConnection()
    repository = VideoEditRepository(connection)
    monkeypatch.setattr(
        repository,
        "get_for_user",
        lambda _user_id, _job_id: {"id": 31, "status": 5},
    )

    repository.update_publish_content(
        user_id=9,
        job_id=31,
        payload=VideoEditPublishContentUpdate(
            post_title="待取消的视频任务",
            post_body="",
            post_tags=[],
            review_status="rejected",
        ),
    )

    job_update = next(
        params for sql, params in connection.executions
        if sql.startswith("update video_edit_job")
    )
    publish_item_update = next(
        params for sql, params in connection.executions
        if sql.startswith("update matrix_publish_item")
    )
    publish_plan_update = next(
        params for sql, params in connection.executions
        if sql.startswith("update matrix_publish_plan")
    )

    assert job_update[4] == 5
    assert publish_item_update[3] == 7
    assert publish_plan_update[0] == 7
    assert connection.committed is True


def test_rejecting_a_delivered_video_job_is_terminal_instead_of_rework(monkeypatch) -> None:
    connection = _ReviewTransitionConnection(job_status=3)
    repository = VideoEditRepository(connection)
    monkeypatch.setattr(
        repository,
        "get_for_user",
        lambda _user_id, _job_id: {"id": 31, "status": 5},
    )

    repository.update_publish_content(
        user_id=9,
        job_id=31,
        payload=VideoEditPublishContentUpdate(
            post_title="客户退回的视频任务",
            post_body="",
            post_tags=[],
            review_status="rejected",
        ),
    )

    job_update = next(
        params for sql, params in connection.executions
        if sql.startswith("update video_edit_job")
    )
    publish_item_update = next(
        params for sql, params in connection.executions
        if sql.startswith("update matrix_publish_item")
    )
    publish_plan_update = next(
        params for sql, params in connection.executions
        if sql.startswith("update matrix_publish_plan")
    )

    assert job_update[4] == 5
    assert publish_item_update[3] == 7
    assert publish_plan_update[0] == 7
    assert connection.committed is True


def test_legacy_revision_rows_are_read_as_returned_terminal_jobs() -> None:
    repository = VideoEditRepository(object())
    job = repository._row_to_job({
        "id": 31,
        "tenant_id": 7,
        "tenant_name": "测试团队",
        "user_id": 9,
        "user_login_name": "customer",
        "user_nickname": "客户",
        "job_title": "历史退回任务",
        "post_title": "",
        "post_body": "",
        "post_tag_json": "[]",
        "review_status": "rejected",
        "script_text": "",
        "requirement_text": "",
        "material_json": "[]",
        "xhs_account_id": 0,
        "xhs_account_name": "",
        "planned_publish_time": 0,
        "credit_cost": 140,
        "publish_plan_id": 81,
        "publish_item_id": 91,
        "status": 4,
        "expected_delivery_time": 1,
        "operator_user_id": 12,
        "operator_name": "原制作人员",
        "developer_note": "",
        "delivery_json": "{}",
        "delivered_time": 0,
        "create_time": 1,
        "update_time": 2,
    })

    assert job["status"] == 5
    assert job["status_name"] == "returned"
    assert job["status_text"] == "已退回"
    assert job["sla_status"] == "returned"
