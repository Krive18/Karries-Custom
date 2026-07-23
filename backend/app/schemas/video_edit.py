from typing import Any, Literal

from pydantic import BaseModel, Field


VideoEditStatusName = Literal[
    "submitted",
    "in_production",
    "delivered",
    "revision_requested",
    "cancelled",
]


class VideoEditMaterial(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    file_type: Literal["image", "video", "document", "other"] = "other"
    file_path: str = Field(default="", max_length=500)
    mime_type: str = Field(default="", max_length=100)
    file_size: int = Field(default=0, ge=0)
    remark: str = Field(default="", max_length=500)


class VideoEditJobCreate(BaseModel):
    job_title: str = Field(min_length=1, max_length=200)
    script_text: str = Field(min_length=1, max_length=10000)
    requirement_text: str = Field(default="", max_length=2000)
    materials: list[VideoEditMaterial] = Field(default_factory=list, max_length=50)


class VideoEditJobClaimRequest(BaseModel):
    note: str = Field(default="", max_length=1000)


class VideoEditJobDeliverRequest(BaseModel):
    delivery_file_name: str = Field(min_length=1, max_length=255)
    delivery_file_path: str = Field(default="", max_length=500)
    delivery_url: str = Field(default="", max_length=1000)
    note: str = Field(default="", max_length=1000)


class VideoEditJobView(BaseModel):
    id: int
    user_id: int
    job_title: str
    script_text: str
    requirement_text: str
    materials: list[dict[str, Any]]
    status: int
    status_name: VideoEditStatusName
    status_text: str
    user_progress_text: str
    expected_delivery_time: int
    operator_user_id: int
    developer_note: str
    delivery: dict[str, Any]
    delivered_time: int
    create_time: int
    update_time: int
