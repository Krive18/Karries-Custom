import json
import re

from pydantic import ValidationError

from app.repositories.ai_usage_repository import AIUsageRepository
from app.repositories.content_draft_repository import ContentDraftRepository
from app.repositories.setting_repository import SettingRepository
from app.repositories.viral_analysis_repository import ViralAnalysisRepository
from app.schemas.viral_analysis import (
    ViralAnalysisJobCreate,
    ViralAnalysisStatus,
    ViralAnalysisStructuredResult,
)
from app.services.ai_provider_service import AIProviderError, AIProviderService
from app.services.ai_settings_service import get_ai_settings_view
from app.services.ai_usage_service import AIUsageService
from app.services.credit_charge_service import CreditChargeService


class ViralAnalysisCapabilityError(ValueError):
    @staticmethod
    def require_text_input(supplement_text: str) -> None:
        if not supplement_text.strip():
            raise ViralAnalysisCapabilityError(
                "supplement_text is required until a video vision provider is configured"
            )


class ViralAnalysisResponseError(ValueError):
    pass


class ViralAnalysisProviderError(RuntimeError):
    pass


class _SnapshotSettingRepository:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def get(self, key: str, default: str = "") -> str:
        return self.values.get(key, default)


class ViralAnalysisService:
    def __init__(self, conn) -> None:
        self.conn = conn
        self.repository = ViralAnalysisRepository(conn)

    def create_job(self, user: dict, payload: ViralAnalysisJobCreate) -> dict:
        return self._external_job(
            self.repository.create_job(user["tenant_id"], user["id"], payload)
        )

    def list_jobs(self, user: dict, page: int, page_size: int) -> dict:
        return self._external_list(
            self.repository.list_for_user(user["tenant_id"], user["id"], page, page_size)
        )

    def get_job(self, user: dict, job_id: int) -> dict | None:
        job = self.repository.get_for_user(user["tenant_id"], user["id"], job_id)
        return self._external_job(job) if job is not None else None

    def list_jobs_for_admin(
        self,
        user: dict,
        page: int,
        page_size: int,
        user_id: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        status: ViralAnalysisStatus | None = None,
        keyword: str | None = None,
    ) -> dict:
        return self._external_list(
            self.repository.list_for_admin(
                user["tenant_id"], page, page_size,
                user_id=user_id, start_time=start_time, end_time=end_time,
                status=status, keyword=keyword,
            )
        )

    def get_job_for_admin(self, user: dict, job_id: int) -> dict | None:
        job = self.repository.get_for_admin(user["tenant_id"], job_id)
        return self._external_job(job) if job is not None else None

    def list_jobs_for_developer(
        self,
        page: int,
        page_size: int,
        tenant_id: int | None = None,
        status: ViralAnalysisStatus | None = None,
    ) -> dict:
        return self.repository.list_for_developer(page, page_size, tenant_id, status)

    def get_job_for_developer(self, job_id: int) -> dict | None:
        job = self.repository.get_for_developer(job_id)
        if job is None:
            return None
        job["latest_ai_usage"] = AIUsageRepository(self.conn).get_latest_for_business(
            job["tenant_id"], "viral_analysis", job_id
        )
        return job

    def cancel_job(self, user: dict, job_id: int) -> dict:
        return self._external_job(
            self.repository.cancel_for_user(user["tenant_id"], user["id"], job_id)
        )

    def run_job(self, user: dict, job_id: int) -> dict:
        tenant_id, user_id = user["tenant_id"], user["id"]
        existing = self.repository.get_for_user(tenant_id, user_id, job_id)
        if existing is None:
            return None
        ViralAnalysisCapabilityError.require_text_input(existing["supplement_text"])

        job, token = self.repository.claim_for_run(tenant_id, user_id, job_id)
        try:
            settings, provider = self._provider_from_settings_snapshot()
            # Snapshot reads are committed before any provider HTTP happens.
            self.conn.commit()
        except Exception as exc:
            self.conn.rollback()
            try:
                self._finalize_failure(
                    tenant_id, user_id, job_id, token,
                    "deepseek", "", "AI provider configuration unavailable", "not_configured",
                )
            except Exception:
                # The API still returns a closed error while preserving the configuration cause.
                pass
            raise ViralAnalysisProviderError("AI provider configuration failed") from exc
        try:
            generated = provider.generate_text(
                system_prompt=self._system_prompt(job),
                user_prompt=job["supplement_text"],
                temperature=0.3,
            )
            structured = parse_structured_result(generated.content)
        except AIProviderError as exc:
            self._finalize_failure(
                tenant_id, user_id, job_id, token, settings.provider, settings.model,
                str(exc), exc.code,
            )
            raise ViralAnalysisProviderError from exc
        except ViralAnalysisResponseError:
            self._finalize_failure(
                tenant_id, user_id, job_id, token, settings.provider, settings.model,
                "AI provider returned invalid analysis result", "invalid_response",
            )
            raise

        try:
            credit_cost = CreditChargeService().estimate("viral_analysis")
            self.repository.finalize_success(
                tenant_id, user_id, job_id, token, structured,
                generated.provider, generated.model_name, credit_cost,
            )
            AIUsageService(AIUsageRepository(self.conn)).record_success(
                tenant_id=tenant_id,
                user_id=user_id,
                business_type="viral_analysis",
                business_id=job_id,
                result=generated,
                credit_cost=credit_cost,
                commit=False,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        completed = self.repository.get_for_user(tenant_id, user_id, job_id)
        return self._external_job(completed) if completed is not None else None

    def save_draft(self, user: dict, job_id: int) -> int | None:
        job = self.repository.get_for_user(user["tenant_id"], user["id"], job_id)
        if job is None or job["status"] != "completed" or job["result"] is None:
            return None
        result = job["result"]
        body = result["rewritten_script"] or result["script_breakdown"]
        return ContentDraftRepository(self.conn).create_from_ai_text(
            tenant_id=user["tenant_id"],
            user_id=user["id"],
            source_type="viral_analysis",
            source_id=job_id,
            title=job["title"],
            body=body,
            ai_provider=job["ai_provider"],
            model_name=job["ai_model"],
            context={"analysis_goal": job["analysis_goal"], "source_type": job["source_type"]},
            content_type="video",
            tags=result["tags"],
        )

    def _finalize_failure(
        self,
        tenant_id: int,
        user_id: int,
        job_id: int,
        token: str,
        provider: str,
        model_name: str,
        error_message: str,
        error_code: str,
    ) -> None:
        try:
            self.repository.finalize_failure(
                tenant_id, user_id, job_id, token, provider, model_name, error_message
            )
            AIUsageService(AIUsageRepository(self.conn)).record_failure(
                tenant_id=tenant_id,
                user_id=user_id,
                business_type="viral_analysis",
                business_id=job_id,
                provider=provider,
                model_name=model_name,
                error_message=error_message,
                error_code=error_code,
                commit=False,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _provider_from_settings_snapshot(self):
        settings_repo = SettingRepository(self.conn)
        settings = get_ai_settings_view(settings_repo).copywriting
        values = {
            "ai.copywriting.provider": settings.provider,
            "ai.copywriting.base_url": settings.base_url,
            "ai.copywriting.model": settings.model,
            "ai.copywriting.enabled": "true" if settings.enabled else "false",
            "ai.copywriting.api_key": settings_repo.get(
                "ai.copywriting.api_key"
            ),
        }
        return settings, AIProviderService(_SnapshotSettingRepository(values))

    def _system_prompt(self, job: dict) -> str:
        goals = ", ".join(job["analysis_goal"]) or "hook, structure, script, reuse"
        return (
            "You are a Xiaohongshu viral-video analysis assistant. "
            "Only analyze the user's supplied supplement text. Do not claim to see video frames. "
            f"Requested dimensions: {goals}. Return strict JSON only with keys "
            "hook_summary, structure_summary, shot_rhythm, script_breakdown, "
            "selling_points, reuse_suggestions, rewritten_script, tags."
        )

    def _external_list(self, page_data: dict) -> dict:
        return {**page_data, "items": [self._external_job(item) for item in page_data["items"]]}

    def _external_job(self, job: dict) -> dict:
        safe = dict(job)
        safe.pop("ai_provider", None)
        safe.pop("ai_model", None)
        safe.pop("error_message", None)
        return safe


def parse_structured_result(raw: str) -> ViralAnalysisStructuredResult:
    normalized = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", normalized, flags=re.DOTALL | re.IGNORECASE)
    if fenced is not None:
        normalized = fenced.group(1)
    try:
        value = json.loads(normalized)
        return ViralAnalysisStructuredResult.model_validate(value)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        raise ViralAnalysisResponseError("AI provider returned invalid analysis result") from exc
