from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class MatrixPlanCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    plan_name: str = Field(min_length=1, max_length=200)
    source_type: Literal["product", "temporary_material"] = "product"
    content_type: Literal["image_text"] = "image_text"
    product_id: int = Field(default=0, ge=0)
    xhs_account_ids: list[int] = Field(min_length=1)
    schedule_start_time: int = Field(
        validation_alias=AliasChoices("schedule_start_time", "schedule_start"),
        ge=0,
    )
    schedule_end_time: int = Field(
        validation_alias=AliasChoices("schedule_end_time", "schedule_end"),
        ge=0,
    )
    items_per_account: int = Field(default=1, ge=1, le=50)
    min_interval_minutes: int = Field(default=360, ge=1, le=1440)
