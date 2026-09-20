import traceback

import pytest

from app.core.secret_cipher import encrypt_secret
from app.services import ai_settings_service
from app.services.ai_settings_service import AISettingConnectionError


class FakeSettingRepository:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=""):
        return self.values.get(key, default)


@pytest.mark.parametrize(
    "legacy_model",
    ["doubao-seed-2-0-lite-260428", "doubao-seed-2-1-pro"],
)
def test_pro_copywriting_legacy_model_uses_current_version(legacy_model):
    repo = FakeSettingRepository(
        {"ai.pro_copywriting.model": legacy_model}
    )

    settings = ai_settings_service.get_ai_settings_view(repo)

    assert settings.pro_copywriting.model == "doubao-seed-2-1-pro-260628"


def test_connection_error_does_not_retain_provider_secret(monkeypatch):
    class FailingDeepSeekClient:
        def __init__(self, **_kwargs):
            pass

        def generate(self, *_args, **_kwargs):
            raise RuntimeError("Authorization: Bearer provider-secret-value")

    monkeypatch.setattr(
        ai_settings_service,
        "DeepSeekTextClient",
        FailingDeepSeekClient,
    )
    repo = FakeSettingRepository(
        {
            "ai.copywriting.api_key": encrypt_secret("provider-secret-value"),
            "ai.copywriting.model": "deepseek-v4-flash",
        }
    )

    with pytest.raises(AISettingConnectionError) as exc_info:
        ai_settings_service.test_ai_setting_connection(repo, "copywriting")

    error = exc_info.value
    formatted = "".join(
        traceback.format_exception(exc_info.type, error, exc_info.tb)
    )
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "provider-secret-value" not in str(error)
    assert "provider-secret-value" not in formatted
