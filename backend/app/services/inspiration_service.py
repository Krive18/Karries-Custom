from app.repositories.ai_usage_repository import AIUsageRepository
from app.repositories.content_draft_repository import ContentDraftRepository
from app.repositories.inspiration_repository import InspirationRepository
from app.repositories.setting_repository import SettingRepository
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

    def archive_session(self, user: dict, session_id: int) -> dict | None:
        return self.repository.archive_session(user["tenant_id"], user["id"], session_id)

    def send_message(
        self, user: dict, session_id: int, payload: InspirationMessageCreate
    ) -> dict:
        tenant_id = user["tenant_id"]
        user_id = user["id"]
        session = self.repository.get_session_for_user(tenant_id, user_id, session_id)
        if session is None:
            raise LookupError("session not found")
        if session["status"] != "active":
            raise ValueError("session is archived")

        context = self._context_from_session(session)
        user_message = self.repository.add_message(
            tenant_id, user_id, session_id, "user", payload.content, context
        )
        history = self.repository.list_successful_history(tenant_id, user_id, session_id)
        history = history[:-1] if history and history[-1][0] == "user" else history

        provider_settings, provider = self._provider_from_settings_snapshot()
        # All writes and settings reads above are committed before the provider HTTP request.
        self.conn.commit()
        credit_cost = CreditChargeService().estimate("inspiration_chat")
        try:
            result = provider.generate_text(
                system_prompt=self._system_prompt(context),
                user_prompt=payload.content,
                history=history,
            )
        except AIProviderError as exc:
            self.repository.add_message(
                tenant_id,
                user_id,
                session_id,
                "assistant",
                "",
                context,
                ai_provider=provider_settings.provider,
                ai_model=provider_settings.model,
                status="failed",
                error_message=str(exc),
            )
            AIUsageService(AIUsageRepository(self.conn)).record_failure(
                tenant_id=tenant_id,
                user_id=user_id,
                business_type="inspiration_chat",
                business_id=session_id,
                provider=provider_settings.provider,
                model_name=provider_settings.model,
                error_message=str(exc),
                error_code=exc.code,
            )
            raise InspirationProviderError from exc

        assistant_message = self.repository.add_message(
            tenant_id,
            user_id,
            session_id,
            "assistant",
            result.content,
            context,
            ai_provider=result.provider,
            ai_model=result.model_name,
            credit_cost=credit_cost,
            latency_ms=result.latency_ms,
        )
        AIUsageService(AIUsageRepository(self.conn)).record_success(
            tenant_id=tenant_id,
            user_id=user_id,
            business_type="inspiration_chat",
            business_id=session_id,
            result=result,
            credit_cost=credit_cost,
        )
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
            user_id=user["id"],
            source_type="inspiration",
            source_id=message_id,
            title=self._derive_title(message["content"]),
            body=message["content"],
            ai_provider=message["ai_provider"],
            model_name=message["ai_model"],
            context=message["context"],
        )

    def list_sessions_for_admin(self, user: dict, page: int, page_size: int) -> dict:
        return self.repository.list_sessions_for_admin(user["tenant_id"], page, page_size)

    def get_session_for_admin(self, user: dict, session_id: int) -> dict | None:
        session = self.repository.get_session_for_admin(user["tenant_id"], session_id)
        if session is None:
            return None
        return {
            "session": session,
            "messages": self.repository.list_messages_for_admin(user["tenant_id"], session_id),
        }

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
