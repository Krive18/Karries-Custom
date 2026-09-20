from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


ViralSourceType = Literal["upload", "link", "text"]
ViralAnalysisGoal = Literal[
    "hook",
    "structure",
    "rhythm",
    "script",
    "selling",
    "reuse",
    "setting",
    "lighting",
]
ViralAnalysisStatus = Literal["pending", "processing", "completed", "failed", "cancelled"]
VisualEvidenceType = Literal["visible_confirmed", "inferred"]
VisualConfidence = Literal["high", "medium", "low"]


def _normalize_evidence_type(value):
    aliases = {
        "画面可确认": "visible_confirmed",
        "可确认": "visible_confirmed",
        "visible": "visible_confirmed",
        "根据画面推测": "inferred",
        "推测": "inferred",
        "inference": "inferred",
    }
    return aliases.get(str(value).strip(), value)


def _normalize_confidence(value):
    aliases = {
        "高": "high",
        "高可信度": "high",
        "中": "medium",
        "中可信度": "medium",
        "低": "low",
        "低可信度": "low",
    }
    return aliases.get(str(value).strip(), value)


class ViralAnalysisTimelineVisualSegment(BaseModel):
    time_range: str = Field(min_length=1, max_length=50)
    setting: str = Field(default="", max_length=3000)
    lighting: str = Field(default="", max_length=3000)
    visual_style: str = Field(default="", max_length=2000)
    evidence_type: VisualEvidenceType
    confidence: VisualConfidence
    visible_evidence: str = Field(min_length=1, max_length=3000)

    @field_validator("evidence_type", mode="before")
    @classmethod
    def normalize_evidence_type(cls, value):
        return _normalize_evidence_type(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value):
        return _normalize_confidence(value)


class ViralAnalysisVisualEvidence(BaseModel):
    conclusion: str = Field(min_length=1, max_length=3000)
    evidence_type: VisualEvidenceType
    confidence: VisualConfidence
    visible_evidence: str = Field(min_length=1, max_length=3000)

    @field_validator("evidence_type", mode="before")
    @classmethod
    def normalize_evidence_type(cls, value):
        return _normalize_evidence_type(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value):
        return _normalize_confidence(value)


class ViralAnalysisJobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    source_type: ViralSourceType
    source_url: str = Field(default="", max_length=2000)
    analysis_goal: list[ViralAnalysisGoal] = Field(default_factory=list, max_length=8)
    supplement_text: str = Field(default="", max_length=10000)


class ViralAnalysisStructuredResult(BaseModel):
    hook_summary: str = Field(min_length=1, max_length=3000)
    structure_summary: str = Field(min_length=1, max_length=5000)
    shot_rhythm: str = Field(default="", max_length=5000)
    script_breakdown: str = Field(default="", max_length=10000)
    original_transcript: str = Field(default="", max_length=20000)
    transcript_analysis: str = Field(default="", max_length=10000)
    selling_points: str = Field(default="", max_length=5000)
    reuse_suggestions: str = Field(default="", max_length=10000)
    rewritten_script: str = Field(default="", max_length=10000)
    setting_analysis: str = Field(default="", max_length=10000)
    lighting_analysis: str = Field(default="", max_length=10000)
    visual_style: str = Field(default="", max_length=5000)
    timeline_visual_analysis: list[ViralAnalysisTimelineVisualSegment] = Field(
        default_factory=list,
        max_length=120,
    )
    visual_evidence: list[ViralAnalysisVisualEvidence] = Field(
        default_factory=list,
        max_length=100,
    )
    tags: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list,
        max_length=20,
    )


class ViralAnalysisTranscriptResult(BaseModel):
    original_transcript: str = Field(min_length=1, max_length=20000)
    transcript_analysis: str = Field(min_length=1, max_length=10000)


class ViralAnalysisMaterialUpload(BaseModel):
    # This marker model reserves the public upload contract for generated docs.
    job_id: int = Field(ge=1)


class ViralAnalysisLibraryMaterialSelect(BaseModel):
    material_file_id: int = Field(ge=1)
