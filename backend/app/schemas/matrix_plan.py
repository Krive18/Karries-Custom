from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _normalize_schedule_aliases(data: Any) -> Any:
    if not isinstance(data, dict):
        return data

    normalized = dict(data)
    if "schedule_start_time" not in normalized and "schedule_start" in normalized:
        normalized["schedule_start_time"] = normalized["schedule_start"]
    if "schedule_end_time" not in normalized and "schedule_end" in normalized:
        normalized["schedule_end_time"] = normalized["schedule_end"]
    return normalized


class MatrixPlanCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    plan_name: str = Field(min_length=1, max_length=200)
    source_type: Literal["product", "temporary_material"] = "product"
    content_type: Literal["image_text"] = "image_text"
    product_id: int = Field(default=0, ge=0)
    xhs_account_ids: list[int] = Field(min_length=1)
    schedule_start_time: int = Field(ge=0)
    schedule_end_time: int = Field(ge=0)
    items_per_account: int = Field(default=1, ge=1, le=50)
    min_interval_minutes: int = Field(default=360, ge=1, le=1440)

    @model_validator(mode="before")
    @classmethod
    def normalize_schedule_aliases(cls, data: Any) -> Any:
        return _normalize_schedule_aliases(data)


class MatrixPlanFromDraftsCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    plan_name: str = Field(min_length=1, max_length=200)
    draft_ids: list[int] = Field(min_length=1, max_length=50)
    xhs_account_ids: list[int] = Field(min_length=1, max_length=100)
    schedule_start_time: int = Field(ge=0)
    schedule_end_time: int = Field(ge=0)
    min_interval_minutes: int = Field(default=360, ge=1, le=1440)

    @model_validator(mode="before")
    @classmethod
    def normalize_schedule_aliases(cls, data: Any) -> Any:
        return _normalize_schedule_aliases(data)


class MatrixPlanActionResult(BaseModel):
    id: int
    status: int
    item_count: int = 0
    cancelled_item_count: int = 0


class MatrixPlanDetail(BaseModel):
    id: int
    user_id: int
    plan_name: str
    source_type: str
    content_type: str
    product_id: int
    status: int
    schedule_start_time: int
    schedule_end_time: int
    scheduling_rule: dict[str, Any]
    item_count: int
    create_time: int
    update_time: int


class MatrixPlanItemDetail(BaseModel):
    id: int
    plan_id: int
    xhs_account_id: int
    content_type: str
    title: str
    body: str
    tags: list[str]
    material: dict[str, Any]
    scheduled_time: int
    status: int
    last_error: str
    attempt_count: int
    max_attempts: int
    next_retry_time: int
    submitted_time: int
    publish_result: dict[str, Any]
    content_fingerprint: str
    create_time: int
    update_time: int


class WorkerClaimRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)
    now_time: int | None = Field(default=None, ge=0)


class WorkerClaimedItem(BaseModel):
    id: int
    plan_id: int
    user_id: int
    xhs_account_id: int
    lease_token: str
    lease_expires_time: int
    attempt_count: int
    max_attempts: int
    login_state_path: str
    content_type: str
    title: str
    body: str
    tags: list[str]
    material: dict[str, Any]
    scheduled_time: int


class WorkerClaimResponse(BaseModel):
    items: list[WorkerClaimedItem]


class WorkerItemSuccessRequest(BaseModel):
    lease_token: str = Field(min_length=1, max_length=64)
    message: str = Field(default="", max_length=1000)
    result_data: dict[str, Any] = Field(default_factory=dict)


class WorkerItemFailRequest(BaseModel):
    lease_token: str = Field(min_length=1, max_length=64)
    error_message: str = Field(min_length=1, max_length=1000)
    retryable: bool = False
    retry_delay_seconds: int = Field(default=60, ge=5, le=3600)


class WorkerItemManualTakeoverRequest(BaseModel):
    lease_token: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=1000)
    invalidate_account_login: bool = False
    mark_account_risk: bool = False
