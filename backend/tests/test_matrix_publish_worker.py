import asyncio
from unittest.mock import AsyncMock

from app.workers.matrix_publish_worker import MatrixPublishWorker


class FakeWorkerClient:
    def __init__(self, items: list[dict]):
        self.items = items
        self.success_calls: list[tuple[int, str, str]] = []
        self.failed_calls: list[tuple[int, str, str, bool, int]] = []
        self.manual_calls: list[tuple[int, str, str, bool, bool]] = []

    def claim(self, limit: int) -> list[dict]:
        return self.items[:limit]

    def mark_success(self, item_id: int, lease_token: str, message: str) -> dict:
        self.success_calls.append((item_id, lease_token, message))
        return {}

    def mark_failed(
        self,
        item_id: int,
        lease_token: str,
        error_message: str,
        retryable: bool = False,
        retry_delay_seconds: int = 60,
    ) -> dict:
        self.failed_calls.append(
            (item_id, lease_token, error_message, retryable, retry_delay_seconds)
        )
        return {"retry_scheduled": retryable}

    def mark_manual_takeover(
        self,
        item_id: int,
        lease_token: str,
        reason: str,
        invalidate_account_login: bool = False,
        mark_account_risk: bool = False,
    ) -> dict:
        self.manual_calls.append(
            (
                item_id,
                lease_token,
                reason,
                invalidate_account_login,
                mark_account_risk,
            )
        )
        return {}


def worker_item(cookie_path: str, image_path: str) -> dict:
    return {
        "id": 101,
        "plan_id": 77,
        "user_id": 9,
        "xhs_account_id": 27,
        "lease_token": "lease-token-101",
        "login_state_path": cookie_path,
        "content_type": "image_text",
        "title": "新品种草",
        "body": "自然真实的小红书正文",
        "tags": ["新品", "种草"],
        "material": {"image_paths": [image_path]},
        "scheduled_time": 1_782_570_600,
    }


def test_matrix_worker_publishes_due_item_and_marks_success(tmp_path):
    cookie_path = tmp_path / "account.json"
    image_path = tmp_path / "look.png"
    cookie_path.write_text("{}", encoding="utf-8")
    image_path.write_bytes(b"image")
    client = FakeWorkerClient([worker_item(str(cookie_path), str(image_path))])
    cookie_checker = AsyncMock(return_value=True)
    publisher = AsyncMock(return_value=None)
    worker = MatrixPublishWorker(
        client,
        headless=True,
        cookie_checker=cookie_checker,
        publisher=publisher,
    )

    result = asyncio.run(worker.run_once())

    assert result == {
        "claimed": 1,
        "success": 1,
        "failed": 0,
        "retried": 0,
        "manual": 0,
    }
    cookie_checker.assert_awaited_once_with(str(cookie_path))
    publisher.assert_awaited_once()
    payload = publisher.await_args.args[0]
    assert payload.publish_strategy == "immediate"
    assert payload.headless is True
    assert payload.image_paths == [str(image_path)]
    assert client.success_calls == [
        (101, "lease-token-101", "已提交至小红书发布平台")
    ]


def test_matrix_worker_publishes_delivered_video_and_marks_success(tmp_path):
    cookie_path = tmp_path / "account.json"
    video_path = tmp_path / "final-cut.mp4"
    cookie_path.write_text("{}", encoding="utf-8")
    video_path.write_bytes(b"\x00\x00\x00\x18ftypisom")
    item = worker_item(str(cookie_path), str(tmp_path / "unused.png"))
    item["content_type"] = "video"
    item["material"] = {"video_path": str(video_path)}
    client = FakeWorkerClient([item])
    note_publisher = AsyncMock(return_value=None)
    video_publisher = AsyncMock(return_value=None)
    worker = MatrixPublishWorker(
        client,
        headless=True,
        cookie_checker=AsyncMock(return_value=True),
        publisher=note_publisher,
        video_publisher=video_publisher,
    )

    result = asyncio.run(worker.run_once())

    assert result["success"] == 1
    note_publisher.assert_not_awaited()
    video_publisher.assert_awaited_once()
    payload = video_publisher.await_args.args[0]
    assert payload.video_path == str(video_path)
    assert payload.publish_strategy == "immediate"
    assert client.success_calls == [
        (101, "lease-token-101", "已提交至小红书发布平台")
    ]


def test_matrix_worker_marks_missing_material_for_manual_takeover(tmp_path):
    cookie_path = tmp_path / "account.json"
    cookie_path.write_text("{}", encoding="utf-8")
    item = worker_item(str(cookie_path), str(tmp_path / "missing.png"))
    client = FakeWorkerClient([item])
    publisher = AsyncMock(return_value=None)
    worker = MatrixPublishWorker(
        client,
        cookie_checker=AsyncMock(return_value=True),
        publisher=publisher,
    )

    result = asyncio.run(worker.run_once())

    assert result["manual"] == 1
    assert client.manual_calls[0][0] == 101
    assert client.manual_calls[0][1] == "lease-token-101"
    assert "发布图片不存在" in client.manual_calls[0][2]
    publisher.assert_not_awaited()


def test_matrix_worker_schedules_transient_publish_error_for_retry(tmp_path):
    cookie_path = tmp_path / "account.json"
    image_path = tmp_path / "look.png"
    cookie_path.write_text("{}", encoding="utf-8")
    image_path.write_bytes(b"image")
    client = FakeWorkerClient([worker_item(str(cookie_path), str(image_path))])
    publisher = AsyncMock(side_effect=RuntimeError("creator page unavailable"))
    worker = MatrixPublishWorker(
        client,
        cookie_checker=AsyncMock(return_value=True),
        publisher=publisher,
    )

    result = asyncio.run(worker.run_once())

    assert result["retried"] == 1
    assert result["failed"] == 0
    assert client.failed_calls[0][0] == 101
    assert client.failed_calls[0][1] == "lease-token-101"
    assert "creator page unavailable" in client.failed_calls[0][2]
    assert client.failed_calls[0][3] is True
    assert client.success_calls == []


def test_matrix_worker_marks_non_retryable_publish_error_as_failed(tmp_path):
    cookie_path = tmp_path / "account.json"
    image_path = tmp_path / "look.png"
    cookie_path.write_text("{}", encoding="utf-8")
    image_path.write_bytes(b"image")
    client = FakeWorkerClient([worker_item(str(cookie_path), str(image_path))])
    publisher = AsyncMock(side_effect=ValueError("invalid title"))
    worker = MatrixPublishWorker(
        client,
        cookie_checker=AsyncMock(return_value=True),
        publisher=publisher,
    )

    result = asyncio.run(worker.run_once())

    assert result["failed"] == 1
    assert result["retried"] == 0
    assert client.failed_calls[0][3] is False


def test_matrix_worker_marks_expired_login_for_reauthentication(tmp_path):
    cookie_path = tmp_path / "account.json"
    image_path = tmp_path / "look.png"
    cookie_path.write_text("{}", encoding="utf-8")
    image_path.write_bytes(b"image")
    client = FakeWorkerClient([worker_item(str(cookie_path), str(image_path))])
    publisher = AsyncMock(
        side_effect=RuntimeError(
            f"cookie文件已失效，请先完成小红书登录: {cookie_path}"
        )
    )
    worker = MatrixPublishWorker(
        client,
        cookie_checker=AsyncMock(return_value=True),
        publisher=publisher,
    )

    result = asyncio.run(worker.run_once())

    assert result["manual"] == 1
    assert result["failed"] == 0
    assert client.manual_calls == [
        (
            101,
            "lease-token-101",
            "小红书账号登录已失效，请到账号管理重新扫码登录",
            True,
            False,
        )
    ]
    assert client.failed_calls == []


def test_matrix_worker_invalidates_account_when_cookie_precheck_fails(tmp_path):
    cookie_path = tmp_path / "account.json"
    image_path = tmp_path / "look.png"
    cookie_path.write_text("{}", encoding="utf-8")
    image_path.write_bytes(b"image")
    client = FakeWorkerClient([worker_item(str(cookie_path), str(image_path))])
    publisher = AsyncMock(return_value=None)
    worker = MatrixPublishWorker(
        client,
        cookie_checker=AsyncMock(return_value=False),
        publisher=publisher,
    )

    result = asyncio.run(worker.run_once())

    assert result["manual"] == 1
    assert client.manual_calls == [
        (
            101,
            "lease-token-101",
            "小红书账号登录已失效，请重新扫码登录",
            True,
            False,
        )
    ]
    publisher.assert_not_awaited()


def test_matrix_worker_stops_account_when_platform_requires_security_verification(
    tmp_path,
):
    cookie_path = tmp_path / "account.json"
    image_path = tmp_path / "look.png"
    cookie_path.write_text("{}", encoding="utf-8")
    image_path.write_bytes(b"image")
    client = FakeWorkerClient([worker_item(str(cookie_path), str(image_path))])
    publisher = AsyncMock(side_effect=RuntimeError("操作频繁，请完成安全验证"))
    worker = MatrixPublishWorker(
        client,
        cookie_checker=AsyncMock(return_value=True),
        publisher=publisher,
    )

    result = asyncio.run(worker.run_once())

    assert result["manual"] == 1
    assert result["failed"] == 0
    assert result["retried"] == 0
    assert client.manual_calls == [
        (
            101,
            "lease-token-101",
            "小红书触发安全验证，已暂停该账号自动发布，请人工检查后恢复",
            False,
            True,
        )
    ]
    assert client.failed_calls == []
