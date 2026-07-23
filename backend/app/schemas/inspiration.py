from typing import Literal

from pydantic import BaseModel, Field


GoalType = Literal["topic", "title", "body", "script", "strategy", "optimize"]
SessionStatus = Literal["active", "archived"]


class InspirationSessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    linked_product_id: int = Field(default=0, ge=0)
    linked_xhs_account_id: int = Field(default=0, ge=0)
    goal_type: GoalType = "topic"
    tone: str = Field(default="自然真诚", max_length=100)
    extra_requirement: str = Field(default="", max_length=1000)


class InspirationMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
