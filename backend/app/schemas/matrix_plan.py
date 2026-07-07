from typing import Literal

from pydantic import BaseModel, Field


class MatrixPlanCreate(BaseModel):
    plan_name: str = Field(min_length=1, max_length=200)
    source_type: Literal["product", "temporary_material"] = "product"
    content_type: Literal["image_text"] = "image_text"
    product_id: int = Field(default=0, ge=0)
    xhs_account_ids: list[int] = Field(min_length=1)
    schedule_start_time: int = Field(ge=0)
    schedule_end_time: int = Field(ge=0)
    items_per_account: int = Field(default=1, ge=1, le=50)
    min_interval_minutes: int = Field(default=360, ge=1, le=1440)
