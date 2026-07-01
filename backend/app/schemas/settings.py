from pydantic import BaseModel, Field


AI_SETTING_SLOTS = {"vision", "copywriting"}


class AISettingUpdate(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    api_key: str = ""
    base_url: str = Field(min_length=1, max_length=500)
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
