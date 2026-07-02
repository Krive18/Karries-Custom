from pydantic import BaseModel, Field


class XHSAccountProfile(BaseModel):
    domain_name: str = Field(default="", max_length=100)
    persona: str = Field(default="", max_length=100)
    target_audience: str = Field(default="", max_length=200)
    content_style: str = Field(default="", max_length=200)
    tone: str = Field(default="", max_length=100)
    common_phrases: str = Field(default="", max_length=1000)
    forbidden_phrases: str = Field(default="", max_length=1000)
    tag_preferences: str = Field(default="[]", max_length=1000)
    word_count_preference: int = Field(default=300, ge=50, le=2000)
    topic_preferences: str = Field(default="", max_length=1000)


class XHSAccountProfileUpdate(BaseModel):
    domain_name: str = Field(default=None, max_length=100)
    persona: str = Field(default=None, max_length=100)
    target_audience: str = Field(default=None, max_length=200)
    content_style: str = Field(default=None, max_length=200)
    tone: str = Field(default=None, max_length=100)
    common_phrases: str = Field(default=None, max_length=1000)
    forbidden_phrases: str = Field(default=None, max_length=1000)
    tag_preferences: str = Field(default=None, max_length=1000)
    word_count_preference: int = Field(default=None, ge=50, le=2000)
    topic_preferences: str = Field(default=None, max_length=1000)


class XHSAccountCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    account_group: str = Field(default="", max_length=100)
    daily_limit: int = Field(default=1, ge=1, le=20)
    min_interval_minutes: int = Field(default=360, ge=30, le=1440)
    profile: XHSAccountProfile = Field(default_factory=XHSAccountProfile)
