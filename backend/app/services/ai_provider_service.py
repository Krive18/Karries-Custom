import os
from collections.abc import Iterable

from app.integrations.deepseek import (
    DEEPSEEK_CHAT_COMPLETIONS_URL,
    DeepSeekTextClient,
    TextGenerationResult,
)
from app.repositories.setting_repository import SettingRepository
from app.services.ai_settings_service import get_ai_setting_key, get_ai_settings_view


class AIProviderError(Exception):
    CODES = frozenset(
        {
            "not_configured",
            "disabled",
            "timeout",
            "transport",
            "invalid_response",
        }
    )

    def __init__(self, code: str, message: str) -> None:
        if code not in self.CODES:
            raise ValueError("unsupported AI provider error code")
        self.code = code
        super().__init__(message)


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
            raise AIProviderError("disabled", "AI 服务未启用")

        api_key = get_ai_setting_key(self.settings_repo, "copywriting") or os.getenv(
            "DEEPSEEK_API_KEY", ""
        )
        if not api_key:
            raise AIProviderError("not_configured", "AI 服务尚未配置")

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(
            {"role": role, "content": content} for role, content in history
        )
        messages.append({"role": "user", "content": user_prompt})
        client = DeepSeekTextClient(
            api_key=api_key,
            base_url=DEEPSEEK_CHAT_COMPLETIONS_URL,
            model=settings.model,
            transport=self.transport,
        )
        provider_error: AIProviderError | None = None
        try:
            return client.generate(messages, temperature)
        except (KeyError, IndexError, TypeError, ValueError):
            provider_error = AIProviderError("invalid_response", "AI 服务响应无效")
        except TimeoutError:
            provider_error = AIProviderError("timeout", "AI 服务调用失败")
        except Exception:
            provider_error = AIProviderError("transport", "AI 服务调用失败")

        if provider_error is not None:
            raise provider_error
        raise RuntimeError("unreachable AI provider state")
