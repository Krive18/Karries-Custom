from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


VideoEditStatusName = Literal[
    "submitted",
    "in_production",
    "delivered",
    "revision_requested",
    "cancelled",
    "returned",
]
VideoEditReviewStatus = Literal["draft", "confirmed", "rejected"]
VideoCreationMode = Literal["standard", "pro"]


class VideoEditMaterial(BaseModel):
    material_file_id: int = Field(default=0, ge=0)
    file_name: str = Field(min_length=1, max_length=255)
    file_type: Literal["image", "video", "document", "other"] = "other"
    file_path: str = Field(default="", max_length=500)
    mime_type: str = Field(default="", max_length=100)
    file_size: int = Field(default=0, ge=0)
    remark: str = Field(default="", max_length=500)


class VideoEditJobCreate(BaseModel):
    job_title: str = Field(min_length=1, max_length=200)
    post_title: str = Field(default="", max_length=100)
    post_body: str = Field(default="", max_length=5000)
    post_tags: list[str] = Field(default_factory=list, max_length=20)
    script_text: str = Field(default="", max_length=10000)
    requirement_text: str = Field(default="", max_length=2000)
    materials: list[VideoEditMaterial] = Field(min_length=1, max_length=50)
    xhs_account_id: int = Field(default=0, ge=0)
    planned_publish_time: int = Field(default=0, ge=0)
    creation_mode: VideoCreationMode = "standard"

    @model_validator(mode="after")
    def validate_work_order(self):
        self.job_title = self.job_title.strip()
        self.post_title = self.post_title.strip() or self.job_title
        self.post_body = self.post_body.strip()
        self.post_tags = list(
            dict.fromkeys(
                tag.strip().lstrip("#")
                for tag in self.post_tags
                if tag.strip().lstrip("#")
            )
        )
        if not self.script_text.strip() and not self.requirement_text.strip():
            raise ValueError("script_text or requirement_text is required")
        if any(material.material_file_id <= 0 for material in self.materials):
            raise ValueError("all materials must come from the product library")
        return self


class VideoScriptOptimizeRequest(BaseModel):
    script_text: str = Field(min_length=1, max_length=10000)
    requirement_text: str = Field(default="", max_length=2000)
    material_file_ids: list[int] = Field(default_factory=list, max_length=50)
    adjustment: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def normalize_material_ids(self):
        self.script_text = self.script_text.strip()
        if not self.script_text:
            raise ValueError("script_text is required")
        self.requirement_text = self.requirement_text.strip()
        self.adjustment = self.adjustment.strip()
        self.material_file_ids = list(dict.fromkeys(self.material_file_ids))
        if any(material_file_id <= 0 for material_file_id in self.material_file_ids):
            raise ValueError("material_file_ids must contain positive integers")
        return self


class VideoScriptOptimizeResult(BaseModel):
    original_script: str
    optimized_script: str


class VideoEditPublishContentUpdate(BaseModel):
    post_title: str = Field(min_length=1, max_length=100)
    post_body: str = Field(default="", max_length=5000)
    post_tags: list[str] = Field(default_factory=list, max_length=20)
    review_status: VideoEditReviewStatus = "draft"

    @model_validator(mode="after")
    def normalize_publish_content(self):
        self.post_title = self.post_title.strip()
        self.post_body = self.post_body.strip()
        self.post_tags = list(
            dict.fromkeys(
                tag.strip().lstrip("#")
                for tag in self.post_tags
                if tag.strip().lstrip("#")
            )
        )
        return self


class VideoEditRevisionRequestCreate(BaseModel):
    feedback: str = Field(min_length=10, max_length=1000)
    client_request_id: str = Field(min_length=8, max_length=64)

    @model_validator(mode="after")
    def normalize_revision_request(self):
        self.feedback = self.feedback.strip()
        self.client_request_id = self.client_request_id.strip()
        if len(self.feedback) < 10:
            raise ValueError("revision feedback must contain at least 10 characters")
        if not self.client_request_id:
            raise ValueError("client_request_id is required")
        return self


class VideoEditJobClaimRequest(BaseModel):
    note: str = Field(default="", max_length=1000)


class VideoEditJobDeliverRequest(BaseModel):
    delivery_file_name: str = Field(min_length=1, max_length=255)
    delivery_file_path: str = Field(default="", max_length=500)
    delivery_url: str = Field(default="", max_length=1000)
    note: str = Field(default="", max_length=1000)


class VideoEditJobView(BaseModel):
    id: int
    tenant_id: int
    tenant_name: str
    user_id: int
    user_login_name: str
    user_nickname: str
    job_title: str
    post_title: str
    post_body: str
    post_tags: list[str]
    review_status: VideoEditReviewStatus
    script_text: str
    requirement_text: str
    materials: list[dict[str, Any]]
    xhs_account_id: int
    planned_publish_time: int
    creation_mode: VideoCreationMode
    creation_mode_label: str
    request_snapshot: dict[str, Any] = Field(default_factory=dict)
    credit_cost: int
    publish_credit_cost: int
    total_credit_cost: int
    publish_plan_id: int
    publish_item_id: int
    status: int
    status_name: VideoEditStatusName
    status_text: str
    user_progress_text: str
    expected_delivery_time: int
    sla_status: Literal["normal", "due_soon", "overdue", "completed", "returned"]
    seconds_to_delivery: int
    operator_user_id: int
    operator_name: str
    developer_note: str
    delivery: dict[str, Any]
    delivery_version_count: int
    delivery_versions: list[dict[str, Any]]
    delivery_assets: list[dict[str, Any]] = Field(default_factory=list)
    delivery_resource_counts: dict[str, int] = Field(default_factory=dict)
    revision_count: int = 0
    latest_revision_request_id: int = 0
    latest_revision_feedback: str = ""
    latest_revision_status: str = ""
    xhs_account_name: str
    delivered_time: int
    create_time: int
    update_time: int
