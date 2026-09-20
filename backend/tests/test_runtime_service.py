from app.runtime.browser_runtime import mark_browser_installed
from app.services.runtime_service import check_runtime


def test_runtime_check_reports_browser_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.runtime_service.resolve_browser_executable_path",
        lambda: "",
    )
    result = check_runtime(tmp_path)

    assert result["browser_installed"] is False
    assert result["browser_executable"] == ""
    assert result["runtime_dir"] == str(tmp_path)
    assert result["browser_marker"] == str(tmp_path / "patchright-chromium-installed.txt")


def test_runtime_check_reports_browser_installed_after_marker_created(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.runtime_service.resolve_browser_executable_path",
        lambda: "",
    )
    marker = mark_browser_installed(tmp_path)

    result = check_runtime(tmp_path)

    assert marker.exists()
    assert result["browser_installed"] is True


def test_runtime_check_reports_detected_system_browser(tmp_path, monkeypatch):
    browser_path = tmp_path / "msedge.exe"
    browser_path.write_bytes(b"edge")
    monkeypatch.setattr(
        "app.services.runtime_service.resolve_browser_executable_path",
        lambda: str(browser_path),
    )

    result = check_runtime(tmp_path)

    assert result["browser_installed"] is True
    assert result["browser_executable"] == str(browser_path)


def test_runtime_check_keeps_endpoint_available_when_browser_detection_fails(
    tmp_path,
    monkeypatch,
):
    def fail_detection():
        raise RuntimeError("browser detection failed")

    monkeypatch.setattr(
        "app.services.runtime_service.resolve_browser_executable_path",
        fail_detection,
    )

    result = check_runtime(tmp_path)

    assert result["browser_installed"] is False
    assert result["browser_executable"] == ""
    assert result["browser_detection_error"] == "RuntimeError: browser detection failed"


def test_runtime_api_check_and_install_browser(
    tmp_path,
    app_client_without_db,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.runtime_service.resolve_browser_executable_path",
        lambda: "",
    )
    client = app_client_without_db
    client.app.state.config.runtime_dir = tmp_path / "runtime"

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
