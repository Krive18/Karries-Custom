import time

from fastapi.testclient import TestClient

from app.main import create_app


def test_account_and_task_api_create_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("XHS_PUBLISHER_DATA_DIR", str(tmp_path))
    client = TestClient(create_app())

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


def test_create_account_returns_unified_error_for_duplicate_name(tmp_path, monkeypatch):
    monkeypatch.setenv("XHS_PUBLISHER_DATA_DIR", str(tmp_path))
    client = TestClient(create_app())
    payload = {"account_name": "brand_a", "cookie_path": "accounts/brand_a.json"}

    first_response = client.post("/api/accounts", json=payload)
    second_response = client.post("/api/accounts", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 400
    second_payload = second_response.json()
    assert second_payload["success"] is False
    assert second_payload["data"] is None
    assert second_payload["error"]["code"] == "DATABASE_CONSTRAINT"
    assert client.app.state.conn.in_transaction is False


def test_create_task_returns_unified_error_for_missing_account(tmp_path, monkeypatch):
    monkeypatch.setenv("XHS_PUBLISHER_DATA_DIR", str(tmp_path))
    client = TestClient(create_app())
    image_path = tmp_path / "note.png"
    image_path.write_bytes(b"image")

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
