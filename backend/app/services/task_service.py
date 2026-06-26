import time
from pathlib import Path

from app.schemas.task import TaskCreate


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_TITLE_LENGTH = 20
MAX_TAG_COUNT = 10
MIN_SCHEDULE_LEAD_SECONDS = 2 * 3600


def validate_task_create(payload: TaskCreate) -> None:
    title = payload.task_title.strip()
    if not title:
        raise ValueError("标题不能为空")

    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError("标题最多 20 个字符")

    if len(payload.tags) > MAX_TAG_COUNT:
        raise ValueError("标签最多 10 个")

    if not payload.image_paths:
        raise ValueError("至少选择 1 张图片")

    for image_path in payload.image_paths:
        path = Path(image_path)
        if not path.exists():
            raise ValueError(f"图片不存在: {image_path}")
        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(f"不支持的图片格式: {path.suffix}")

    if payload.schedule_time <= int(time.time()) + MIN_SCHEDULE_LEAD_SECONDS:
        raise ValueError("发布时间必须至少晚于当前时间 2 小时")
