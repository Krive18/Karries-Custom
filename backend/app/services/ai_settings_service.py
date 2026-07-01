from app.repositories.setting_repository import SettingRepository
from app.schemas.settings import AISettingsView, AISettingView


DEFAULT_AI_SETTINGS = {
    "vision": {
        "provider": "doubao",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "model": "doubao-vision-pro",
        "enabled": "true",
    },
    "copywriting": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-chat",
        "enabled": "true",
    },
}


def setting_key(slot: str, field: str) -> str:
    return f"ai.{slot}.{field}"


def mask_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}********{value[-4:]}"


def get_ai_setting_key(repo: SettingRepository, slot: str) -> str:
    return repo.get(setting_key(slot, "api_key"))


def get_ai_settings_view(repo: SettingRepository) -> AISettingsView:
    return AISettingsView(
        vision=_slot_view(repo, "vision"),
        copywriting=_slot_view(repo, "copywriting"),
    )


def _slot_view(repo: SettingRepository, slot: str) -> AISettingView:
    defaults = DEFAULT_AI_SETTINGS[slot]
    api_key = get_ai_setting_key(repo, slot)
    return AISettingView(
        provider=repo.get(setting_key(slot, "provider"), defaults["provider"]),
        base_url=repo.get(setting_key(slot, "base_url"), defaults["base_url"]),
        model=repo.get(setting_key(slot, "model"), defaults["model"]),
        enabled=repo.get(setting_key(slot, "enabled"), defaults["enabled"]) == "true",
        has_key=bool(api_key),
        masked_key=mask_key(api_key),
    )
