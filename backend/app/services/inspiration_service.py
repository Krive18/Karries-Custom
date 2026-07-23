import uuid

from app.repositories.ai_usage_repository import AIUsageRepository
from app.repositories.content_draft_repository import ContentDraftRepository
from app.repositories.inspiration_repository import (
    InspirationRepository,
    InspirationSessionNotFoundError,
    InspirationSessionStateError,
)
from app.repositories.product_repository import ProductRepository
from app.repositories.setting_repository import SettingRepository
from app.repositories.xhs_account_repository import XHSAccountRepository
from app.schemas.inspiration import InspirationMessageCreate, InspirationSessionCreate
from app.services.ai_provider_service import AIProviderError, AIProviderService
from app.services.ai_settings_service import get_ai_setting_key, get_ai_settings_view
from app.services.ai_usage_service import AIUsageService
from app.services.credit_charge_service import CreditChargeService


class InspirationProviderError(Exception):
    pass


class _SnapshotSettingRepository:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def get(self, key: str, default: str = "") -> str:
        return self.values.get(key, default)


class InspirationService:
    def __init__(self, conn) -> None:
        self.conn = conn
        self.repository = InspirationRepository(conn)

    def create_session(self, user: dict, payload: InspirationSessionCreate) -> dict:
        if payload.linked_product_id > 0:
            product = ProductRepository(self.conn).get_for_user(
                user["id"], payload.linked_product_id
            )
            if product is None:
                raise LookupError("product not found")
        if payload.linked_xhs_account_id > 0:
            account = XHSAccountRepository(self.conn).get_for_user(
                user["id"], payload.linked_xhs_account_id
            )
            if account is None:
                raise LookupError("xhs account not found")
        return self.repository.create_session(user["tenant_id"], user["id"], payload)

    def list_sessions(self, user: dict, page: int, page_size: int) -> dict:
        return self.repository.list_sessions_for_user(
            user["tenant_id"], user["id"], page, page_size
        )

    def get_session(self, user: dict, session_id: int) -> dict | None:
        session = self.repository.get_session_for_user(
            user["tenant_id"], user["id"], session_id
        )
        if session is None:
            return None
        return {
            "session": session,
            "messages": self.repository.list_messages_for_user(
                user["tenant_id"], user["id"], session_id
            ),
        }

    def archive_session(self, user: dict, session_id: int) -> dict:
        try:
            return self.repository.archive_active_session(
                user["tenant_id"], user["id"], session_id
            )
        except Exception:
            self.conn.rollback()
            raise

    def send_message(
        self, user: dict, session_id: int, payload: InspirationMessageCreate
    ) -> dict:
        tenant_id = user["tenant_id"]
        user_id = user["id"]
        client_request_id = (
            getattr(payload, "client_request_id", "").strip() or uuid.uuid4().hex
        )

        try:
            existing = self.repository.get_session_for_user(tenant_id, user_id, session_id)
            if existing is None:
                raise InspirationSessionNotFoundError
            context = self._context_from_session(existing)
            session, user_message, generation_token, assistant_message = (
                self.repository.claim_and_store_user_message(
                    tenant_id,
                    user_id,
                    session_id,
                    payload.content,
                    context,
                    client_request_id,
                )
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        if assistant_message is not None:
            if assistant_message["status"] == "failed":
                raise InspirationProviderError
            return {
                "user_message": user_message,
                "assistant_message": assistant_message,
                "credit_cost": assistant_message["credit_cost"],
            }

        history = self.repository.list_successful_history(
            tenant_id, user_id, session_id, user_message["id"]
        )
        try:
            provider_settings, provider = self._provider_from_settings_snapshot()
            provider_name = str(getattr(provider_settings, "provider", "unknown"))
            model_name = str(getattr(provider_settings, "model", ""))
        except Exception as exc:
            self.conn.rollback()
            provider_error = self._provider_error_from_exception(exc)
            self._finalize_provider_failure(
                tenant_id,
                user_id,
                session_id,
                context,
                "unknown",
                "",
                provider_error,
                generation_token,
                client_request_id,
            )
            raise InspirationProviderError from exc
        # History and settings reads are completed before the provider HTTP request.
        self.conn.commit()
        credit_cost = CreditChargeService().estimate("inspiration_chat")
        try:
            result = provider.generate_text(
                system_prompt=self._system_prompt(context),
                user_prompt=payload.content,
                history=history,
            )
        except Exception as exc:
            provider_error = self._provider_error_from_exception(exc)
            self._finalize_provider_failure(
                tenant_id,
                user_id,
                session_id,
                context,
                provider_name,
                model_name,
                provider_error,
                generation_token,
                client_request_id,
            )
            raise InspirationProviderError from exc

        try:
            assistant_message_id = self.repository.finalize_generation(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                content=result.content,
                context=context,
                ai_provider=result.provider,
                ai_model=result.model_name,
                generation_token=generation_token,
                credit_cost=credit_cost,
                latency_ms=result.latency_ms,
                status="success",
                client_request_id=client_request_id,
            )
            AIUsageService(AIUsageRepository(self.conn)).record_success(
                tenant_id=tenant_id,
                user_id=user_id,
                business_type="inspiration_chat",
                business_id=session_id,
                result=result,
                credit_cost=credit_cost,
                commit=False,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        assistant_message = self.repository.get_message_for_user(
            tenant_id, user_id, assistant_message_id
        )
        if assistant_message is None:
            raise RuntimeError("finalized inspiration message was not found")
        return {
            "user_message": user_message,
            "assistant_message": assistant_message,
            "credit_cost": credit_cost,
        }

    def save_draft(self, user: dict, message_id: int) -> int | None:
        message = self.repository.get_message_for_user(
            user["tenant_id"], user["id"], message_id
        )
        if message is None or message["role"] != "assistant" or message["status"] != "success":
            return None
        return ContentDraftRepository(self.conn).create_from_ai_text(
            tenant_id=user["tenant_id"],
            user_id=user["id"],
            source_type="inspiration",
            source_id=message_id,
            title=self._derive_title(message["content"]),
            body=message["content"],
            ai_provider=message["ai_provider"],
            model_name=message["ai_model"],
            context=message["context"],
        )

    def list_sessions_for_admin(
        self,
        user: dict,
        page: int,
        page_size: int,
        user_id: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        product_id: int | None = None,
        keyword: str | None = None,
    ) -> dict:
        return self.repository.list_sessions_for_admin(
            user["tenant_id"],
            page,
            page_size,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            product_id=product_id,
            keyword=keyword,
        )

    def get_session_for_admin(self, user: dict, session_id: int) -> dict | None:
        session = self.repository.get_session_for_admin(user["tenant_id"], session_id)
        if session is None:
            return None
        return {
            "session": session,
            "messages": self.repository.list_messages_for_admin(user["tenant_id"], session_id),
        }

    def _finalize_provider_failure(
        self,
        tenant_id: int,
        user_id: int,
        session_id: int,
        context: dict,
        provider: str,
        model_name: str,
        error: AIProviderError,
        generation_token: str,
        client_request_id: str,
    ) -> None:
        try:
            self.repository.finalize_generation(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                content="",
                context=context,
                ai_provider=provider,
                ai_model=model_name,
                generation_token=generation_token,
                credit_cost=0,
                latency_ms=0,
                status="failed",
                error_message=str(error),
                client_request_id=client_request_id,
            )
            AIUsageService(AIUsageRepository(self.conn)).record_failure(
                tenant_id=tenant_id,
                user_id=user_id,
                business_type="inspiration_chat",
                business_id=session_id,
                provider=provider,
                model_name=model_name,
                error_message=str(error),
                error_code=error.code,
                commit=False,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _provider_error_from_exception(self, error: Exception) -> AIProviderError:
        if isinstance(error, AIProviderError):
            return error
        return AIProviderError("transport", "AI service initialization or call failed")

    def _context_from_session(self, session: dict) -> dict:
        return {
            "session_title": session["title"],
            "linked_product_id": session["linked_product_id"],
            "linked_xhs_account_id": session["linked_xhs_account_id"],
            "goal_type": session["goal_type"],
            "tone": session["tone"],
            "extra_requirement": session["extra_requirement"],
        }

    def _system_prompt(self, context: dict) -> str:
        return (
            "You are a Xiaohongshu content ideation assistant. "
            f"Conversation goal: {context['goal_type']}. "
            f"Tone: {context['tone']}. "
            f"Additional requirement: {context['extra_requirement']}."
        )

    def _derive_title(self, content: str) -> str:
        first_line = next((line.strip() for line in content.splitlines() if line.strip()), "")
        return first_line[:100] or "AI inspiration draft"

    def _provider_from_settings_snapshot(self):
        settings_repo = SettingRepository(self.conn)
        settings = get_ai_settings_view(settings_repo).copywriting
        values = {
            "ai.copywriting.provider": settings.provider,
            "ai.copywriting.base_url": settings.base_url,
            "ai.copywriting.model": settings.model,
            "ai.copywriting.enabled": "true" if settings.enabled else "false",
            "ai.copywriting.api_key": get_ai_setting_key(settings_repo, "copywriting"),
        }
        return settings, AIProviderService(_SnapshotSettingRepository(values))
