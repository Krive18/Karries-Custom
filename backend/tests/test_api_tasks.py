from contextlib import contextmanager
import time
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.main import create_app


class SharedMysqlConnection:
    def __init__(self, conn):
        self.conn = conn
        self.closed_by_app = False

    def cursor(self):
        return self.conn.cursor()

    def commit(self):
        return self.conn.commit()

    def rollback(self):
        return self.conn.rollback()

    def close(self):
        self.closed_by_app = True

    @property
    def open(self):
        return self.conn.open


@contextmanager
def mysql_client(monkeypatch, mysql_conn):
    shared_conn = SharedMysqlConnection(mysql_conn)
    monkeypatch.setattr("app.main.connect", lambda _config: shared_conn)
    with TestClient(create_app()) as client:
        yield client
    assert shared_conn.closed_by_app is True


def test_account_and_task_api_create_and_list(tmp_path, monkeypatch, mysql_conn):
    with mysql_client(monkeypatch, mysql_conn) as client:
        account_response = client.post(
            "/api/accounts",
            json={"account_name": "brand_a", "cookie_path": "accounts/brand_a.json"},
        )

        assert account_response.status_code == 200
        account_payload = account_response.json()
        assert account_payload["success"] is True
        account_id = account_payload["data"]["id"]
        assert account_id

        image_path = tmp_path / "note.png"
        image_path.write_bytes(b"image")
        task_title = "Travel plan"

        task_response = client.post(
            "/api/tasks",
            json={
                "account_id": account_id,
                "task_title": task_title,
                "task_body": "Body text",
                "tags": ["travel", "family"],
                "image_paths": [str(image_path)],
                "schedule_time": int(time.time()) + 2 * 3600 + 60,
            },
        )

        assert task_response.status_code == 200
        task_payload = task_response.json()
        assert task_payload["success"] is True
        assert task_payload["data"]["task_title"] == task_title

        accounts_response = client.get("/api/accounts")
        assert accounts_response.status_code == 200
        accounts_payload = accounts_response.json()
        assert accounts_payload["success"] is True
        assert [account["id"] for account in accounts_payload["data"]] == [account_id]

        tasks_response = client.get("/api/tasks")
        assert tasks_response.status_code == 200
        tasks_payload = tasks_response.json()
        assert tasks_payload["success"] is True
        assert [task["task_title"] for task in tasks_payload["data"]] == [task_title]


def test_create_account_returns_unified_error_for_duplicate_name(tmp_path, monkeypatch, mysql_conn):
    payload = {"account_name": "brand_a", "cookie_path": "accounts/brand_a.json"}

    with mysql_client(monkeypatch, mysql_conn) as client:
        first_response = client.post("/api/accounts", json=payload)
        second_response = client.post("/api/accounts", json=payload)

        assert first_response.status_code == 200
        assert second_response.status_code == 400
        second_payload = second_response.json()
        assert second_payload["success"] is False
        assert second_payload["data"] is None
        assert second_payload["error"]["code"] == "DATABASE_CONSTRAINT"
        assert client.app.state.conn.open is True


def test_create_task_returns_unified_error_for_missing_account(tmp_path, monkeypatch, mysql_conn):
    image_path = tmp_path / "note.png"
    image_path.write_bytes(b"image")

    with mysql_client(monkeypatch, mysql_conn) as client:
        response = client.post(
            "/api/tasks",
            json={
                "account_id": 999,
                "task_title": "Travel plan",
                "task_body": "Body text",
                "tags": ["travel"],
                "image_paths": [str(image_path)],
                "schedule_time": int(time.time()) + 2 * 3600 + 60,
            },
        )

        assert response.status_code == 400
        payload = response.json()
        assert payload["success"] is False
        assert payload["data"] is None
        assert payload["error"]["code"] == "DATABASE_CONSTRAINT"


def test_submit_task_api_marks_task_submitted(tmp_path, monkeypatch, mysql_conn):
    monkeypatch.setattr("app.workers.publish_worker.submit_note", AsyncMock(return_value=None))

    with mysql_client(monkeypatch, mysql_conn) as client:
        account_response = client.post(
            "/api/accounts",
            json={"account_name": "brand_a", "cookie_path": "accounts/brand_a.json"},
        )
        account_id = account_response.json()["data"]["id"]
        image_path = tmp_path / "note.png"
        image_path.write_bytes(b"image")
        task_response = client.post(
            "/api/tasks",
            json={
                "account_id": account_id,
                "task_title": "Travel plan",
                "task_body": "Body text",
                "tags": ["travel"],
                "image_paths": [str(image_path)],
                "schedule_time": int(time.time()) + 2 * 3600 + 60,
            },
        )
        task_id = task_response.json()["data"]["id"]

        submit_response = client.post(f"/api/tasks/{task_id}/submit")

        assert submit_response.status_code == 200
        payload = submit_response.json()
        assert payload["success"] is True
        assert payload["data"]["status"] == 5
        assert payload["data"]["submitted_time"] > 0


def test_submit_task_api_returns_publish_failed_for_platform_value_error(tmp_path, monkeypatch, mysql_conn):
    monkeypatch.setattr(
        "app.workers.publish_worker.submit_note",
        AsyncMock(side_effect=ValueError("定时时间过近")),
    )

    with mysql_client(monkeypatch, mysql_conn) as client:
        account_response = client.post(
            "/api/accounts",
            json={"account_name": "brand_a", "cookie_path": "accounts/brand_a.json"},
        )
        account_id = account_response.json()["data"]["id"]
        image_path = tmp_path / "note.png"
        image_path.write_bytes(b"image")
        task_response = client.post(
            "/api/tasks",
            json={
                "account_id": account_id,
                "task_title": "Travel plan",
                "task_body": "Body text",
                "tags": ["travel"],
                "image_paths": [str(image_path)],
                "schedule_time": int(time.time()) + 2 * 3600 + 60,
            },
        )
        task_id = task_response.json()["data"]["id"]

        submit_response = client.post(f"/api/tasks/{task_id}/submit")

        assert submit_response.status_code == 500
        submit_payload = submit_response.json()
        assert submit_payload["success"] is False
        assert submit_payload["error"]["code"] == "PUBLISH_FAILED"
        assert "定时时间过近" in submit_payload["error"]["message"]

        tasks_response = client.get("/api/tasks")
        task_payload = tasks_response.json()["data"][0]
        assert task_payload["status"] == 6
        assert "定时时间过近" in task_payload["last_error"]
