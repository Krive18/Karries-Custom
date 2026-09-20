import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_server_delivery import verify_web_is_same_origin


PACKAGE_SCRIPT = PROJECT_ROOT / "scripts" / "build_server_delivery.py"


def _write(root: Path, relative_path: str, content: str = "fixture") -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_same_origin_check_ignores_dependency_localhost_error_text(tmp_path):
    _write(
        tmp_path,
        "assets/index.js",
        'throw new Error("File URL host must be localhost or empty on darwin")',
    )

    verify_web_is_same_origin(tmp_path)


@pytest.mark.parametrize(
    "endpoint",
    (
        "http://localhost:8765/api",
        "http://127.0.0.1:8765/api",
        "https://localhost/api",
        "https://example.com:8767/api",
    ),
)
def test_same_origin_check_rejects_local_or_private_api_endpoint(tmp_path, endpoint):
    _write(tmp_path, "assets/index.js", f'fetch("{endpoint}")')

    with pytest.raises(RuntimeError, match="local API addresses"):
        verify_web_is_same_origin(tmp_path)


def test_delivery_builder_includes_qr_runtime_and_excludes_local_artifacts(tmp_path):
    fixture_root = tmp_path / "project"
    output_root = tmp_path / "deliveries"
    release_name = "karries-server-test"
    for relative_path in (
        "backend/app/server_main.py",
        "backend/app/__pycache__/server_main.pyc",
        "backend/pyproject.toml",
        "external/social-auto-upload-xiaohongshu/conf.py",
        "external/social-auto-upload-xiaohongshu/uploader/__init__.py",
        "external/social-auto-upload-xiaohongshu/uploader/base_video.py",
        "external/social-auto-upload-xiaohongshu/uploader/xhs_uploader/accounts.ini",
        "external/social-auto-upload-xiaohongshu/uploader/xiaohongshu_uploader/__init__.py",
        "external/social-auto-upload-xiaohongshu/uploader/xiaohongshu_uploader/main.py",
        "external/social-auto-upload-xiaohongshu/utils/__init__.py",
        "external/social-auto-upload-xiaohongshu/utils/base_social_media.py",
        "external/social-auto-upload-xiaohongshu/utils/login_qrcode.py",
        "external/social-auto-upload-xiaohongshu/utils/log.py",
        "external/social-auto-upload-xiaohongshu/utils/stealth.min.js",
        "external/social-auto-upload-xiaohongshu/logs/xhs.log",
        "deploy/server/install.sh",
        "deploy/server/upgrade-preserve-data.sh",
        "deploy/server/rollback-preserve-data.sh",
        "deploy/server/UPGRADE-PRESERVE-DATA.txt",
        "deploy/server/UPLOAD-README.txt",
        "apps/desktop/dist/customer-renderer/index.html",
        "apps/desktop/dist/manager-renderer/manager.html",
        "apps/desktop/dist/developer-renderer/developer.html",
        "docs/项目上线前技术审查报告.md",
    ):
        _write(fixture_root, relative_path)

    result = subprocess.run(
        [
            sys.executable,
            str(PACKAGE_SCRIPT),
            "--project-root",
            str(fixture_root),
            "--output-root",
            str(output_root),
            "--release-name",
            release_name,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    release_root = output_root / release_name
    assert (
        release_root
        / "external/social-auto-upload-xiaohongshu/uploader/xiaohongshu_uploader/main.py"
    ).is_file()
    assert (release_root / "web/customer/index.html").is_file()
    assert (release_root / "web/manager/manager.html").is_file()
    assert (release_root / "web/developer/developer.html").is_file()
    assert not (release_root / "backend/app/__pycache__").exists()
    assert not (release_root / "external/social-auto-upload-xiaohongshu/logs").exists()
    assert not (
        release_root
        / "external/social-auto-upload-xiaohongshu/uploader/xhs_uploader/accounts.ini"
    ).exists()
    assert (release_root / "RELEASE-MANIFEST.json").is_file()
    assert (release_root / "SHA256SUMS").is_file()
    assert b"\r\n" not in (release_root / "SHA256SUMS").read_bytes()
    assert (release_root / "deploy/server/upgrade-preserve-data.sh").is_file()
    assert (release_root / "deploy/server/rollback-preserve-data.sh").is_file()
    assert (release_root / "UPGRADE-PRESERVE-DATA.txt").is_file()

    archive_path = output_root / f"{release_name}.tar.gz"
    assert archive_path.is_file()
    archive_checksum_path = output_root / f"{release_name}.tar.gz.sha256"
    assert archive_checksum_path.is_file()
    assert b"\r\n" not in archive_checksum_path.read_bytes()
    with tarfile.open(archive_path, "r:gz") as archive:
        names = archive.getnames()
    assert (
        f"{release_name}/external/social-auto-upload-xiaohongshu/"
        "uploader/xiaohongshu_uploader/main.py"
    ) in names
    assert f"{release_name}/deploy/server/upgrade-preserve-data.sh" in names
    assert f"{release_name}/UPGRADE-PRESERVE-DATA.txt" in names
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
