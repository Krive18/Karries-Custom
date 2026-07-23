from typing import Literal

from pydantic import BaseModel, Field


ViralSourceType = Literal["upload", "link", "text"]
ViralAnalysisGoal = Literal["hook", "structure", "rhythm", "script", "selling", "reuse"]


class ViralAnalysisJobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    source_type: ViralSourceType
    source_url: str = Field(default="", max_length=2000)
    analysis_goal: list[ViralAnalysisGoal] = Field(default_factory=list, max_length=6)
    supplement_text: str = Field(default="", max_length=10000)


class ViralAnalysisStructuredResult(BaseModel):
    hook_summary: str = Field(min_length=1, max_length=3000)
    structure_summary: str = Field(min_length=1, max_length=5000)
    shot_rhythm: str = Field(default="", max_length=5000)
    script_breakdown: str = Field(default="", max_length=10000)
    selling_points: str = Field(default="", max_length=5000)
    reuse_suggestions: str = Field(default="", max_length=10000)
    rewritten_script: str = Field(default="", max_length=10000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class ViralAnalysisMaterialUpload(BaseModel):
    # This marker model reserves the public upload contract for generated docs.
    job_id: int = Field(ge=1)
