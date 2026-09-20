from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AI_SETTING_SLOTS = {"vision", "copywriting", "pro_copywriting"}


class AISettingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(default="", max_length=512)
    model: str = Field(min_length=1, max_length=100)
    enabled: bool = True


class AISettingView(BaseModel):
    provider: str
    base_url: str
    model: str
    enabled: bool
    has_key: bool
    masked_key: str


class AISettingsView(BaseModel):
    vision: AISettingView
    copywriting: AISettingView
    pro_copywriting: AISettingView


class AISettingConnectionTestResult(BaseModel):
    success: bool = True
    slot: Literal["vision", "copywriting", "pro_copywriting"]
    provider: str
    model: str
    request_id: str = ""
    latency_ms: int = Field(ge=0)
