from typing import Literal

from pydantic import BaseModel, Field


DraftStatus = Literal["draft", "confirmed", "rejected"]


class ContentDraftGenerateRequest(BaseModel):
    product_id: int = Field(ge=1)
    xhs_account_id: int = Field(default=0, ge=0)
    content_direction: str = Field(default="xiaohongshu_seed", max_length=100)
    tone: str = Field(default="natural", max_length=100)
    extra_requirement: str = Field(default="", max_length=1000)


class ContentDraftUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    body: str | None = Field(default=None, min_length=1, max_length=5000)
    tags: list[str] | None = Field(default=None, max_length=20)
    status: DraftStatus | None = None
