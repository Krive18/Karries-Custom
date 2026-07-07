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
