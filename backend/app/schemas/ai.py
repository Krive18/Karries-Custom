from pydantic import BaseModel, Field


class ImageCopyRequest(BaseModel):
    image_paths: list[str] = Field(default_factory=list)
    style: str = "小红书种草"
    extra_prompt: str = ""


class ImageCopyResult(BaseModel):
    title: str
    body: str
    tags: list[str]
