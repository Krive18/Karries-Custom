from app.repositories.ai_personalization_repository import (
    AIPersonalizationRepository,
)
from app.schemas.inspiration import (
    InspirationPersonalizationPreferenceUpdate,
    InspirationPersonalizationTemplateCreate,
    InspirationPersonalizationTemplateUpdate,
    InspirationPersonalizationUpdate,
)


DEFAULT_AI_PERSONALIZATION = {
    "assistant_name": "AI Agent",
    "assistant_traits": "专业、耐心、务实，擅长小红书内容策划与运营",
    "preferred_address": "",
    "occupation": "",
    "user_details": "",
    "response_preferences": "回答清晰、可执行，优先给出适合小红书运营的具体建议",
}

LEGACY_DEFAULT_ASSISTANT_NAMES = {"AI灵感对话", "Agent交互"}


class AIPersonalizationService:
    def __init__(self, conn) -> None:
        self.repository = AIPersonalizationRepository(conn)

    def get_for_user(self, user: dict) -> dict:
        profile = self.repository.get_for_user(user["tenant_id"], user["id"])
        if profile is not None:
            if profile.get("assistant_name") in LEGACY_DEFAULT_ASSISTANT_NAMES:
                profile = {**profile, "assistant_name": DEFAULT_AI_PERSONALIZATION["assistant_name"]}
            return profile
        return {
            "id": 0,
            "tenant_id": user["tenant_id"],
            "user_id": user["id"],
            **DEFAULT_AI_PERSONALIZATION,
            "create_time": 0,
            "update_time": 0,
        }

    def update_for_user(
        self,
        user: dict,
        payload: InspirationPersonalizationUpdate,
    ) -> dict:
        return self.repository.upsert_for_user(
            user["tenant_id"],
            user["id"],
            payload.model_dump(),
        )

    def list_templates(self, user: dict, include_archived: bool = False) -> list[dict]:
        tenant_id = user["tenant_id"]
        user_id = user["id"]
        self.repository.migrate_legacy_profile(tenant_id, user_id)
        return self.repository.list_templates_for_user(
            tenant_id, user_id, include_archived=include_archived
        )

    def get_template(
        self, user: dict, template_id: int, *, include_archived: bool = False
    ) -> dict | None:
        return self.repository.get_template_for_user(
            user["tenant_id"],
            user["id"],
            template_id,
            include_archived=include_archived,
        )

    def create_template(
        self, user: dict, payload: InspirationPersonalizationTemplateCreate
    ) -> dict:
        return self.repository.create_template(
            user["tenant_id"], user["id"], payload.model_dump()
        )

    def update_template(
        self,
        user: dict,
        template_id: int,
        payload: InspirationPersonalizationTemplateUpdate,
    ) -> dict | None:
        return self.repository.update_template(
            user["tenant_id"], user["id"], template_id, payload.model_dump()
        )

    def duplicate_template(self, user: dict, template_id: int) -> dict | None:
        source = self.get_template(user, template_id)
        if source is None:
            return None
        values = {
            key: source[key]
            for key in (
                "assistant_name",
                "assistant_traits",
                "preferred_address",
                "occupation",
                "user_details",
                "response_preferences",
            )
        }
        values["template_name"] = f"{source['template_name']} 副本"[:100]
        return self.repository.create_template(user["tenant_id"], user["id"], values)

    def archive_template(self, user: dict, template_id: int) -> dict | None:
        previous_preference = self.repository.get_preference_for_user(
            user["tenant_id"], user["id"]
        )
        archived = self.repository.archive_template(
            user["tenant_id"], user["id"], template_id
        )
        if archived is None:
            return None
        if (
            previous_preference is not None
            and previous_preference["interaction_mode"] == "personalized"
            and int(previous_preference["personalization_template_id"] or 0)
            == template_id
        ):
            self.repository.upsert_preference(
                user["tenant_id"], user["id"], "normal", 0
            )
        return archived

    def get_preference(self, user: dict) -> dict:
        preference = self.repository.get_preference_for_user(
            user["tenant_id"], user["id"]
        )
        if preference is None:
            return {
                "id": 0,
                "tenant_id": user["tenant_id"],
                "user_id": user["id"],
                "interaction_mode": "normal",
                "personalization_template_id": 0,
                "create_time": 0,
                "update_time": 0,
            }
        template_id = int(preference["personalization_template_id"] or 0)
        if preference["interaction_mode"] == "personalized" and (
            template_id <= 0 or self.get_template(user, template_id) is None
        ):
            return {**preference, "interaction_mode": "normal", "personalization_template_id": 0}
        return preference

    def update_preference(
        self, user: dict, payload: InspirationPersonalizationPreferenceUpdate
    ) -> dict:
        template_id = payload.personalization_template_id
        if payload.interaction_mode == "personalized":
            if template_id <= 0 or self.get_template(user, template_id) is None:
                raise LookupError("personalization template not found")
        return self.repository.upsert_preference(
            user["tenant_id"],
            user["id"],
            payload.interaction_mode,
            template_id,
        )
