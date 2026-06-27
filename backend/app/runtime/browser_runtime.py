from pathlib import Path


BROWSER_MARKER_NAME = "patchright-chromium-installed.txt"


def mark_browser_installed(runtime_dir: Path) -> Path:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    marker = runtime_dir / BROWSER_MARKER_NAME
    marker.write_text("installed", encoding="utf-8")
    return marker
