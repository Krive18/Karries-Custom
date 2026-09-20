import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RESOURCE_DIRECTORIES = {
    "video": "视频",
    "voiceover": "口播音频",
    "subtitle": "字幕",
}
INVALID_ARCHIVE_NAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


@dataclass(frozen=True)
class BuiltDeliveryArchive:
    path: Path
    download_name: str


class DeliveryArchiveError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class VideoDeliveryArchiveService:
    def __init__(self, delivery_root: Path) -> None:
        self.delivery_root = delivery_root.resolve()

    def build(self, job: dict[str, Any]) -> BuiltDeliveryArchive:
        assets = [
            asset
            for asset in job.get("delivery_assets", [])
            if asset.get("resource_type") in RESOURCE_DIRECTORIES
        ]
        if not assets:
            raise DeliveryArchiveError(
                "DELIVERY_ARCHIVE_EMPTY",
                "暂无可下载的交付文件",
            )

        archive_file = tempfile.NamedTemporaryFile(
            prefix=f"video-delivery-{int(job.get('id', 0))}-",
            suffix=".zip",
            delete=False,
        )
        archive_path = Path(archive_file.name)
        archive_file.close()

        used_names: dict[str, set[str]] = {
            directory: set()
            for directory in RESOURCE_DIRECTORIES.values()
        }
        try:
            with zipfile.ZipFile(
                archive_path,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                for directory in RESOURCE_DIRECTORIES.values():
                    archive.writestr(f"{directory}/", b"")
                for index, asset in enumerate(assets, start=1):
                    resource_type = str(asset.get("resource_type"))
                    directory = RESOURCE_DIRECTORIES[resource_type]
                    source_path = self._resolve_source_path(
                        str(asset.get("delivery_file_path", "")),
                    )
                    archive_name = _unique_archive_name(
                        _sanitize_file_name(
                            str(asset.get("delivery_file_name") or source_path.name),
                            resource_type,
                            index,
                        ),
                        used_names[directory],
                    )
                    archive.write(source_path, f"{directory}/{archive_name}")
        except Exception:
            archive_path.unlink(missing_ok=True)
            raise

        return BuiltDeliveryArchive(
            path=archive_path,
            download_name=f"{_sanitize_job_name(str(job.get('job_title') or '视频任务'))}-完整交付包.zip",
        )

    def _resolve_source_path(self, relative_path: str) -> Path:
        if not relative_path.strip():
            raise _incomplete_archive_error()
        candidate = (self.delivery_root / relative_path).resolve()
        try:
            candidate.relative_to(self.delivery_root)
        except ValueError as exc:
            raise _incomplete_archive_error() from exc
        if not candidate.is_file():
            raise _incomplete_archive_error()
        return candidate


def _sanitize_job_name(name: str) -> str:
    sanitized = INVALID_ARCHIVE_NAME_CHARS.sub("-", name).strip(" .")
    return sanitized or "视频任务"


def _sanitize_file_name(name: str, resource_type: str, index: int) -> str:
    source_name = Path(name).name
    suffix = Path(source_name).suffix
    sanitized = INVALID_ARCHIVE_NAME_CHARS.sub("-", source_name).strip(" .")
    if sanitized:
        return sanitized
    fallback_suffix = suffix if suffix else ""
    return f"{resource_type}-{index}{fallback_suffix}"


def _unique_archive_name(file_name: str, used_names: set[str]) -> str:
    candidate = file_name
    stem = Path(file_name).stem
    suffix = Path(file_name).suffix
    counter = 2
    while candidate.casefold() in used_names:
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1
    used_names.add(candidate.casefold())
    return candidate


def _incomplete_archive_error() -> DeliveryArchiveError:
    return DeliveryArchiveError(
        "DELIVERY_ARCHIVE_INCOMPLETE",
        "交付文件不完整，请稍后重试或联系管理员",
    )
