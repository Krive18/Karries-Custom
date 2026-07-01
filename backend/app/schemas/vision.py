from pydantic import BaseModel, Field


class VisionAnalysisResult(BaseModel):
    provider: str = "local"
    summary: str
    product_name: str = ""
    scene: str = ""
    colors: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    selling_points: list[str] = Field(default_factory=list)
    raw_text: str = ""
