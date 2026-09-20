from pydantic import BaseModel, Field


class ImageCopyRequest(BaseModel):
    image_paths: list[str] = Field(default_factory=list)
    material_ids: list[int] = Field(default_factory=list, max_length=20)
    xhs_account_id: int = Field(default=0, ge=0)
    style: str = "小红书种草"
    extra_prompt: str = ""


class ImageCopyResult(BaseModel):
    title: str
    body: str
    tags: list[str]
    history_id: int = 0
