from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from threading import Lock
from typing import Awaitable, Callable


@dataclass(frozen=True)
class FeishuIdentity:
    open_id: str
    message_id: str
    chat_type: str


@dataclass(frozen=True, repr=False)
class FeishuAppCredentials:
    app_id: str
    app_secret: str

    @classmethod
    def from_environment(cls) -> "FeishuAppCredentials":
        app_id = (
            os.environ.get("FEISHU_APP_ID")
            or os.environ.get("LARK_APP_ID")
            or ""
        ).strip()
        app_secret = (
            os.environ.get("FEISHU_APP_SECRET")
            or os.environ.get("LARK_APP_SECRET")
            or ""
        ).strip()
        if not app_id or not app_secret:
            raise ValueError(
                "missing FEISHU_APP_ID/FEISHU_APP_SECRET environment variables"
            )
        return cls(app_id=app_id, app_secret=app_secret)


class OneShotOpenIdCollector:
    """Accept the first valid group sender without retaining message content."""

    def __init__(self) -> None:
        self._identity: FeishuIdentity | None = None
        self._lock = Lock()

    @property
    def identity(self) -> FeishuIdentity | None:
        return self._identity

    def capture(self, message) -> FeishuIdentity | None:
        chat_type = str(getattr(message, "chat_type", "") or "").strip()
        sender_id = str(getattr(message, "sender_id", "") or "").strip()
        message_id = str(
            getattr(message, "message_id", "")
            or getattr(message, "id", "")
            or ""
        ).strip()

        if chat_type != "group" or not sender_id.startswith("ou_"):
            return None

        candidate = FeishuIdentity(
            open_id=sender_id,
            message_id=message_id,
            chat_type=chat_type,
        )
        with self._lock:
            if self._identity is not None:
                return None
            self._identity = candidate
            return candidate


def build_capture_handler(
    *,
    collector: OneShotOpenIdCollector | None = None,
    output: Callable[[str], None] = print,
    on_capture: Callable[[FeishuIdentity], None] | None = None,
) -> Callable[[object], Awaitable[None]]:
    one_shot_collector = collector or OneShotOpenIdCollector()

    async def on_message(message: object) -> None:
        identity = one_shot_collector.capture(message)
        if identity is None:
            return
        output(f"FEISHU_OPEN_ID={identity.open_id}")
        if on_capture is not None:
            # Run the notification on the next loop turn. This lets the
            # message callback return before the controller starts stopping
            # SDK-owned loops and background tasks.
            asyncio.get_running_loop().call_soon(on_capture, identity)

    return on_message
