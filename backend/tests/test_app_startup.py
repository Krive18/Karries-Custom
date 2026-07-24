from fastapi.testclient import TestClient

from app.main import create_app


class FakeConnection:
    def __init__(self):
        self.closed = False
        self.rolled_back = False

    def close(self):
        self.closed = True

    def rollback(self):
        self.rolled_back = True


def route_paths(app):
    return {route.path for route in app.routes}


def test_health_endpoint_returns_success(monkeypatch):
    fake_conn = FakeConnection()
    monkeypatch.setattr("app.main.connect", lambda _config: fake_conn)
    monkeypatch.setattr("app.main.migrate", lambda _conn: None)

    with TestClient(create_app()) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"status": "ok"}, "error": None}
    assert fake_conn.closed is True


def test_app_closes_database_connection_on_shutdown(monkeypatch):
    fake_conn = FakeConnection()
    monkeypatch.setattr("app.main.connect", lambda _config: fake_conn)
    monkeypatch.setattr("app.main.migrate", lambda _conn: None)

    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200

    assert fake_conn.closed is True


def test_app_closes_database_connection_when_migration_fails(monkeypatch):
    fake_conn = FakeConnection()

    def fail_migrate(_conn):
        raise RuntimeError("migration failed")

    monkeypatch.setattr("app.main.connect", lambda _config: fake_conn)
    monkeypatch.setattr("app.main.migrate", fail_migrate)

    try:
        with TestClient(create_app()):
            pass
    except RuntimeError as exc:
        assert str(exc) == "migration failed"
    else:
        raise AssertionError("migration failure should bubble up")

    assert fake_conn.closed is True


def test_customer_surface_does_not_register_internal_routes():
    paths = route_paths(create_app("customer"))

    assert "/api/inspiration/sessions" in paths
    assert "/api/settings/ai" not in paths
    assert "/api/developer/viral-analysis/jobs" not in paths
    assert "/api/internal/video-edit/jobs" not in paths
    assert "/api/worker/matrix-publish-items/claim" not in paths


def test_developer_surface_only_registers_internal_business_routes():
    paths = route_paths(create_app("developer"))

    assert "/api/settings/ai" in paths
    assert "/api/developer/viral-analysis/jobs" in paths
    assert "/api/internal/video-edit/jobs" in paths
    assert "/api/worker/matrix-publish-items/claim" in paths
    assert "/api/inspiration/sessions" not in paths
    assert "/api/viral-analysis/jobs" not in paths
    assert "/api/tasks" not in paths
