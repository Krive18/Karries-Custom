import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator


GoalType = Literal[
    "general",
    "topic",
    "title",
    "body",
    "script",
    "strategy",
    "optimize",
]
SessionStatus = Literal["active", "generating", "archived"]
InteractionMode = Literal["normal", "personalized"]
ModelMode = Literal["standard", "pro"]


class InspirationSessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    linked_product_id: int = Field(default=0, ge=0)
    linked_xhs_account_id: int = Field(default=0, ge=0)
    interaction_mode: InteractionMode = "personalized"
    personalization_template_id: int = Field(default=0, ge=0)
    goal_type: GoalType = "general"
    tone: str = Field(default="自然真诚", max_length=100)
    extra_requirement: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def normalize_conversation_space(self):
        if self.interaction_mode == "normal":
            self.personalization_template_id = 0
        return self


class InspirationMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    model_mode: ModelMode = "standard"
    attachment_ids: list[int] = Field(default_factory=list, max_length=4)
    client_request_id: str = Field(
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )

    @field_validator("attachment_ids")
    @classmethod
    def normalize_attachment_ids(cls, value: list[int]) -> list[int]:
        normalized = list(dict.fromkeys(value))
        if any(item <= 0 for item in normalized):
            raise ValueError("attachment ids must be positive")
        return normalized


class InspirationMessageRevisionCreate(InspirationMessageCreate):
    retained_attachment_ids: list[int] = Field(default_factory=list, max_length=4)

    @field_validator("retained_attachment_ids")
    @classmethod
    def normalize_retained_attachment_ids(cls, value: list[int]) -> list[int]:
        normalized = list(dict.fromkeys(value))
        if any(item <= 0 for item in normalized):
            raise ValueError("retained attachment ids must be positive")
        return normalized

    @model_validator(mode="after")
    def limit_total_attachments(self):
        if len(set(self.attachment_ids) | set(self.retained_attachment_ids)) > 4:
            raise ValueError("a message revision accepts at most four attachments")
        return self


class InspirationSessionPin(BaseModel):
    is_pinned: bool


class InspirationSessionRename(BaseModel):
    title: str = Field(min_length=1, max_length=100)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("title must not be blank")
        return title


class InspirationPersonalizationUpdate(BaseModel):
    assistant_name: str = Field(default="AI Agent", min_length=1, max_length=50)
    assistant_traits: str = Field(default="", max_length=500)
    preferred_address: str = Field(default="", max_length=50)
    occupation: str = Field(default="", max_length=100)
    user_details: str = Field(default="", max_length=2000)
    response_preferences: str = Field(default="", max_length=1000)

    @field_validator(
        "assistant_name",
        "assistant_traits",
        "preferred_address",
        "occupation",
        "user_details",
        "response_preferences",
    )
    @classmethod
    def normalize_text(cls, value: str, info: ValidationInfo) -> str:
        normalized = value.strip()
        if info.field_name == "assistant_name" and not normalized:
            raise ValueError("assistant name must not be blank")
        if info.field_name in {
            "assistant_name",
            "assistant_traits",
            "preferred_address",
            "occupation",
        }:
            normalized = re.sub(r"\s+", " ", normalized)
        return normalized


class InspirationPersonalizationTemplateUpdate(InspirationPersonalizationUpdate):
    template_name: str = Field(min_length=1, max_length=100)

    @field_validator("template_name")
    @classmethod
    def normalize_template_name(cls, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value.strip())
        if not normalized:
            raise ValueError("template name must not be blank")
        return normalized


class InspirationPersonalizationTemplateCreate(
    InspirationPersonalizationTemplateUpdate
):
    pass


class InspirationPersonalizationPreferenceUpdate(BaseModel):
    interaction_mode: InteractionMode = "normal"
    personalization_template_id: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def normalize_selection(self):
        if self.interaction_mode == "normal":
            self.personalization_template_id = 0
        return self
