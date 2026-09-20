from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path


IGNORED_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".runtime",
    ".venv",
    "node_modules",
    "logs",
    "cookies",
    "media",
    "tests",
    "accounts.ini",
}
IGNORED_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp"}
FORBIDDEN_WEB_PATTERNS = (
    re.compile(r"127\.0\.0\.1", re.IGNORECASE),
    re.compile(r"https?://localhost\b", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9.-])//localhost(?=[:/])", re.IGNORECASE),
    re.compile(r":(?:8765|8766|8767)\b", re.IGNORECASE),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ignore_local_artifacts(_directory: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        path = Path(name)
        if name in IGNORED_NAMES or path.suffix.lower() in IGNORED_SUFFIXES:
            ignored.add(name)
    return ignored


def require_path(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"required release input is missing: {path}")
    return path


def copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(
        require_path(source),
        target,
        ignore=ignore_local_artifacts,
    )


def git_value(project_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def verify_web_is_same_origin(web_root: Path) -> None:
    violations: list[str] = []
    for path in sorted(web_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".html", ".js", ".css"}:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore").lower()
        patterns = [pattern.pattern for pattern in FORBIDDEN_WEB_PATTERNS if pattern.search(content)]
        if patterns:
            violations.append(f"{path.relative_to(web_root)}: {', '.join(patterns)}")
    if violations:
        raise RuntimeError(
            "production web output contains local API addresses:\n"
            + "\n".join(violations)
        )


def build_release(
    project_root: Path,
    output_root: Path,
    release_name: str,
) -> tuple[Path, Path, Path]:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", release_name):
        raise ValueError("release name may contain only letters, numbers, dot, dash and underscore")

    project_root = project_root.resolve()
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    release_root = output_root / release_name
    archive_path = output_root / f"{release_name}.tar.gz"
    archive_checksum_path = output_root / f"{release_name}.tar.gz.sha256"
    for target in (release_root, archive_path, archive_checksum_path):
        if target.exists():
            raise FileExistsError(f"release target already exists: {target}")

    copy_tree(project_root / "backend" / "app", release_root / "backend" / "app")
    shutil.copy2(
        require_path(project_root / "backend" / "pyproject.toml"),
        release_root / "backend" / "pyproject.toml",
    )

    external_source = project_root / "external" / "social-auto-upload-xiaohongshu"
    external_target = release_root / "external" / "social-auto-upload-xiaohongshu"
    external_target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(require_path(external_source / "conf.py"), external_target / "conf.py")
    copy_tree(external_source / "uploader", external_target / "uploader")
    copy_tree(external_source / "utils", external_target / "utils")
    upstream_note = external_source / "UPSTREAM_SOURCE.md"
    if upstream_note.is_file():
        shutil.copy2(upstream_note, external_target / upstream_note.name)

    copy_tree(project_root / "deploy" / "server", release_root / "deploy" / "server")

    portal_sources = {
        "customer": project_root / "apps" / "desktop" / "dist" / "customer-renderer",
        "manager": project_root / "apps" / "desktop" / "dist" / "manager-renderer",
        "developer": project_root / "apps" / "desktop" / "dist" / "developer-renderer",
    }
    for portal, source in portal_sources.items():
        copy_tree(source, release_root / "web" / portal)

    deploy_readme = require_path(project_root / "deploy" / "server" / "UPLOAD-README.txt")
    shutil.copy2(deploy_readme, release_root / "DEPLOY.txt")
    upgrade_readme = require_path(
        project_root / "deploy" / "server" / "UPGRADE-PRESERVE-DATA.txt"
    )
    shutil.copy2(upgrade_readme, release_root / "UPGRADE-PRESERVE-DATA.txt")
    audit_report = project_root / "docs" / "项目上线前技术审查报告.md"
    if audit_report.is_file():
        docs_target = release_root / "docs"
        docs_target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(audit_report, docs_target / audit_report.name)

    verify_web_is_same_origin(release_root / "web")

    git_status = git_value(project_root, "status", "--porcelain")
    manifest = {
        "release_name": release_name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_branch": git_value(project_root, "branch", "--show-current"),
        "source_commit": git_value(project_root, "rev-parse", "HEAD"),
        "source_dirty": bool(git_status and git_status != "unknown"),
        "contains_xhs_qr_runtime": True,
        "frontend_api_mode": "same-origin /api",
        "release_type": "production database-preserving upgrade",
        "database_payload_included": False,
        "upgrade_entrypoint": "deploy/server/upgrade-preserve-data.sh",
        "rollback_entrypoint": "deploy/server/rollback-preserve-data.sh",
    }
    (release_root / "RELEASE-MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    checksum_lines = []
    for path in sorted(release_root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            checksum_lines.append(
                f"{sha256_file(path)}  {path.relative_to(release_root).as_posix()}"
            )
    (release_root / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(release_root, arcname=release_name, recursive=True)
    archive_checksum_path.write_text(
        f"{sha256_file(archive_path)}  {archive_path.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    return release_root, archive_path, archive_checksum_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a clean KARRIES server delivery archive.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--release-name", required=True)
    args = parser.parse_args()
    release_root, archive_path, checksum_path = build_release(
        args.project_root,
        args.output_root,
        args.release_name,
    )
    print(json.dumps({
        "release_root": str(release_root),
        "archive": str(archive_path),
        "archive_checksum": str(checksum_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
