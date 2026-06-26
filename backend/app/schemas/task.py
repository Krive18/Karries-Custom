from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    account_id: int
    task_title: str = ""
    task_body: str = ""
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    schedule_time: int


class TaskView(TaskCreate):
    id: int
    status: int
    last_error: str
    submitted_time: int
    create_time: int
    update_time: int
