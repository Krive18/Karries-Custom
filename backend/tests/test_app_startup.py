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


class FakeCursor:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def execute(self, statement):
        self.statements.append(statement)


class ReadyConnection(FakeConnection):
    def __init__(self):
        super().__init__()
        self.ready_cursor = FakeCursor()

    def cursor(self):
        return self.ready_cursor


def route_paths(app):
    paths = set()

    def collect(routes):
        for route in routes:
            path = getattr(route, "path", None)
            if path:
                paths.add(path)
                continue

            router = getattr(route, "original_router", None)
            if router is not None:
                collect(router.routes)

    collect(app.routes)
    return paths


def test_health_endpoint_returns_success(monkeypatch):
    fake_conn = FakeConnection()
    monkeypatch.setattr("app.main.connect", lambda _config: fake_conn)
    monkeypatch.setattr("app.main.migrate", lambda _conn: None)

    with TestClient(create_app()) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"status": "ok"}, "error": None}
    assert fake_conn.closed is True


def test_health_endpoint_returns_request_id(monkeypatch):
    fake_conn = FakeConnection()
    monkeypatch.setattr("app.main.connect", lambda _config: fake_conn)
    monkeypatch.setattr("app.main.migrate", lambda _conn: None)

    with TestClient(create_app()) as client:
        response = client.get("/api/health", headers={"X-Request-ID": "trace-123"})

    assert response.headers["X-Request-ID"] == "trace-123"


def test_readiness_endpoint_checks_database(monkeypatch):
    lifespan_conn = FakeConnection()
    ready_conn = ReadyConnection()
    monkeypatch.setattr("app.main.connect", lambda _config: lifespan_conn)
    monkeypatch.setattr("app.main.migrate", lambda _conn: None)
    app = create_app()
    app.state.connect_db = lambda: ready_conn

    with TestClient(app) as client:
        response = client.get("/api/ready")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ready"}
    assert ready_conn.ready_cursor.statements == ["select 1"]
    assert ready_conn.closed is True


def test_readiness_endpoint_returns_503_when_database_is_unavailable(monkeypatch):
    lifespan_conn = FakeConnection()
    monkeypatch.setattr("app.main.connect", lambda _config: lifespan_conn)
    monkeypatch.setattr("app.main.migrate", lambda _conn: None)
    app = create_app()
    app.state.connect_db = lambda: (_ for _ in ()).throw(RuntimeError("db secret"))

    with TestClient(app) as client:
        response = client.get("/api/ready")

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "SERVICE_UNAVAILABLE",
        "message": "数据库暂不可用",
    }


def test_app_closes_database_connection_on_shutdown(monkeypatch):
    fake_conn = FakeConnection()
    monkeypatch.setattr("app.main.connect", lambda _config: fake_conn)
    monkeypatch.setattr("app.main.migrate", lambda _conn: None)

    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200

    assert fake_conn.closed is True


def test_app_starts_and_retries_when_database_is_initially_unavailable(monkeypatch):
    fake_conn = FakeConnection()
    attempts = 0

    def fail_migrate(_conn):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("migration failed")

    monkeypatch.setattr("app.main.connect", lambda _config: fake_conn)
    monkeypatch.setattr("app.main.migrate", fail_migrate)
    monkeypatch.setenv("MYSQL_RECONNECT_RETRY_SECONDS", "0")

    with TestClient(create_app()) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert attempts >= 2
    assert fake_conn.closed is True


def test_customer_surface_does_not_register_internal_routes():
    paths = route_paths(create_app("customer"))

    assert "/api/inspiration/sessions" in paths
    assert "/api/admin/summary" not in paths
    assert "/api/admin/inspiration/sessions" not in paths
    assert "/api/settings/ai" not in paths
    assert "/api/developer/viral-analysis/jobs" not in paths
    assert "/api/internal/video-edit/jobs" not in paths
    assert "/api/worker/matrix-publish-items/claim" not in paths
    assert "/api/auth/register" not in paths


def test_customer_surface_registers_worker_route_for_embedded_worker(monkeypatch):
    monkeypatch.setenv("XHS_EMBEDDED_PUBLISH_WORKER", "1")

    paths = route_paths(create_app("customer"))

    assert "/api/worker/matrix-publish-items/claim" in paths
    assert "/api/settings/ai" not in paths
    assert "/api/developer/viral-analysis/jobs" not in paths


def test_manager_surface_only_registers_management_business_routes():
    paths = route_paths(create_app("manager"))

    assert "/api/admin/summary" in paths
    assert "/api/admin/users" in paths
    assert "/api/admin/inspiration/sessions" in paths
    assert "/api/admin/viral-analysis/jobs" in paths
    assert "/api/inspiration/sessions" not in paths
    assert "/api/settings/ai" not in paths
    assert "/api/auth/register" not in paths


def test_developer_surface_only_registers_internal_business_routes():
    paths = route_paths(create_app("developer"))

    assert "/api/settings/ai" in paths
    assert "/api/developer/viral-analysis/jobs" in paths
    assert "/api/internal/video-edit/jobs" in paths
    assert "/api/worker/matrix-publish-items/claim" in paths
    assert "/api/inspiration/sessions" not in paths
    assert "/api/viral-analysis/jobs" not in paths
    assert "/api/tasks" not in paths
    assert "/api/auth/register" not in paths


def test_all_surface_keeps_hidden_bootstrap_registration():
    paths = route_paths(create_app("all"))

    assert "/api/auth/register" in paths
