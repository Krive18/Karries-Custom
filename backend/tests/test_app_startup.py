from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_success():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"status": "ok"}, "error": None}
