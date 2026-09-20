import logging

from app.core.secret_cipher import decrypt_secret
from app.integrations.deepseek import DeepSeekTextClient
from app.integrations.vision import OpenAICompatibleVisionClient
from app.repositories.setting_repository import SettingRepository
from app.schemas.settings import (
    AISettingConnectionTestResult,
    AISettingsView,
    AISettingView,
)


logger = logging.getLogger(__name__)


DEFAULT_AI_SETTINGS = {
    "vision": {
        "provider": "doubao",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3/responses",
        "model": "doubao-seed-2-0-lite-260428",
        "enabled": "true",
    },
    "copywriting": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-v4-flash",
        "enabled": "true",
    },
    "pro_copywriting": {
        "provider": "doubao",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3/responses",
        "model": "doubao-seed-2-1-pro-260628",
        "enabled": "true",
    },
}

LEGACY_DEEPSEEK_MODELS = {"deepseek-chat", "deepseek-reasoner"}
LEGACY_PRO_COPYWRITING_MODELS = {
    "doubao-seed-2-0-lite-260428",
    "doubao-seed-2-1-pro",
}


class AISettingKeyMissingError(ValueError):
    pass


class AISettingConnectionError(RuntimeError):
    pass


def setting_key(slot: str, field: str) -> str:
    return f"ai.{slot}.{field}"


def mask_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}********{value[-4:]}"


def get_ai_setting_key(repo: SettingRepository, slot: str) -> str:
    return decrypt_secret(repo.get(setting_key(slot, "api_key")))


def get_ai_settings_view(repo: SettingRepository) -> AISettingsView:
    return AISettingsView(
        vision=_slot_view(repo, "vision"),
        copywriting=_slot_view(repo, "copywriting"),
        pro_copywriting=_slot_view(repo, "pro_copywriting"),
    )


def test_ai_setting_connection(
    repo: SettingRepository,
    slot: str,
) -> AISettingConnectionTestResult:
    setting = _slot_view(repo, slot)
    api_key = get_ai_setting_key(repo, slot)
    if not api_key:
        raise AISettingKeyMissingError("AI provider key is not configured")

    connection_error: AISettingConnectionError | None = None
    result = None
    try:
        if slot == "copywriting":
            result = DeepSeekTextClient(
                api_key=api_key,
                base_url=setting.base_url,
                model=setting.model,
            ).generate(
                [{"role": "user", "content": "连接测试，请只回复 OK"}],
                temperature=0,
            )
        else:
            result = OpenAICompatibleVisionClient(
                setting=setting,
                api_key=api_key,
            ).test_connection()
    except Exception as exc:
        logger.warning(
            "AI provider connection test failed: slot=%r provider=%r model=%r error_type=%r",
            slot,
            setting.provider,
            setting.model,
            type(exc).__name__,
        )
        connection_error = AISettingConnectionError(
            "AI provider connection test failed"
        )

    if connection_error is not None:
        raise connection_error
    if result is None:
        raise RuntimeError("unreachable AI provider connection test state")

    logger.info(
        "AI provider connection test succeeded: slot=%r provider=%r model=%r latency_ms=%s request_id=%r",
        slot,
        result.provider,
        result.model_name,
        result.latency_ms,
        result.request_id,
    )
    return AISettingConnectionTestResult(
        slot=slot,
        provider=result.provider,
        model=result.model_name,
        request_id=result.request_id,
        latency_ms=result.latency_ms,
    )


def _slot_view(repo: SettingRepository, slot: str) -> AISettingView:
    defaults = DEFAULT_AI_SETTINGS[slot]
    api_key = get_ai_setting_key(repo, slot)
    model = repo.get(setting_key(slot, "model"), defaults["model"])
    if slot == "copywriting" and model in LEGACY_DEEPSEEK_MODELS:
        model = defaults["model"]
    if slot == "pro_copywriting" and model in LEGACY_PRO_COPYWRITING_MODELS:
        model = defaults["model"]
    return AISettingView(
        provider=defaults["provider"],
        base_url=defaults["base_url"],
        model=model,
        enabled=repo.get(setting_key(slot, "enabled"), defaults["enabled"]) == "true",
        has_key=bool(api_key),
        masked_key=mask_key(api_key),
    )
