from pathlib import Path

from app.runtime.browser_runtime import BROWSER_MARKER_NAME


def check_runtime(runtime_dir: Path) -> dict:
    browser_marker = runtime_dir / BROWSER_MARKER_NAME
    return {
        "runtime_dir": str(runtime_dir),
        "browser_installed": browser_marker.exists(),
        "browser_marker": str(browser_marker),
    }
