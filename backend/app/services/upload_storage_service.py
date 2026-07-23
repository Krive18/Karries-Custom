import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


class UploadStorageError(ValueError):
    pass


@dataclass(frozen=True)
class StoredUpload:
    file_name: str
    file_type: str
    mime_type: str
    file_size: int
    storage_path: str


class UploadStorageService:
    MAX_BYTES = 200 * 1024 * 1024
    CHUNK_SIZE = 1024 * 1024
    _MIME_TYPES = {
        "image/jpeg": ("image", ".jpg", {".jpg", ".jpeg"}),
        "image/png": ("image", ".png", {".png"}),
        "image/webp": ("image", ".webp", {".webp"}),
        "video/mp4": ("video", ".mp4", {".mp4"}),
        "video/quicktime": ("video", ".mov", {".mov"}),
    }

    def __init__(
        self,
        root_dir: Path | str,
        max_bytes: int = MAX_BYTES,
        chunk_size: int = CHUNK_SIZE,
    ) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.max_bytes = max_bytes
        self.chunk_size = chunk_size

    def save(
        self,
        stream: BinaryIO,
        original_name: str,
        declared_mime_type: str,
        tenant_id: int,
        job_id: int,
    ) -> StoredUpload:
        if declared_mime_type not in self._MIME_TYPES:
            raise UploadStorageError("unsupported upload media type")
        display_name = self._sanitize_display_name(original_name)
        if Path(display_name).suffix.lower() not in self._MIME_TYPES[declared_mime_type][2]:
            raise UploadStorageError("file extension does not match upload media type")

        directory = self._safe_directory(tenant_id, job_id)
        temp_path = directory / f"{uuid.uuid4().hex}.part"
        try:
            header, size = self._write_stream(stream, temp_path)
            detected_mime_type = self._detect_mime_type(header)
            if detected_mime_type is None:
                raise UploadStorageError("unsupported upload file signature")
            if detected_mime_type != declared_mime_type:
                raise UploadStorageError("declared media type does not match file signature")

            file_type, extension, _ = self._MIME_TYPES[declared_mime_type]
            final_name = f"{uuid.uuid4().hex}{extension}"
            final_path = directory / final_name
            self._assert_within_root(final_path)
            os.replace(temp_path, final_path)
            return StoredUpload(
                file_name=display_name,
                file_type=file_type,
                mime_type=declared_mime_type,
                file_size=size,
                storage_path=str(final_path.relative_to(self.root_dir)),
            )
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def delete(self, storage_path: str) -> None:
        target = self.root_dir / storage_path
        self._assert_within_root(target)
        target.unlink(missing_ok=True)

    def _safe_directory(self, tenant_id: int, job_id: int) -> Path:
        if tenant_id <= 0 or job_id <= 0:
            raise UploadStorageError("invalid upload scope")
        directory = self.root_dir / f"tenant_{tenant_id}" / f"job_{job_id}"
        self._assert_within_root(directory)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _write_stream(self, stream: BinaryIO, temp_path: Path) -> tuple[bytes, int]:
        header = b""
        total_size = 0
        with temp_path.open("xb") as output:
            while True:
                chunk = stream.read(self.chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > self.max_bytes:
                    raise UploadStorageError("upload file is too large")
                if len(header) < 32:
                    header = (header + chunk)[:32]
                output.write(chunk)
        if total_size == 0:
            raise UploadStorageError("upload file is empty")
        return header, total_size

    def _detect_mime_type(self, header: bytes) -> str | None:
        if header.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
            return "image/webp"
        if len(header) >= 12 and header[4:8] == b"ftyp":
            return "video/quicktime" if header[8:12] == b"qt  " else "video/mp4"
        return None

    def _sanitize_display_name(self, original_name: str) -> str:
        name = Path(original_name or "upload").name
        name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
        name = name or "upload"
        suffix = Path(name).suffix
        if len(name) <= 255:
            return name
        if suffix and len(suffix) < 255:
            return name[: 255 - len(suffix)] + suffix
        return name[:255]

    def _assert_within_root(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self.root_dir)
        except ValueError as exc:
            raise UploadStorageError("upload path escapes configured root") from exc
