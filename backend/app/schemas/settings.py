from pydantic import BaseModel, ConfigDict, Field


AI_SETTING_SLOTS = {"vision", "copywriting"}


class AISettingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: str = ""
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
