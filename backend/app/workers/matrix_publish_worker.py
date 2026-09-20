import asyncio
import logging
import os
from pathlib import Path
import time
from typing import Awaitable, Callable

import requests

from app.integrations.xiaohongshu import (
    build_note_payload,
    build_video_payload,
    check_cookie,
    submit_note,
    submit_video,
)


logger = logging.getLogger(__name__)

LOGIN_STATE_ERROR_MARKERS = (
    "cookie文件已失效",
    "cookie文件不存在",
    "登录状态文件不存在",
    "账号登录已失效",
    "重新扫码登录",
    "login expired",
)

RETRYABLE_ERROR_MARKERS = (
    "timeout",
    "timed out",
    "connection",
    "temporarily unavailable",
    "page unavailable",
    "net::err",
    "target page",
    "browser has been closed",
    "connection closed",
)

SECURITY_CHALLENGE_ERROR_MARKERS = (
    "安全验证",
    "风险验证",
    "操作频繁",
    "访问频繁",
    "异常操作",
    "captcha",
    "security verification",
)


def is_login_state_error(message: str) -> bool:
    normalized = message.strip().lower()
    return any(marker.lower() in normalized for marker in LOGIN_STATE_ERROR_MARKERS)


def is_retryable_publish_error(exc: Exception) -> bool:
    if isinstance(
        exc,
        (
            TimeoutError,
            ConnectionError,
            requests.Timeout,
            requests.ConnectionError,
        ),
    ):
        return True
    normalized = str(exc).strip().lower()
    return any(marker in normalized for marker in RETRYABLE_ERROR_MARKERS)


def is_security_challenge_error(message: str) -> bool:
    normalized = message.strip().lower()
    return any(
        marker.lower() in normalized for marker in SECURITY_CHALLENGE_ERROR_MARKERS
    )


class MatrixWorkerApiClient:
    def __init__(self, base_url: str, worker_token: str, timeout_seconds: int = 30):
        self.base_url = base_url.rstrip("/")
        self.worker_token = worker_token
        self.timeout_seconds = timeout_seconds

    def claim(self, limit: int) -> list[dict]:
        data = self._request(
            "POST",
            "/api/worker/matrix-publish-items/claim",
            {"limit": limit},
        )
        return list(data.get("items") or [])

    def mark_success(self, item_id: int, lease_token: str, message: str) -> dict:
        return self._request(
            "POST",
            f"/api/worker/matrix-publish-items/{item_id}/success",
            {"lease_token": lease_token, "message": message},
        )

    def mark_failed(
        self,
        item_id: int,
        lease_token: str,
        error_message: str,
        retryable: bool = False,
        retry_delay_seconds: int = 60,
    ) -> dict:
        return self._request(
            "POST",
            f"/api/worker/matrix-publish-items/{item_id}/fail",
            {
                "lease_token": lease_token,
                "error_message": error_message[:1000],
                "retryable": retryable,
                "retry_delay_seconds": retry_delay_seconds,
            },
        )

    def mark_manual_takeover(
        self,
        item_id: int,
        lease_token: str,
        reason: str,
        invalidate_account_login: bool = False,
        mark_account_risk: bool = False,
    ) -> dict:
        return self._request(
            "POST",
            f"/api/worker/matrix-publish-items/{item_id}/manual-takeover",
            {
                "lease_token": lease_token,
                "reason": reason[:1000],
                "invalidate_account_login": invalidate_account_login,
                "mark_account_risk": mark_account_risk,
            },
        )

    def _request(self, method: str, path: str, payload: dict) -> dict:
        response = requests.request(
            method,
            f"{self.base_url}{path}",
            headers={"X-Worker-Token": self.worker_token},
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        if not body.get("success"):
            error = body.get("error") or {}
            raise RuntimeError(str(error.get("message") or "worker API request failed"))
        return dict(body.get("data") or {})


class MatrixPublishWorker:
    def __init__(
        self,
        client: MatrixWorkerApiClient,
        *,
        headless: bool = True,
        claim_limit: int = 3,
        cookie_checker: Callable[[str], Awaitable[bool]] = check_cookie,
        publisher: Callable[..., Awaitable[None]] = submit_note,
        video_publisher: Callable[..., Awaitable[None]] = submit_video,
    ):
        self.client = client
        self.headless = headless
        self.claim_limit = claim_limit
        self.cookie_checker = cookie_checker
        self.publisher = publisher
        self.video_publisher = video_publisher

    async def run_once(self) -> dict[str, int]:
        items = await asyncio.to_thread(self.client.claim, self.claim_limit)
        result = {
            "claimed": len(items),
            "success": 0,
            "failed": 0,
            "retried": 0,
            "manual": 0,
        }
        for item in items:
            outcome = await self._process_item(item)
            result[outcome] += 1
        return result

    async def run_forever(self, poll_interval_seconds: int = 10) -> None:
        while True:
            try:
                result = await self.run_once()
                if result["claimed"]:
                    logger.info("matrix publish worker result: %s", result)
            except Exception:
                logger.exception("matrix publish worker loop failed")
            await asyncio.sleep(max(poll_interval_seconds, 1))

    async def _process_item(self, item: dict) -> str:
        item_id = int(item["id"])
        lease_token = str(item["lease_token"])
        try:
            manual_reason = await self._validate_item(item)
        except Exception as exc:
            if is_login_state_error(str(exc)):
                await asyncio.to_thread(
                    self.client.mark_manual_takeover,
                    item_id,
                    lease_token,
                    "小红书账号登录已失效，请到账号管理重新扫码登录",
                    True,
                )
                return "manual"
            if is_security_challenge_error(str(exc)):
                return await self._mark_security_challenge(item)
            return await self._mark_publish_error(item, exc)

        if manual_reason:
            await asyncio.to_thread(
                self.client.mark_manual_takeover,
                item_id,
                lease_token,
                manual_reason,
                is_login_state_error(manual_reason),
            )
            return "manual"

        material = item.get("material") or {}
        if item.get("content_type") == "video":
            payload = build_video_payload(
                account_file=str(item["login_state_path"]),
                title=str(item["title"]),
                body=str(item["body"]),
                tags=[str(tag) for tag in item.get("tags") or []],
                video_path=str(material.get("video_path") or ""),
                schedule_time=int(time.time()),
                publish_strategy="immediate",
                headless=self.headless,
            )
            publish = self.video_publisher
        else:
            image_paths = [
                str(path) for path in material.get("image_paths") or []
            ]
            payload = build_note_payload(
                account_file=str(item["login_state_path"]),
                title=str(item["title"]),
                body=str(item["body"]),
                tags=[str(tag) for tag in item.get("tags") or []],
                image_paths=image_paths,
                schedule_time=int(time.time()),
                publish_strategy="immediate",
                headless=self.headless,
            )
            publish = self.publisher
        try:
            await publish(payload)
        except Exception as exc:
            if is_login_state_error(str(exc)):
                await asyncio.to_thread(
                    self.client.mark_manual_takeover,
                    item_id,
                    lease_token,
                    "小红书账号登录已失效，请到账号管理重新扫码登录",
                    True,
                )
                return "manual"
            if is_security_challenge_error(str(exc)):
                return await self._mark_security_challenge(item)
            return await self._mark_publish_error(item, exc)

        await asyncio.to_thread(
            self.client.mark_success,
            item_id,
            lease_token,
            "已提交至小红书发布平台",
        )
        return "success"

    async def _mark_security_challenge(self, item: dict) -> str:
        await asyncio.to_thread(
            self.client.mark_manual_takeover,
            int(item["id"]),
            str(item["lease_token"]),
            "小红书触发安全验证，已暂停该账号自动发布，请人工检查后恢复",
            False,
            True,
        )
        return "manual"

    async def _mark_publish_error(self, item: dict, exc: Exception) -> str:
        retryable = is_retryable_publish_error(exc)
        attempt_count = max(int(item.get("attempt_count") or 1), 1)
        retry_delay_seconds = min(60 * (2 ** (attempt_count - 1)), 600)
        result = await asyncio.to_thread(
            self.client.mark_failed,
            int(item["id"]),
            str(item["lease_token"]),
            f"{type(exc).__name__}: {exc}",
            retryable,
            retry_delay_seconds,
        )
        if result.get("retry_scheduled"):
            return "retried"
        return "failed"

    async def _validate_item(self, item: dict) -> str:
        if item.get("content_type") not in {"image_text", "video"}:
            return "当前发布执行器暂不支持该内容类型，请人工处理"

        login_state_path = str(item.get("login_state_path") or "").strip()
        if not login_state_path or not Path(login_state_path).is_file():
            return "小红书账号登录状态文件不存在，请重新扫码登录"
        try:
            login_valid = await self.cookie_checker(login_state_path)
        except Exception:
            raise
        if not login_valid:
            return "小红书账号登录已失效，请重新扫码登录"

        material = item.get("material") or {}
        if item.get("content_type") == "video":
            video_path = str(material.get("video_path") or "").strip()
            if not video_path:
                return "视频成片尚未生成，请等待成片回传"
            if not Path(video_path).is_file():
                return f"发布视频不存在：{Path(video_path).name}"
            return ""

        image_paths = [str(path) for path in material.get("image_paths") or []]
        if not image_paths:
            return "发布内容没有可用图片，请从产品知识库补充素材"
        missing_paths = [path for path in image_paths if not Path(path).is_file()]
        if missing_paths:
            return f"发布图片不存在：{Path(missing_paths[0]).name}"
        return ""


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    worker_token = os.environ.get("WORKER_API_TOKEN", "").strip()
    if not worker_token:
        raise RuntimeError("WORKER_API_TOKEN is required")

    base_url = os.environ.get("BACKEND_API_URL", "http://127.0.0.1:8765")
    headless = os.environ.get("XHS_WORKER_HEADLESS", "1").strip() != "0"
    poll_interval = int(os.environ.get("XHS_WORKER_POLL_SECONDS", "10"))
    claim_limit = int(os.environ.get("XHS_WORKER_CLAIM_LIMIT", "3"))
    worker = MatrixPublishWorker(
        MatrixWorkerApiClient(base_url, worker_token),
        headless=headless,
        claim_limit=claim_limit,
    )
    asyncio.run(worker.run_forever(poll_interval))


if __name__ == "__main__":
    main()
