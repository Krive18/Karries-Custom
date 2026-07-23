import os
from collections.abc import Iterable

from app.integrations.deepseek import DeepSeekTextClient, TextGenerationResult
from app.repositories.setting_repository import SettingRepository
from app.services.ai_settings_service import get_ai_setting_key, get_ai_settings_view


class AIProviderError(Exception):
    pass


class AIProviderService:
    def __init__(self, settings_repo: SettingRepository, transport=None) -> None:
        self.settings_repo = settings_repo
        self.transport = transport

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Iterable[tuple[str, str]] = (),
        temperature: float = 0.7,
    ) -> TextGenerationResult:
        settings = get_ai_settings_view(self.settings_repo).copywriting
        if not settings.enabled:
            raise AIProviderError("AI 服务未启用")

        api_key = get_ai_setting_key(self.settings_repo, "copywriting") or os.getenv(
            "DEEPSEEK_API_KEY", ""
        )
        if not api_key:
            raise AIProviderError("AI 服务尚未配置")

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(
            {"role": role, "content": content} for role, content in history
        )
        messages.append({"role": "user", "content": user_prompt})
        client = DeepSeekTextClient(
            api_key=api_key,
            base_url=settings.base_url,
            model=settings.model,
            transport=self.transport,
        )
        try:
            return client.generate(messages, temperature)
        except (KeyError, IndexError, TypeError, ValueError):
            raise AIProviderError("AI 服务响应无效") from None
        except Exception:
            raise AIProviderError("AI 服务调用失败") from None
