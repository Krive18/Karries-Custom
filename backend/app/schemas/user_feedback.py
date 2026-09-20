from typing import Literal

from pydantic import BaseModel, Field, model_validator


FeedbackCategory = Literal["bug", "feature", "experience", "other"]
FeedbackStatus = Literal["pending", "in_progress", "completed"]


class UserFeedbackCreate(BaseModel):
    category: FeedbackCategory
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=10, max_length=5000)

    @model_validator(mode="after")
    def normalize_content(self):
        self.title = self.title.strip()
        self.description = self.description.strip()
        if len(self.title) < 2:
            raise ValueError("title must contain at least 2 characters")
        if len(self.description) < 10:
            raise ValueError("description must contain at least 10 characters")
        return self


class DeveloperFeedbackUpdate(BaseModel):
    status: FeedbackStatus
    developer_reply: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def normalize_reply(self):
        self.developer_reply = self.developer_reply.strip()
        if self.status == "completed" and len(self.developer_reply) < 2:
            raise ValueError("developer_reply is required when completing feedback")
        return self

