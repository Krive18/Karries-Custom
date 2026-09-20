from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.viral_analysis import (
    ViralAnalysisTimelineVisualSegment,
    ViralAnalysisVisualEvidence,
)


ContentCollectionSourceType = Literal["viral_analysis"]
CollectionTag = Annotated[str, Field(min_length=1, max_length=100)]


class ContentCollectionCreateRequest(BaseModel):
    source_type: ContentCollectionSourceType = "viral_analysis"
    source_id: int = Field(ge=1)


class ContentCollectionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    hook_summary: str | None = Field(default=None, min_length=1, max_length=3000)
    structure_summary: str | None = Field(default=None, min_length=1, max_length=5000)
    shot_rhythm: str | None = Field(default=None, max_length=5000)
    script_breakdown: str | None = Field(default=None, max_length=10000)
    selling_points: str | None = Field(default=None, max_length=5000)
    reuse_suggestions: str | None = Field(default=None, max_length=10000)
    rewritten_script: str | None = Field(default=None, max_length=10000)
    setting_analysis: str | None = Field(default=None, max_length=10000)
    lighting_analysis: str | None = Field(default=None, max_length=10000)
    visual_style: str | None = Field(default=None, max_length=5000)
    timeline_visual_analysis: list[ViralAnalysisTimelineVisualSegment] | None = Field(
        default=None,
        max_length=120,
    )
    visual_evidence: list[ViralAnalysisVisualEvidence] | None = Field(
        default=None,
        max_length=100,
    )
    tags: list[CollectionTag] | None = Field(default=None, max_length=20)

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, value):
        if isinstance(value, dict) and any(item is None for item in value.values()):
            raise ValueError("collection fields cannot be null")
        return value
