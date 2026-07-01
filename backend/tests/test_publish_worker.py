import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from app.repositories.account_repository import AccountRepository
from app.repositories.log_repository import LogRepository
from app.repositories.task_repository import TaskRepository
from app.workers.publish_worker import PublishWorker


def make_publish_context(mysql_conn, tmp_path):
    accounts = AccountRepository(mysql_conn)
    tasks = TaskRepository(mysql_conn)
    logs = LogRepository(mysql_conn)
    account_id = accounts.create("brand_a", str(tmp_path / "brand.json"))
    task_id = tasks.create(
        account_id=account_id,
        task_title="标题",
        task_body="正文",
        tags=["旅行"],
        image_paths=[str(tmp_path / "a.png")],
        schedule_time=int(time.time()) + 3 * 3600,
    )
    return mysql_conn, tasks, logs, task_id


def test_worker_marks_task_submitted(monkeypatch, tmp_path, mysql_conn):
    conn, tasks, logs, task_id = make_publish_context(mysql_conn, tmp_path)
    monkeypatch.setattr("app.workers.publish_worker.submit_note", AsyncMock(return_value=None))

    worker = PublishWorker(conn)
    asyncio.run(worker.submit(task_id))

    row = tasks.get(task_id)
    assert row["status"] == 5
    assert row["submitted_time"] > 0
    log_rows = logs.list_by_task(task_id)
    assert any("提交成功" in item["log_message"] for item in log_rows)


def test_worker_marks_task_failed_when_submit_raises(monkeypatch, tmp_path, mysql_conn):
    conn, tasks, logs, task_id = make_publish_context(mysql_conn, tmp_path)
    monkeypatch.setattr(
        "app.workers.publish_worker.submit_note",
        AsyncMock(side_effect=RuntimeError("平台提交失败")),
    )

    worker = PublishWorker(conn)
    with pytest.raises(RuntimeError, match="平台提交失败"):
        asyncio.run(worker.submit(task_id))

    row = tasks.get(task_id)
    assert row["status"] == 6
    assert "平台提交失败" in row["last_error"]
    log_rows = logs.list_by_task(task_id)
    assert any(item["log_level"] == "ERROR" and "提交失败" in item["log_message"] for item in log_rows)
