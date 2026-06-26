import re
import time

import pytest

from app.schemas.task import TaskCreate
from app.services.task_service import validate_task_create


def make_payload(tmp_path, **overrides):
    image_path = tmp_path / "note.png"
    image_path.write_bytes(b"image")
    data = {
        "account_id": 1,
        "task_title": "亲子游路线",
        "task_body": "正文内容",
        "tags": ["亲子游", "旅行"],
        "image_paths": [str(image_path)],
        "schedule_time": int(time.time()) + 2 * 3600 + 60,
    }
    data.update(overrides)
    return TaskCreate(**data)


def assert_validation_error(payload, message):
    with pytest.raises(ValueError, match=re.escape(message)):
        validate_task_create(payload)


def test_validate_task_create_rejects_empty_title(tmp_path):
    payload = make_payload(tmp_path, task_title="   ")

    assert_validation_error(payload, "标题不能为空")


def test_validate_task_create_rejects_schedule_time_with_less_than_two_hours_lead(tmp_path):
    payload = make_payload(tmp_path, schedule_time=int(time.time()) + 2 * 3600)

    assert_validation_error(payload, "发布时间必须至少晚于当前时间 2 小时")


def test_validate_task_create_accepts_valid_payload(tmp_path):
    payload = make_payload(tmp_path)

    validate_task_create(payload)


def test_validate_task_create_rejects_title_longer_than_twenty_chars(tmp_path):
    payload = make_payload(tmp_path, task_title="一" * 21)

    assert_validation_error(payload, "标题最多 20 个字符")


def test_validate_task_create_rejects_more_than_ten_tags(tmp_path):
    payload = make_payload(tmp_path, tags=[f"tag{i}" for i in range(11)])

    assert_validation_error(payload, "标签最多 10 个")


def test_validate_task_create_rejects_missing_images(tmp_path):
    payload = make_payload(tmp_path, image_paths=[])

    assert_validation_error(payload, "至少选择 1 张图片")


def test_validate_task_create_rejects_nonexistent_image(tmp_path):
    missing_path = tmp_path / "missing.png"
    payload = make_payload(tmp_path, image_paths=[str(missing_path)])

    assert_validation_error(payload, f"图片不存在: {missing_path}")


def test_validate_task_create_rejects_unsupported_image_extension(tmp_path):
    image_path = tmp_path / "note.gif"
    image_path.write_bytes(b"image")
    payload = make_payload(tmp_path, image_paths=[str(image_path)])

    assert_validation_error(payload, "不支持的图片格式: .gif")
