from __future__ import annotations

import base64
import hashlib
import hmac
import html
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Literal
from urllib.parse import urlsplit

import requests


logger = logging.getLogger(__name__)

FEISHU_WEBHOOK_HOST = "open.feishu.cn"
FEISHU_WEBHOOK_PATH_PREFIX = "/open-apis/bot/v2/hook/"
SHANGHAI_TIMEZONE = timezone(timedelta(hours=8))
FEISHU_OPEN_ID_PATTERN = re.compile(r"ou_[A-Za-z0-9_-]+")


@dataclass(frozen=True)
class FeishuBotSettings:
    enabled: bool = False
    webhook_url: str = field(default="", repr=False)
    signing_secret: str = field(default="", repr=False)
    mention_open_id: str = field(default="", repr=False)
    mention_name: str = "任务负责人"
    timeout_seconds: float = 5.0
    max_attempts: int = 3

    @classmethod
    def from_environment(cls) -> "FeishuBotSettings":
        return cls(
            enabled=_env_bool("FEISHU_BOT_ENABLED", False),
            webhook_url=os.environ.get("FEISHU_BOT_WEBHOOK_URL", "").strip(),
            signing_secret=os.environ.get(
                "FEISHU_BOT_SIGNING_SECRET", ""
            ).strip(),
            mention_open_id=os.environ.get(
                "FEISHU_BOT_MENTION_OPEN_ID", ""
            ).strip(),
            mention_name=os.environ.get(
                "FEISHU_BOT_MENTION_NAME", "任务负责人"
            ).strip()
            or "任务负责人",
            timeout_seconds=_bounded_float(
                "FEISHU_BOT_TIMEOUT_SECONDS", default=5.0, minimum=1.0, maximum=15.0
            ),
            max_attempts=_bounded_int(
                "FEISHU_BOT_MAX_ATTEMPTS", default=3, minimum=1, maximum=5
            ),
        )

    def validate(self) -> None:
        if not self.enabled:
            return
        if not self.webhook_url or not self.signing_secret:
            raise ValueError(
                "enabled Feishu bot requires both webhook URL and signing secret"
            )
        if not FEISHU_OPEN_ID_PATTERN.fullmatch(self.mention_open_id):
            raise ValueError(
                "enabled Feishu bot requires a valid target OpenID"
            )
        parsed = urlsplit(self.webhook_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != FEISHU_WEBHOOK_HOST
            or parsed.port not in (None, 443)
            or not parsed.path.startswith(FEISHU_WEBHOOK_PATH_PREFIX)
            or not parsed.path.removeprefix(FEISHU_WEBHOOK_PATH_PREFIX)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("webhook URL must be an official Feishu webhook")


@dataclass(frozen=True)
class TaskCreatedNotification:
    kind: Literal["video", "translation"]
    task_id: int
    title: str
    details: tuple[tuple[str, str], ...]
    created_at: int

    @classmethod
    def video(cls, job: dict) -> "TaskCreatedNotification":
        return cls(
            kind="video",
            task_id=int(job["id"]),
            title=_plain_text(job.get("job_title") or "视频创作任务", 120),
            details=(
                (
                    "创作模式",
                    _plain_text(job.get("creation_mode_label") or "标准模式", 40),
                ),
                ("制作素材", f"{len(job.get('materials') or [])} 项"),
            ),
            created_at=int(job.get("create_time") or time.time()),
        )

    @classmethod
    def translation(cls, task: dict) -> "TaskCreatedNotification":
        source_language = _plain_text(task.get("source_language") or "auto", 12)
        target_language = _plain_text(task.get("target_language") or "", 12)
        return cls(
            kind="translation",
            task_id=int(task["id"]),
            title="AI 翻译任务",
            details=(("翻译语言", f"{source_language} → {target_language}"),),
            created_at=int(task.get("create_time") or time.time()),
        )

    def render_text(self) -> str:
        kind_label = "视频创作" if self.kind == "video" else "AI 智能翻译"
        heading_label = "视频创作" if self.kind == "video" else "AI智能翻译"
        created_text = datetime.fromtimestamp(
            self.created_at,
            tz=SHANGHAI_TIMEZONE,
        ).strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"KARRIES｜新{heading_label}任务",
            f"任务类型：{kind_label}",
            f"任务编号：#{self.task_id}",
            f"任务标题：{self.title}",
        ]
        lines.extend(f"{label}：{value}" for label, value in self.details)
        lines.extend(
            [
                f"提交时间：{created_text}",
                "请进入 KARRIES 开发者工作台处理。",
            ]
        )
        return "\n".join(lines)


def generate_signature(signing_secret: str, timestamp: int | str) -> str:
    # Feishu custom-bot signing contract:
    # https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
    string_to_sign = f"{timestamp}\n{signing_secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


class FeishuBotNotifier:
    def __init__(
        self,
        settings: FeishuBotSettings,
        *,
        post: Callable = requests.post,
        clock: Callable[[], int | float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        settings.validate()
        self._settings = settings
        self._post = post
        self._clock = clock
        self._sleep = sleep

    def send(self, notification: TaskCreatedNotification) -> bool:
        if not self._settings.enabled:
            return False

        for attempt in range(1, self._settings.max_attempts + 1):
            timestamp = int(self._clock())
            payload = {
                "timestamp": str(timestamp),
                "sign": generate_signature(
                    self._settings.signing_secret,
                    timestamp,
                ),
                "msg_type": "text",
                "content": {
                    "text": _mention_text(self._settings)
                    + notification.render_text()
                },
            }
            try:
                response = self._post(
                    self._settings.webhook_url,
                    json=payload,
                    timeout=self._settings.timeout_seconds,
                    allow_redirects=False,
                )
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict) or _feishu_error_code(body) != 0:
                    raise ValueError("Feishu rejected the notification")
                logger.info(
                    "feishu_task_notification_sent; kind=%s; task_id=%s; attempt=%s",
                    notification.kind,
                    notification.task_id,
                    attempt,
                )
                return True
            except Exception as exc:
                logger.warning(
                    "feishu_task_notification_failed; attempt=%s/%s; error_type=%s",
                    attempt,
                    self._settings.max_attempts,
                    type(exc).__name__,
                )
                if attempt < self._settings.max_attempts:
                    self._sleep(0.25 * (2 ** (attempt - 1)))
        return False


def send_task_created_notification(notification: TaskCreatedNotification) -> bool:
    if _external_notifications_blocked_for_tests():
        logger.info(
            "feishu_task_notification_suppressed; reason=test_environment; kind=%s; task_id=%s",
            notification.kind,
            notification.task_id,
        )
        return False

    settings = FeishuBotSettings.from_environment()
    if not settings.enabled:
        return False
    try:
        return FeishuBotNotifier(settings).send(notification)
    except ValueError as exc:
        logger.warning(
            "feishu_task_notification_configuration_invalid; error_type=%s",
            type(exc).__name__,
        )
        return False


def _external_notifications_blocked_for_tests() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    environment = os.environ.get("XHS_ENV", os.environ.get("APP_ENV", ""))
    return environment.strip().lower() in {"test", "testing"}


def _feishu_error_code(body: dict) -> int:
    raw_code = body.get("code", body.get("StatusCode", -1))
    try:
        return int(raw_code)
    except (TypeError, ValueError):
        return -1


def _plain_text(value, limit: int) -> str:
    normalized = " ".join(str(value).split())
    if not normalized:
        return "-"
    return normalized[:limit]


def _mention_text(settings: FeishuBotSettings) -> str:
    display_name = html.escape(
        _plain_text(settings.mention_name or "任务负责人", 40),
        quote=False,
    )
    return (
        f'<at user_id="{settings.mention_open_id}">{display_name}</at>\n'
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _bounded_int(name: str, *, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return min(max(value, minimum), maximum)


def _bounded_float(
    name: str,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return min(max(value, minimum), maximum)
