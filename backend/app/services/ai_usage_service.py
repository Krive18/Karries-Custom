import re

from app.integrations.deepseek import TextGenerationResult
from app.repositories.ai_usage_repository import AIUsageRepository


class AIUsageService:
    def __init__(self, repository: AIUsageRepository) -> None:
        self.repository = repository

    def record_success(
        self,
        tenant_id: int,
        user_id: int,
        business_type: str,
        business_id: int,
        result: TextGenerationResult,
        credit_cost: int,
    ) -> int:
        return self.repository.create(
            tenant_id=tenant_id,
            user_id=user_id,
            business_type=business_type,
            business_id=business_id,
            provider=result.provider,
            model_name=result.model_name,
            status="success",
            credit_cost=credit_cost,
            latency_ms=result.latency_ms,
            input_chars=result.input_chars,
            output_chars=result.output_chars,
            error_message="",
        )

    def record_failure(
        self,
        tenant_id: int,
        user_id: int,
        business_type: str,
        business_id: int,
        provider: str,
        model_name: str,
        error_message: str,
        latency_ms: int = 0,
        input_chars: int = 0,
        error_code: str | None = None,
    ) -> int:
        return self.repository.create(
            tenant_id=tenant_id,
            user_id=user_id,
            business_type=business_type,
            business_id=business_id,
            provider=provider,
            model_name=model_name,
            status="failed",
            credit_cost=0,
            latency_ms=latency_ms,
            input_chars=input_chars,
            output_chars=0,
            error_message=_sanitize_error_message(error_message, error_code),
        )


ERROR_SUMMARIES = {
    "not_configured": "AI provider is not configured",
    "disabled": "AI provider is disabled",
    "timeout": "AI provider timeout",
    "transport": "AI provider transport failed",
    "invalid_response": "AI provider returned invalid response",
}


def _sanitize_error_message(error_message: str, error_code: str | None = None) -> str:
    if error_code in ERROR_SUMMARIES:
        return ERROR_SUMMARIES[error_code]

    normalized = re.sub(r"\s+", " ", str(error_message)).strip().lower()
    if "timeout" in normalized:
        return ERROR_SUMMARIES["timeout"]
    if "ai 服务尚未配置" in normalized:
        return ERROR_SUMMARIES["not_configured"]
    if "ai 服务未启用" in normalized:
        return ERROR_SUMMARIES["disabled"]
    if "ai 服务响应无效" in normalized:
        return ERROR_SUMMARIES["invalid_response"]
    return "AI provider request failed"
