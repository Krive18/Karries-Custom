from fastapi.testclient import TestClient
import pytest
import sqlite3

from app.main import create_app


def test_health_endpoint_returns_success():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"status": "ok"}, "error": None}


def test_app_closes_database_connection_on_shutdown(tmp_path, monkeypatch):
    monkeypatch.setenv("XHS_PUBLISHER_DATA_DIR", str(tmp_path))
    app = create_app()
    conn = app.state.conn

    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("select 1")
