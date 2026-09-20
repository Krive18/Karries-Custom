from __future__ import annotations

import asyncio
from contextlib import suppress

from app.integrations.feishu_open_id_capture import (
    FeishuAppCredentials,
    OneShotOpenIdCollector,
    build_capture_handler,
)


def create_channel(credentials: FeishuAppCredentials):
    from lark_channel import FeishuChannel, LogLevel

    return FeishuChannel(
        app_id=credentials.app_id,
        app_secret=credentials.app_secret,
        # The SDK currently logs an intentional WebSocket close as ERROR.
        # This CLI reports connection failures itself, so only surface truly
        # critical SDK logs and keep a successful one-shot capture clean.
        log_level=LogLevel.CRITICAL,
    )


async def capture_once(channel) -> None:
    controller_loop = asyncio.get_running_loop()
    captured = asyncio.Event()

    def capture_finished(_identity) -> None:
        controller_loop.call_soon_threadsafe(captured.set)

    channel.on(
        "message",
        build_capture_handler(
            collector=OneShotOpenIdCollector(),
            on_capture=capture_finished,
        ),
    )

    print("正在等待群聊中的新 @ 消息；本工具不会回复或发送任何消息。")
    print("请让同事发送：@KARRIES 通讯录助手 获取我的ID")
    connect_task = asyncio.create_task(channel.connect())
    capture_task = asyncio.create_task(captured.wait())
    try:
        done, _pending = await asyncio.wait(
            {connect_task, capture_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if capture_task in done:
            # Stop from the controller thread, after the SDK callback has
            # returned. Stopping inside the callback deadlocks the SDK's own
            # cleanup loop and leaves pending coroutines behind.
            await asyncio.to_thread(channel.stop)
            await connect_task
        else:
            await connect_task
            if not captured.is_set():
                raise RuntimeError("飞书连接在捕获 OpenID 前意外结束")
    finally:
        capture_task.cancel()
        with suppress(asyncio.CancelledError):
            await capture_task
        if not connect_task.done():
            await asyncio.to_thread(channel.stop)
            with suppress(asyncio.CancelledError, Exception):
                await connect_task


def _close_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Cancel and drain tasks left by the SDK's module-level WS loop."""
    if loop.is_closed() or loop.is_running():
        return
    pending = list(asyncio.all_tasks(loop))
    for task in pending:
        task.cancel()
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


def _close_channel_sdk_loop(channel) -> None:
    if channel is None or not type(channel).__module__.startswith("lark_channel."):
        return
    try:
        from lark_channel.ws import client as sdk_client
    except (ImportError, ModuleNotFoundError):
        return
    _close_event_loop(sdk_client.loop)


def main() -> int:
    channel = None
    try:
        credentials = FeishuAppCredentials.from_environment()
    except ValueError:
        print("缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET 环境变量。")
        return 2

    try:
        # lark-channel-sdk captures the current event loop while importing.
        # Build the channel before asyncio.run() so it does not cache a loop
        # that is already running and then call run_until_complete() on it.
        channel = create_channel(credentials)
        asyncio.run(capture_once(channel))
    except KeyboardInterrupt:
        print("已取消监听。")
        return 130
    except Exception as exc:
        print(f"飞书长连接失败（{type(exc).__name__}），请检查应用凭证和网络。")
        return 1
    finally:
        _close_channel_sdk_loop(channel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
