from pathlib import Path

from app.integrations.xiaohongshu import resolve_browser_executable_path
from app.runtime.browser_runtime import BROWSER_MARKER_NAME


def check_runtime(runtime_dir: Path) -> dict:
    browser_marker = runtime_dir / BROWSER_MARKER_NAME
    browser_detection_error = ""
    try:
        browser_executable = resolve_browser_executable_path()
    except Exception as exc:
        browser_executable = ""
        browser_detection_error = f"{type(exc).__name__}: {exc}"
    return {
        "runtime_dir": str(runtime_dir),
        "browser_installed": bool(browser_executable) or browser_marker.exists(),
        "browser_executable": browser_executable,
        "browser_detection_error": browser_detection_error,
        "browser_marker": str(browser_marker),
    }
