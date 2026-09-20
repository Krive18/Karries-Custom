import json
import logging
import re
from pathlib import Path
from time import perf_counter

from pydantic import ValidationError

from app.integrations.deepseek import TextGenerationResult
from app.integrations.media_transcode import prepared_media_path
from app.integrations.vision import OpenAICompatibleVisionClient, VisionProviderError
from app.repositories.ai_usage_repository import AIUsageRepository
from app.repositories.setting_repository import SettingRepository
from app.repositories.viral_analysis_repository import ViralAnalysisRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.viral_analysis import (
    ViralAnalysisJobCreate,
    ViralAnalysisStatus,
    ViralAnalysisStructuredResult,
    ViralAnalysisTranscriptResult,
)
from app.services.ai_provider_service import AIProviderError, AIProviderService
from app.services.ai_settings_service import get_ai_setting_key, get_ai_settings_view
from app.services.ai_usage_service import AIUsageService
from app.services.credit_charge_service import CreditChargeService
from app.services.remote_media_service import RemoteMediaError, RemoteMediaService


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


class ViralAnalysisCreditError(ValueError):
    pass


logger = logging.getLogger(__name__)


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

    def run_job(
        self,
        user: dict,
        job_id: int,
        upload_root: Path | None = None,
        request_id: str = "",
    ) -> dict:
        tenant_id, user_id = user["tenant_id"], user["id"]
        existing = self.repository.get_for_user(tenant_id, user_id, job_id)
        if existing is None:
            return None
        use_uploaded_media = (
            existing["source_type"] == "upload"
            and bool(existing["materials"])
        )
        source_url = str(existing.get("source_url") or "").strip()
        use_linked_media = existing["source_type"] == "link" and bool(source_url)
        use_visual_media = use_uploaded_media or use_linked_media
        if not use_visual_media:
            ViralAnalysisCapabilityError.require_text_input(existing["supplement_text"])

        credit_cost = CreditChargeService().estimate_viral_analysis(
            existing["analysis_goal"]
        )
        wallet = WalletRepository(self.conn).get_wallet(user_id)
        if wallet is None or int(wallet["balance"]) < credit_cost:
            raise ViralAnalysisCreditError("insufficient credits")

        job, token = self.repository.claim_for_run(tenant_id, user_id, job_id)
        try:
            if use_visual_media:
                settings, provider = self._vision_provider_from_settings_snapshot()
            else:
                settings, provider = self._provider_from_settings_snapshot()
            # Snapshot reads are committed before any provider HTTP happens.
            self.conn.commit()
        except Exception as exc:
            self.conn.rollback()
            try:
                self._finalize_failure(
                    tenant_id, user_id, job_id, token,
                    "vision" if use_visual_media else "copywriting",
                    "",
                    "AI provider configuration unavailable",
                    "not_configured",
                    request_id=request_id,
                )
            except Exception:
                # The API still returns a closed error while preserving the configuration cause.
                pass
            raise ViralAnalysisProviderError("AI provider configuration failed") from exc
        provider_started_at = perf_counter()
        try:
            if use_uploaded_media:
                generated = self._analyze_uploaded_media(
                    job,
                    provider,
                    upload_root,
                )
            elif use_linked_media:
                generated = self._analyze_linked_media(
                    job,
                    provider,
                    upload_root,
                )
            else:
                generated = provider.generate_text(
                    system_prompt=self._system_prompt(job),
                    user_prompt=job["supplement_text"],
                    temperature=0.3,
                )
            structured = parse_structured_result(generated.content)
            if self._requires_video_transcript(job) and (
                not structured.original_transcript.strip()
                or not structured.transcript_analysis.strip()
            ):
                transcript_prompt = self._transcript_prompt(job)
                if use_uploaded_media:
                    transcript_generated = self._analyze_uploaded_media(
                        job,
                        provider,
                        upload_root,
                        prompt=transcript_prompt,
                    )
                else:
                    transcript_generated = self._analyze_linked_media(
                        job,
                        provider,
                        upload_root,
                        prompt=transcript_prompt,
                    )
                transcript = parse_transcript_result(transcript_generated.content)
                structured = structured.model_copy(
                    update={
                        "original_transcript": transcript.original_transcript,
                        "transcript_analysis": transcript.transcript_analysis,
                    }
                )
                generated = _merge_generation_results(generated, transcript_generated)
        except RemoteMediaError as exc:
            self._finalize_failure(
                tenant_id,
                user_id,
                job_id,
                token,
                settings.provider,
                settings.model,
                str(exc),
                "remote_media",
                request_id=request_id,
                latency_ms=int((perf_counter() - provider_started_at) * 1000),
            )
            raise ViralAnalysisCapabilityError(str(exc)) from exc
        except VisionProviderError as exc:
            self._finalize_failure(
                tenant_id, user_id, job_id, token, settings.provider, settings.model,
                str(exc), exc.code,
                request_id=request_id,
                latency_ms=int((perf_counter() - provider_started_at) * 1000),
            )
            raise ViralAnalysisProviderError from exc
        except AIProviderError as exc:
            self._finalize_failure(
                tenant_id, user_id, job_id, token, settings.provider, settings.model,
                str(exc), exc.code,
                request_id=request_id,
                latency_ms=int((perf_counter() - provider_started_at) * 1000),
            )
            raise ViralAnalysisProviderError from exc
        except ViralAnalysisResponseError:
            self._finalize_failure(
                tenant_id, user_id, job_id, token, settings.provider, settings.model,
                "AI provider returned invalid analysis result", "invalid_response",
                request_id=generated.request_id or request_id,
                latency_ms=int((perf_counter() - provider_started_at) * 1000),
            )
            raise
        except (OSError, TimeoutError, ValueError) as exc:
            self._finalize_failure(
                tenant_id,
                user_id,
                job_id,
                token,
                settings.provider,
                settings.model,
                "AI provider request failed",
                "transport",
                request_id=request_id,
                latency_ms=int((perf_counter() - provider_started_at) * 1000),
            )
            raise ViralAnalysisProviderError from exc

        try:
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
                request_id=request_id,
                commit=False,
            )
            WalletRepository(self.conn).adjust_credits(
                user_id,
                -credit_cost,
                "viral_analysis",
                job_id,
                "爆款解析",
                commit=False,
            )
            self.conn.commit()
            logger.info(
                "viral_analysis_provider_call status=success provider=%s model=%s "
                "request_id=%s duration_ms=%s business_id=%s",
                generated.provider,
                generated.model_name,
                generated.request_id or request_id,
                generated.latency_ms,
                job_id,
            )
        except ValueError as exc:
            self.conn.rollback()
            self._finalize_failure(
                tenant_id,
                user_id,
                job_id,
                token,
                generated.provider,
                generated.model_name,
                "insufficient credits",
                "billing",
                request_id=generated.request_id or request_id,
                latency_ms=generated.latency_ms,
            )
            raise ViralAnalysisCreditError("insufficient credits") from exc
        except Exception:
            self.conn.rollback()
            raise
        completed = self.repository.get_for_user(tenant_id, user_id, job_id)
        return self._external_job(completed) if completed is not None else None

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
        request_id: str = "",
        latency_ms: int = 0,
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
                request_id=request_id,
                latency_ms=latency_ms,
                commit=False,
            )
            self.conn.commit()
            logger.info(
                "viral_analysis_provider_call status=failed provider=%s model=%s "
                "request_id=%s duration_ms=%s business_id=%s error_code=%s",
                provider,
                model_name,
                request_id,
                latency_ms,
                job_id,
                error_code,
            )
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

    def _vision_provider_from_settings_snapshot(self):
        settings_repo = SettingRepository(self.conn)
        settings = get_ai_settings_view(settings_repo).vision
        if not settings.enabled:
            raise AIProviderError("disabled", "AI vision provider is disabled")
        api_key = get_ai_setting_key(settings_repo, "vision")
        if not api_key:
            raise AIProviderError(
                "not_configured",
                "AI vision provider is not configured",
            )
        return settings, OpenAICompatibleVisionClient(settings, api_key)

    def _analyze_uploaded_media(
        self,
        job: dict,
        provider: OpenAICompatibleVisionClient,
        upload_root: Path | None,
        prompt: str | None = None,
    ):
        if upload_root is None:
            raise ValueError("viral analysis upload storage is unavailable")
        material = self.repository.get_material_for_job(
            job["tenant_id"],
            job["id"],
            job["material_file_id"],
        )
        if material is None:
            raise ValueError("viral analysis material is unavailable")

        root = Path(upload_root).resolve()
        media_path = (root / material["storage_path"]).resolve()
        try:
            media_path.relative_to(root)
        except ValueError as exc:
            raise ValueError("viral analysis material path is invalid") from exc
        if not media_path.is_file():
            raise ValueError("viral analysis material is unavailable")

        with prepared_media_path(str(media_path), material["file_type"]) as prepared:
            return provider.analyze_media(
                prepared,
                material["file_type"],
                prompt or self._vision_prompt(job),
            )

    def _analyze_linked_media(
        self,
        job: dict,
        provider: OpenAICompatibleVisionClient,
        upload_root: Path | None,
        prompt: str | None = None,
    ):
        if upload_root is None:
            raise RemoteMediaError("视频链接临时存储不可用，请稍后重试")
        source_url = str(job.get("source_url") or "").strip()
        if not source_url:
            raise RemoteMediaError("请填写需要解析的视频链接")
        media = RemoteMediaService(Path(upload_root) / "remote").fetch(source_url)
        try:
            with prepared_media_path(str(media.path), media.media_type) as prepared:
                return provider.analyze_media(
                    prepared,
                    media.media_type,
                    prompt or self._vision_prompt(job),
                )
        finally:
            media.cleanup()

    def _system_prompt(self, job: dict) -> str:
        goals = ", ".join(job["analysis_goal"]) or "hook, structure, script, reuse"
        return (
            "You are a Xiaohongshu viral-video analysis assistant. "
            "Only analyze the user's supplied supplement text. Do not claim to see video frames. "
            f"Requested dimensions: {goals}. Return strict JSON only with keys "
            "hook_summary, structure_summary, shot_rhythm, script_breakdown, "
            "original_transcript, transcript_analysis, selling_points, reuse_suggestions, "
            "rewritten_script, setting_analysis, "
            "lighting_analysis, visual_style, timeline_visual_analysis, visual_evidence, "
            "tags. Treat the supplied supplement text as the only transcript source: preserve "
            "its wording in original_transcript and ground transcript_analysis in that text. "
            "Analyze the hook wording, sentence and argument progression, emotional triggers, "
            "proof or selling-point language, call to action, information density, reusable "
            "language formula and weaknesses. Do not invent missing dialogue. "
            "Because no image or video is supplied, setting_analysis, "
            "lighting_analysis and visual_style must be empty strings, and both visual "
            "arrays must be empty. Never infer visual details from text alone."
        )

    def _vision_prompt(self, job: dict) -> str:
        goals = ", ".join(job["analysis_goal"]) or (
            "hook, structure, rhythm, script, reuse"
        )
        supplement = job["supplement_text"].strip() or "none"
        return (
            "Analyze the supplied Xiaohongshu reference media using visible frames, "
            "spoken content, music, sound effects, pacing, and scene changes. "
            "Use timestamps when they can be determined. Analyze the setting (shooting "
            "location, background, props, subject position, foreground/midground/background, "
            "spatial layers and color palette), lighting (key-light direction, side/back "
            "light, softness, color temperature, contrast, shadows, highlights and exposure "
            "tendency), and overall visual style. Do not invent lighting power, lux values, "
            "lamp models, exact camera settings, lenses, aperture, shutter speed or ISO. "
            "If a detail cannot be confirmed from visible evidence, label it as inferred or "
            "state that it cannot be confirmed. "
            "Transcribe audible speech and visible subtitles into original_transcript with "
            "timestamps. Label [口播] and [画面字幕] separately when they differ. Preserve the "
            "original wording, repeated phrases and colloquial language. Do not fabricate "
            "transcript content: mark unclear audio as [听不清] and state when visible subtitles "
            "cannot be confirmed. transcript_analysis must be grounded only in "
            "original_transcript and cover hook phrasing, sentence and argument progression, "
            "emotional triggers, proof or selling-point language, call to action, information "
            "density, reusable language formula and weaknesses. "
            f"Requested dimensions: {goals}. Additional user context: {supplement}. "
            "Return strict JSON only with keys hook_summary, structure_summary, "
            "shot_rhythm, script_breakdown, original_transcript, transcript_analysis, "
            "selling_points, reuse_suggestions, "
            "rewritten_script, setting_analysis, lighting_analysis, visual_style, "
            "timeline_visual_analysis, visual_evidence, tags. timeline_visual_analysis "
            "must be an array of objects with time_range, setting, lighting, visual_style, "
            "evidence_type, confidence and visible_evidence. visual_evidence must be an "
            "array of objects with conclusion, evidence_type, confidence and "
            "visible_evidence. evidence_type must be visible_confirmed when the conclusion "
            "is directly visible, or inferred when it is only inferred from the image. "
            "confidence must be high, medium or low. All descriptive values must be Chinese; "
            "tags must be an array."
        )

    def _transcript_prompt(self, job: dict) -> str:
        supplement = job["supplement_text"].strip() or "none"
        return (
            "Perform a dedicated transcript pass on the supplied Xiaohongshu video. "
            "Return strict JSON only with keys original_transcript and transcript_analysis. "
            "In original_transcript, transcribe all audible speech and all visible subtitles "
            "in chronological order with timestamps. Label [口播] and [画面字幕] separately "
            "when they differ. Preserve exact wording, repetitions and colloquial language; "
            "mark uncertain audio as [听不清]. If the video truly has no confirmable speech "
            "or subtitles, return a non-empty Chinese statement explaining that result. "
            "Ground transcript_analysis only in original_transcript and analyze the opening "
            "hook, sentence and argument progression, emotional triggers, proof or selling "
            "points, call to action, information density, reusable language formula and "
            "weaknesses. Never invent dialogue or claims. "
            f"Additional user context: {supplement}. All values must be Chinese strings."
        )

    @staticmethod
    def _requires_video_transcript(job: dict) -> bool:
        if job.get("source_type") == "link":
            return True
        selected_id = int(job.get("material_file_id") or 0)
        return any(
            int(material.get("id") or 0) == selected_id
            and material.get("file_type") == "video"
            for material in job.get("materials") or []
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
    last_error: Exception | None = None
    for value in _provider_json_objects(raw):
        try:
            for field in (
                "hook_summary",
                "structure_summary",
                "shot_rhythm",
                "script_breakdown",
                "original_transcript",
                "transcript_analysis",
                "selling_points",
                "reuse_suggestions",
                "rewritten_script",
                "setting_analysis",
                "lighting_analysis",
                "visual_style",
            ):
                if field in value:
                    value[field] = _normalize_provider_text(value[field])
            return ViralAnalysisStructuredResult.model_validate(value)
        except (ValidationError, TypeError, ValueError) as exc:
            last_error = exc
    raise ViralAnalysisResponseError(
        "AI provider returned invalid analysis result"
    ) from last_error


def parse_transcript_result(raw: str) -> ViralAnalysisTranscriptResult:
    last_error: Exception | None = None
    for value in _provider_json_objects(raw):
        try:
            normalized = {
                field: _normalize_provider_text(value.get(field)).strip()
                for field in ("original_transcript", "transcript_analysis")
            }
            return ViralAnalysisTranscriptResult.model_validate(normalized)
        except (ValidationError, TypeError, ValueError) as exc:
            last_error = exc
    raise ViralAnalysisResponseError(
        "AI provider returned invalid transcript result"
    ) from last_error


def _merge_generation_results(
    primary: TextGenerationResult,
    transcript: TextGenerationResult,
) -> TextGenerationResult:
    return TextGenerationResult(
        content=primary.content,
        provider=primary.provider,
        model_name=primary.model_name,
        latency_ms=primary.latency_ms + transcript.latency_ms,
        input_chars=primary.input_chars + transcript.input_chars,
        output_chars=primary.output_chars + transcript.output_chars,
        request_id=primary.request_id or transcript.request_id,
    )


def _provider_json_objects(raw: str):
    normalized = raw.strip().lstrip("\ufeff")
    candidates = [normalized]
    fenced = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        normalized,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced is not None:
        candidates.insert(0, fenced.group(1).strip())

    decoder = json.JSONDecoder()
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            value = None
        if isinstance(value, dict):
            yield value

    for match in re.finditer(r"{", normalized):
        try:
            value, _ = decoder.raw_decode(normalized[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            yield value


def _normalize_provider_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            part for item in value if (part := _normalize_provider_text(item).strip())
        )
    if isinstance(value, dict):
        return "\n".join(
            f"{key}: {_normalize_provider_text(item)}"
            for key, item in value.items()
        )
    if value is None:
        return ""
    return str(value)
