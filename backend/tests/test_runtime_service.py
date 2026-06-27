from fastapi.testclient import TestClient

from app.main import create_app
from app.runtime.browser_runtime import mark_browser_installed
from app.services.runtime_service import check_runtime


def test_runtime_check_reports_browser_missing(tmp_path):
    result = check_runtime(tmp_path)

    assert result["browser_installed"] is False
    assert result["runtime_dir"] == str(tmp_path)
    assert result["browser_marker"] == str(tmp_path / "patchright-chromium-installed.txt")


def test_runtime_check_reports_browser_installed_after_marker_created(tmp_path):
    marker = mark_browser_installed(tmp_path)

    result = check_runtime(tmp_path)

    assert marker.exists()
    assert result["browser_installed"] is True


def test_runtime_api_check_and_install_browser(tmp_path, monkeypatch):
    monkeypatch.setenv("XHS_PUBLISHER_DATA_DIR", str(tmp_path / "data"))
    app = create_app()
    app.state.config.runtime_dir = tmp_path / "runtime"
    client = TestClient(app)

    check_response = client.get("/api/runtime/check")
    install_response = client.post("/api/runtime/install-browser")
    second_check_response = client.get("/api/runtime/check")

    assert check_response.status_code == 200
    assert check_response.json()["data"]["browser_installed"] is False
    assert install_response.status_code == 200
    assert install_response.json()["data"]["marker"] == str(
        tmp_path / "runtime" / "patchright-chromium-installed.txt"
    )
    assert second_check_response.status_code == 200
    assert second_check_response.json()["data"]["browser_installed"] is True
