import json
import sqlite3

import pytest

from app.db.connection import connect
from app.db.migrations import migrate
from app.repositories.account_repository import AccountRepository
from app.repositories.log_repository import LogRepository
from app.repositories.task_repository import TaskRepository


def migrated_connection(tmp_path):
    conn = sqlite3.connect(tmp_path / "publisher.db")
    conn.row_factory = sqlite3.Row
    migrate(conn)
    return conn


def test_task_repository_creates_and_reads_task(tmp_path):
    conn = migrated_connection(tmp_path)
    accounts = AccountRepository(conn)
    tasks = TaskRepository(conn)

    account_id = accounts.create("brand_a", "accounts/brand_a.json")
    task_id = tasks.create(
        account_id=account_id,
        task_title="亲子游路线",
        task_body="正文内容",
        tags=["亲子游", "旅行"],
        image_paths=["D:/images/1.png"],
        schedule_time=1782460800,
    )

    row = tasks.get(task_id)

    assert row is not None
    assert row["task_title"] == "亲子游路线"
    assert json.loads(row["tag_text"]) == ["亲子游", "旅行"]
    assert json.loads(row["image_path_text"]) == ["D:/images/1.png"]


def test_account_repository_lists_newest_first_and_updates_status(tmp_path):
    conn = migrated_connection(tmp_path)
    accounts = AccountRepository(conn)

    first_id = accounts.create("品牌一", "accounts/brand_1.json")
    second_id = accounts.create("品牌二", "accounts/brand_2.json")

    rows = accounts.list_all()

    assert [row["id"] for row in rows] == [second_id, first_id]

    before = accounts.get(first_id)
    assert before is not None
    assert before["last_checked_time"] == 0

    accounts.update_status(first_id, 2)
    updated = accounts.get(first_id)

    assert updated is not None
    assert updated["status"] == 2
    assert updated["last_checked_time"] > 0
    assert updated["update_time"] > 0


def test_task_repository_lists_newest_first_and_persists_status_error(tmp_path):
    conn = migrated_connection(tmp_path)
    accounts = AccountRepository(conn)
    tasks = TaskRepository(conn)

    account_id = accounts.create("品牌一", "accounts/brand_1.json")
    first_id = tasks.create(
        account_id=account_id,
        task_title="第一篇",
        task_body="正文一",
        tags=["种草"],
        image_paths=["D:/images/1.png"],
        schedule_time=1782460800,
    )
    second_id = tasks.create(
        account_id=account_id,
        task_title="第二篇",
        task_body="正文二",
        tags=["旅行"],
        image_paths=["D:/images/2.png"],
        schedule_time=1782547200,
    )

    rows = tasks.list_all()

    assert [row["id"] for row in rows] == [second_id, first_id]

    tasks.set_status(first_id, 6, last_error="失败原因")
    updated = tasks.get(first_id)

    assert updated is not None
    assert updated["status"] == 6
    assert updated["last_error"] == "失败原因"


def test_log_repository_appends_and_lists_logs_oldest_first(tmp_path):
    conn = migrated_connection(tmp_path)
    accounts = AccountRepository(conn)
    tasks = TaskRepository(conn)
    logs = LogRepository(conn)

    account_id = accounts.create("品牌一", "accounts/brand_1.json")
    task_id = tasks.create(
        account_id=account_id,
        task_title="发布记录",
        task_body="正文",
        tags=["记录"],
        image_paths=["D:/images/1.png"],
        schedule_time=1782460800,
    )

    first_log_id = logs.append(task_id, "INFO", "开始发布", "")
    second_log_id = logs.append(task_id, "ERROR", "发布失败", "screenshots/fail.png")

    rows = logs.list_by_task(task_id)

    assert [row["id"] for row in rows] == [first_log_id, second_log_id]
    assert [(row["log_level"], row["log_message"], row["screenshot_path"]) for row in rows] == [
        ("INFO", "开始发布", ""),
        ("ERROR", "发布失败", "screenshots/fail.png"),
    ]


def test_task_repository_enforces_account_foreign_key(tmp_path):
    conn = connect(tmp_path / "publisher.db")
    migrate(conn)
    tasks = TaskRepository(conn)

    with pytest.raises(sqlite3.IntegrityError):
        tasks.create(
            account_id=999,
            task_title="无账号任务",
            task_body="正文",
            tags=["异常"],
            image_paths=["D:/images/1.png"],
            schedule_time=1782460800,
        )
