import asyncio
import builtins
import sys
import threading
from types import SimpleNamespace

from app.cli import capture_feishu_open_id as capture_cli
from app.cli.capture_feishu_open_id import capture_once, create_channel, main
from app.integrations.feishu_open_id_capture import (
    FeishuAppCredentials,
    OneShotOpenIdCollector,
    build_capture_handler,
)


def _message(
    *,
    sender_id: str = "ou_coworker123",
    message_id: str = "om_message123",
    chat_type: str = "group",
):
    return SimpleNamespace(
        sender_id=sender_id,
        message_id=message_id,
        chat_type=chat_type,
        content_text="this must never be logged",
    )


def test_collector_captures_group_sender_open_id_once():
    collector = OneShotOpenIdCollector()

    captured = collector.capture(_message())

    assert captured is not None
    assert captured.open_id == "ou_coworker123"
    assert captured.message_id == "om_message123"
    assert captured.chat_type == "group"
    assert collector.capture(_message(message_id="om_second")) is None


def test_collector_ignores_direct_messages_and_invalid_sender_ids():
    collector = OneShotOpenIdCollector()

    assert collector.capture(_message(chat_type="p2p")) is None
    assert collector.capture(_message(sender_id="mobile-or-user-id")) is None
    assert collector.identity is None


def test_handler_outputs_only_open_id_without_stopping_channel_inside_callback():
    output = []
    captured = []

    class ReceiveOnlyChannel:
        def __init__(self):
            self.disconnect_calls = 0

        async def disconnect(self):
            self.disconnect_calls += 1

        async def send(self, *_args, **_kwargs):
            raise AssertionError("the one-shot capture tool must never send messages")

    channel = ReceiveOnlyChannel()
    handler = build_capture_handler(
        collector=OneShotOpenIdCollector(),
        output=output.append,
        on_capture=captured.append,
    )

    asyncio.run(handler(_message()))

    assert output == ["FEISHU_OPEN_ID=ou_coworker123"]
    assert [identity.open_id for identity in captured] == ["ou_coworker123"]
    assert channel.disconnect_calls == 0
    assert "this must never be logged" not in "".join(output)


def test_handler_ignores_non_group_message_without_output_or_disconnect():
    output = []

    class ReceiveOnlyChannel:
        disconnect_calls = 0

        async def disconnect(self):
            self.disconnect_calls += 1

    channel = ReceiveOnlyChannel()
    handler = build_capture_handler(
        collector=OneShotOpenIdCollector(),
        output=output.append,
    )

    asyncio.run(handler(_message(chat_type="p2p")))

    assert output == []
    assert channel.disconnect_calls == 0


def test_capture_controller_stops_only_after_message_handler_returns():
    class FakeChannel:
        def __init__(self):
            self.handler = None
            self.handler_running = False
            self.stop_calls = 0
            self.stopped = threading.Event()

        def on(self, event_name, handler):
            assert event_name == "message"
            self.handler = handler

        async def connect(self):
            self.handler_running = True
            await self.handler(_message())
            self.handler_running = False
            while not self.stopped.is_set():
                await asyncio.sleep(0)

        def stop(self):
            assert self.handler_running is False
            self.stop_calls += 1
            self.stopped.set()

    channel = FakeChannel()

    asyncio.run(capture_once(channel))

    assert channel.stop_calls == 1


def test_sdk_loop_cleanup_cancels_pending_tasks_and_closes_loop():
    sdk_loop = asyncio.new_event_loop()
    pending = sdk_loop.create_task(asyncio.sleep(3600))

    capture_cli._close_event_loop(sdk_loop)

    assert pending.cancelled()
    assert sdk_loop.is_closed()


def test_capture_cli_uses_critical_only_sdk_logging_and_never_prints_secret(
    monkeypatch,
    capsys,
):
    created = []

    class FakeChannel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.handler = None
            self.stop_calls = 0
            created.append(self)

        def on(self, event_name, handler):
            assert event_name == "message"
            self.handler = handler

        async def connect(self):
            await self.handler(_message())

        def stop(self):
            self.stop_calls += 1

    monkeypatch.setitem(
        sys.modules,
        "lark_channel",
        SimpleNamespace(
            FeishuChannel=FakeChannel,
            LogLevel=SimpleNamespace(CRITICAL="critical-only"),
        ),
    )

    channel = create_channel(
        FeishuAppCredentials(
            app_id="cli_test",
            app_secret="do-not-print-this-secret",
        )
    )
    asyncio.run(capture_once(channel))

    assert created[0].kwargs == {
        "app_id": "cli_test",
        "app_secret": "do-not-print-this-secret",
        "log_level": "critical-only",
    }
    output = capsys.readouterr().out
    assert "FEISHU_OPEN_ID=ou_coworker123" in output
    assert "do-not-print-this-secret" not in output


def test_main_imports_channel_sdk_before_starting_event_loop(monkeypatch):
    import_states = []
    original_import = builtins.__import__

    class FakeChannel:
        def __init__(self, **_kwargs):
            self.handler = None
            self.stop_calls = 0

        def on(self, _event_name, handler):
            self.handler = handler

        async def connect(self):
            await self.handler(_message())

        async def disconnect(self):
            return None

        def stop(self):
            self.stop_calls += 1

    def import_with_loop_probe(name, *args, **kwargs):
        if name == "lark_channel":
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                import_states.append("before-loop")
            else:
                import_states.append("inside-loop")
            return SimpleNamespace(
                FeishuChannel=FakeChannel,
                LogLevel=SimpleNamespace(CRITICAL="critical-only"),
            )
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_with_loop_probe)
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")

    assert main() == 0
    assert import_states == ["before-loop"]
