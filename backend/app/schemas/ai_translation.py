from typing import Literal

from pydantic import BaseModel, Field, model_validator


TranslationLanguage = Literal[
    "auto",
    "vi",
    "en",
    "zh",
    "ms",
    "th",
    "tl",
    "ja",
    "ko",
    "es",
]
TranslationTargetLanguage = Literal[
    "vi",
    "en",
    "zh",
    "ms",
    "th",
    "tl",
    "ja",
    "ko",
    "es",
]


class AiTranslationMaterialCreate(BaseModel):
    material_file_id: int = Field(ge=1)
    source_language: TranslationLanguage = "auto"
    target_language: TranslationTargetLanguage
    client_request_id: str = Field(min_length=8, max_length=64)

    @model_validator(mode="after")
    def normalize_request(self):
        self.client_request_id = self.client_request_id.strip()
        if not self.client_request_id:
            raise ValueError("client_request_id is required")
        if self.source_language != "auto" and self.source_language == self.target_language:
            raise ValueError("source and target languages must be different")
        return self


class AiTranslationUploadMeta(BaseModel):
    source_language: TranslationLanguage = "auto"
    target_language: TranslationTargetLanguage
    client_request_id: str = Field(min_length=8, max_length=64)

    @model_validator(mode="after")
    def normalize_request(self):
        self.client_request_id = self.client_request_id.strip()
        if not self.client_request_id:
            raise ValueError("client_request_id is required")
        if self.source_language != "auto" and self.source_language == self.target_language:
            raise ValueError("source and target languages must be different")
        return self


class AiTranslationActionRequest(BaseModel):
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def normalize_note(self):
        self.note = self.note.strip()
        return self


class AiTranslationRevisionRequest(BaseModel):
    feedback: str = Field(min_length=5, max_length=2000)

    @model_validator(mode="after")
    def normalize_feedback(self):
        self.feedback = self.feedback.strip()
        if len(self.feedback) < 5:
            raise ValueError("revision feedback must contain at least 5 characters")
        return self
