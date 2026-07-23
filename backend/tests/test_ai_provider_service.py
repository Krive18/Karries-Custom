import traceback

import pytest

from app.integrations.deepseek import DeepSeekTextClient
from app.services.ai_provider_service import AIProviderError, AIProviderService


class FakeSettingRepository:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=""):
        return self.values.get(key, default)


def test_text_client_sends_openai_compatible_messages():
    calls = []

    def fake_transport(url, headers, payload, timeout):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return {"choices": [{"message": {"content": "reply"}}]}

    client = DeepSeekTextClient(api_key="sk-test", transport=fake_transport)

    result = client.generate(
        [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
        ],
        temperature=0.4,
    )

    assert result.content == "reply"
    assert result.provider == "deepseek"
    assert result.model_name == "deepseek-chat"
    assert result.input_chars == len("systemhello")
    assert result.output_chars == len("reply")
    assert calls[0]["payload"]["model"] == "deepseek-chat"
    assert calls[0]["payload"]["messages"][1]["content"] == "hello"
    assert calls[0]["payload"]["temperature"] == 0.4


def test_provider_uses_database_key_before_environment(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-environment")
    repo = FakeSettingRepository(
        {
            "ai.copywriting.api_key": "sk-database",
            "ai.copywriting.base_url": "https://deepseek.example/chat/completions",
            "ai.copywriting.model": "deepseek-reasoner",
        }
    )
    captured = {}

    def fake_transport(url, headers, payload, timeout):
        captured["url"] = url
        captured["authorization"] = headers["Authorization"]
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "configured reply"}}]}

    service = AIProviderService(repo, transport=fake_transport)

    result = service.generate_text("system", "user", history=(("assistant", "earlier"),))

    assert result.content == "configured reply"
    assert result.model_name == "deepseek-reasoner"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["authorization"] == "Bearer sk-database"
    assert captured["payload"]["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "assistant", "content": "earlier"},
        {"role": "user", "content": "user"},
    ]


def test_provider_rejects_missing_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    service = AIProviderService(FakeSettingRepository())

    with pytest.raises(AIProviderError, match="AI 服务尚未配置") as exc_info:
        service.generate_text("system", "user")

    assert exc_info.value.code == "not_configured"


def test_provider_error_rejects_unsupported_code():
    with pytest.raises(ValueError, match="unsupported AI provider error code"):
        AIProviderError("raw_provider_error", "unsafe message")


def test_provider_error_code_allowlist_is_immutable():
    with pytest.raises(AttributeError):
        AIProviderError.CODES.add("raw_provider_error")


def test_provider_rejects_disabled_copywriting_setting():
    service = AIProviderService(
        FakeSettingRepository(
            {
                "ai.copywriting.api_key": "sk-database",
                "ai.copywriting.enabled": "false",
            }
        )
    )

    with pytest.raises(AIProviderError, match="AI 服务未启用") as exc_info:
        service.generate_text("system", "user")

    assert exc_info.value.code == "disabled"


def test_provider_hides_key_when_transport_fails():
    def failing_transport(*_args):
        raise RuntimeError("HTTP 401 for sk-private-secret")

    service = AIProviderService(
        FakeSettingRepository({"ai.copywriting.api_key": "sk-private-secret"}),
        transport=failing_transport,
    )

    with pytest.raises(AIProviderError, match="AI 服务调用失败") as exc_info:
        service.generate_text("system", "user")

    assert "sk-private-secret" not in str(exc_info.value)
    assert exc_info.value.code == "transport"


def test_provider_hides_transport_secret_from_formatted_traceback():
    def failing_transport(*_args):
        raise RuntimeError("Authorization: Bearer custom-secret-value")

    service = AIProviderService(
        FakeSettingRepository({"ai.copywriting.api_key": "sk-private-secret"}),
        transport=failing_transport,
    )

    with pytest.raises(AIProviderError) as exc_info:
        service.generate_text("system", "user")

    formatted_traceback = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert str(exc_info.value) == "AI 服务调用失败"
    assert "custom-secret-value" not in formatted_traceback


def test_provider_detaches_transport_exception_context():
    def failing_transport(*_args):
        raise RuntimeError("Authorization: Bearer object-secret")

    service = AIProviderService(
        FakeSettingRepository({"ai.copywriting.api_key": "sk-private-secret"}),
        transport=failing_transport,
    )

    with pytest.raises(AIProviderError) as exc_info:
        service.generate_text("system", "user")

    error = exc_info.value
    formatted_traceback = "".join(
        traceback.format_exception(exc_info.type, error, exc_info.tb)
    )
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "object-secret" not in repr(error)
    assert "object-secret" not in str(error)
    assert "object-secret" not in formatted_traceback


def test_provider_rejects_invalid_response_without_leaking_key():
    service = AIProviderService(
        FakeSettingRepository({"ai.copywriting.api_key": "sk-private-secret"}),
        transport=lambda *_args: {"choices": []},
    )

    with pytest.raises(AIProviderError, match="AI 服务响应无效") as exc_info:
        service.generate_text("system", "user")

    assert "sk-private-secret" not in str(exc_info.value)
    assert exc_info.value.code == "invalid_response"


def test_provider_classifies_timeout_with_safe_code():
    def timeout_transport(*_args):
        raise TimeoutError("private upstream timeout")

    service = AIProviderService(
        FakeSettingRepository({"ai.copywriting.api_key": "sk-private-secret"}),
        transport=timeout_transport,
    )

    with pytest.raises(AIProviderError, match="AI 服务调用失败") as exc_info:
        service.generate_text("system", "user")

    assert exc_info.value.code == "timeout"
