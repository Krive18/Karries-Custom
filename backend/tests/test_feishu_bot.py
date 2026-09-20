import pytest

from app.integrations.feishu_bot import (
    FeishuBotNotifier,
    FeishuBotSettings,
    TaskCreatedNotification,
    generate_signature,
    send_task_created_notification,
)


def test_generate_signature_matches_feishu_hmac_sha256_reference():
    assert generate_signature("test-secret", 1_700_000_000) == (
        "mbm4Y4oluIPQ00qlBIhX8vAZ0EKv3nw0LuTb91jPL84="
    )


def test_enabled_settings_reject_non_feishu_webhook_hosts():
    settings = FeishuBotSettings(
        enabled=True,
        webhook_url="https://example.com/open-apis/bot/v2/hook/not-feishu",
        signing_secret="test-secret",
        mention_open_id="ou_target",
    )

    with pytest.raises(ValueError, match="official Feishu webhook"):
        settings.validate()


def test_enabled_settings_require_a_valid_target_open_id():
    missing_target = FeishuBotSettings(
        enabled=True,
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test-hook",
        signing_secret="test-secret",
    )
    invalid_target = FeishuBotSettings(
        enabled=True,
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test-hook",
        signing_secret="test-secret",
        mention_open_id='ou_bad\"><at user_id="all">',
    )

    with pytest.raises(ValueError, match="target OpenID"):
        missing_target.validate()
    with pytest.raises(ValueError, match="target OpenID"):
        invalid_target.validate()


def test_secrets_are_not_exposed_by_settings_repr():
    settings = FeishuBotSettings(
        enabled=True,
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test-hook",
        signing_secret="test-secret",
        mention_open_id="ou_private_target",
    )

    rendered = repr(settings)

    assert "test-hook" not in rendered
    assert "test-secret" not in rendered
    assert "ou_private_target" not in rendered


def test_notifier_sends_signed_plain_text_without_private_task_fields():
    calls = []

    class SuccessfulResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 0, "msg": "success"}

    def fake_post(url, *, json, timeout, allow_redirects):
        calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
                "allow_redirects": allow_redirects,
            }
        )
        return SuccessfulResponse()

    settings = FeishuBotSettings(
        enabled=True,
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test-hook",
        signing_secret="test-secret",
        mention_open_id="ou_target",
        mention_name="视频同事",
        timeout_seconds=4,
        max_attempts=2,
    )
    notification = TaskCreatedNotification.video(
        {
            "id": 42,
            "job_title": "新品视频任务",
            "creation_mode_label": "Pro 模式",
            "materials": [{"file_name": "private-video.mp4"}],
            "create_time": 1_700_000_000,
            "script_text": "不应该发到群里的完整脚本",
            "user_login_name": "private-user",
        }
    )
    notifier = FeishuBotNotifier(
        settings,
        post=fake_post,
        clock=lambda: 1_700_000_000,
        sleep=lambda _seconds: None,
    )

    assert notifier.send(notification) is True
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == settings.webhook_url
    assert call["timeout"] == 4
    assert call["allow_redirects"] is False
    assert call["json"]["timestamp"] == "1700000000"
    assert call["json"]["sign"] == generate_signature(
        "test-secret", 1_700_000_000
    )
    assert call["json"]["msg_type"] == "text"
    message = call["json"]["content"]["text"]
    assert message.startswith('<at user_id="ou_target">视频同事</at>\n')
    assert "KARRIES｜新视频创作任务" in message
    assert "任务类型：视频创作" in message
    assert "#42" in message
    assert "新品视频任务" in message
    assert "Pro 模式" in message
    assert "1 项" in message
    assert "完整脚本" not in message
    assert "private-user" not in message
    assert "private-video.mp4" not in message


def test_translation_notification_names_the_task_type_precisely():
    notification = TaskCreatedNotification.translation(
        {
            "id": 7,
            "source_language": "zh",
            "target_language": "en",
            "create_time": 1_700_000_000,
        }
    )

    message = notification.render_text()

    assert "KARRIES｜新AI智能翻译任务" in message
    assert "任务类型：AI 智能翻译" in message
    assert "翻译语言：zh → en" in message


def test_notifier_retries_transient_failures_without_raising_to_task_creation():
    attempts = []
    delays = []

    class FailedResponse:
        def raise_for_status(self):
            raise RuntimeError("temporary Feishu failure")

        def json(self):
            return {}

    def fake_post(*_args, **_kwargs):
        attempts.append(1)
        return FailedResponse()

    notifier = FeishuBotNotifier(
        FeishuBotSettings(
            enabled=True,
                webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test-hook",
                signing_secret="test-secret",
                mention_open_id="ou_target",
                max_attempts=3,
        ),
        post=fake_post,
        clock=lambda: 1_700_000_000,
        sleep=delays.append,
    )

    result = notifier.send(
        TaskCreatedNotification.translation(
            {
                "id": 7,
                "source_file_name": "source.mp4",
                "source_language": "zh",
                "target_language": "en",
                "create_time": 1_700_000_000,
            }
        )
    )

    assert result is False
    assert len(attempts) == 3
    assert delays == [0.25, 0.5]


def test_pytest_environment_never_sends_real_feishu_notifications(monkeypatch):
    monkeypatch.setenv("FEISHU_BOT_ENABLED", "1")
    monkeypatch.setenv(
        "FEISHU_BOT_WEBHOOK_URL",
        "https://open.feishu.cn/open-apis/bot/v2/hook/test-hook",
    )
    monkeypatch.setenv("FEISHU_BOT_SIGNING_SECRET", "test-secret")
    monkeypatch.setenv("FEISHU_BOT_MENTION_OPEN_ID", "ou_target")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_example.py::test_case (call)")
    send_calls = []
    monkeypatch.setattr(
        FeishuBotNotifier,
        "send",
        lambda *_args, **_kwargs: send_calls.append(1) or True,
    )

    result = send_task_created_notification(
        TaskCreatedNotification.translation(
            {
                "id": 7,
                "source_language": "zh",
                "target_language": "en",
                "create_time": 1_700_000_000,
            }
        )
    )

    assert result is False
    assert send_calls == []


def test_declared_test_environment_never_sends_real_feishu_notifications(
    monkeypatch,
):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("XHS_ENV", "test")
    monkeypatch.setenv("FEISHU_BOT_ENABLED", "1")
    monkeypatch.setenv(
        "FEISHU_BOT_WEBHOOK_URL",
        "https://open.feishu.cn/open-apis/bot/v2/hook/test-hook",
    )
    monkeypatch.setenv("FEISHU_BOT_SIGNING_SECRET", "test-secret")
    send_calls = []
    monkeypatch.setattr(
        FeishuBotNotifier,
        "send",
        lambda *_args, **_kwargs: send_calls.append(1) or True,
    )

    result = send_task_created_notification(
        TaskCreatedNotification.translation(
            {
                "id": 8,
                "source_language": "zh",
                "target_language": "en",
                "create_time": 1_700_000_000,
            }
        )
    )

    assert result is False
    assert send_calls == []


def test_production_environment_can_send_configured_notification(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("XHS_ENV", "production")
    monkeypatch.setenv("FEISHU_BOT_ENABLED", "1")
    monkeypatch.setenv(
        "FEISHU_BOT_WEBHOOK_URL",
        "https://open.feishu.cn/open-apis/bot/v2/hook/test-hook",
    )
    monkeypatch.setenv("FEISHU_BOT_SIGNING_SECRET", "test-secret")
    monkeypatch.setenv("FEISHU_BOT_MENTION_OPEN_ID", "ou_target")
    send_calls = []
    monkeypatch.setattr(
        FeishuBotNotifier,
        "send",
        lambda _self, notification: send_calls.append(notification) or True,
    )
    notification = TaskCreatedNotification.translation(
        {
            "id": 9,
            "source_language": "zh",
            "target_language": "en",
            "create_time": 1_700_000_000,
        }
    )

    result = send_task_created_notification(notification)

    assert result is True
    assert send_calls == [notification]


def test_notification_timestamp_includes_seconds():
    notification = TaskCreatedNotification.translation(
        {
            "id": 7,
            "source_language": "zh",
            "target_language": "en",
            "create_time": 1_700_000_000,
        }
    )

    assert "提交时间：2023-11-15 06:13:20" in notification.render_text()
