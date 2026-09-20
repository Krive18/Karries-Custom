from pydantic import BaseModel, Field, model_validator


class AdminNotificationCreate(BaseModel):
    recipient_user_ids: list[int] = Field(default_factory=list, max_length=100)
    notification_type: str = Field(default="task", pattern="^(task|announcement|system)$")
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)
    priority: int = Field(default=1, ge=1, le=3)
    action_path: str = Field(default="", max_length=300)
    business_type: str = Field(default="", max_length=50)
    business_id: int = Field(default=0, ge=0)
    deadline_time: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def normalize_text(self):
        self.title = self.title.strip()
        self.content = self.content.strip()
        self.recipient_user_ids = sorted(set(self.recipient_user_ids))
        if not self.title or not self.content:
            raise ValueError("title and content are required")
        return self
