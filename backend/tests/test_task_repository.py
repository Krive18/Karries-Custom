import json
import sqlite3

from app.db.migrations import migrate
from app.repositories.account_repository import AccountRepository
from app.repositories.task_repository import TaskRepository


def test_task_repository_creates_and_reads_task(tmp_path):
    conn = sqlite3.connect(tmp_path / "publisher.db")
    conn.row_factory = sqlite3.Row
    migrate(conn)
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
