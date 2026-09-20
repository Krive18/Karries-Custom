import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Iterable

from app.repositories.material_library_repository import (
    MaterialLibraryNotFoundError,
    MaterialLibraryRepository,
)
from app.repositories.wallet_repository import WalletRepository


class MaterialLibraryPreviewError(RuntimeError):
    pass


class MaterialLibraryService:
    def __init__(self, conn, storage_root: Path | str) -> None:
        self.conn = conn
        self.repository = MaterialLibraryRepository(conn)
        self.storage_root = Path(storage_root).resolve()

    def list_items(
        self,
        tenant_id: int,
        project_group_id: int,
        folder_id: int,
        keyword: str = "",
        file_type: str = "",
        recursive: bool = False,
    ) -> dict:
        result = self.repository.list_items(
            tenant_id,
            project_group_id,
            folder_id,
            keyword=keyword,
            file_type=file_type,
            recursive=recursive,
        )
        return {
            **result,
            "assets": [self.external_asset(asset) for asset in result["assets"]],
        }

    def get_storage_usage(self, tenant_id: int, user_id: int) -> dict:
        membership = WalletRepository(self.conn).get_current_membership(
            tenant_id,
            user_id,
        )
        quota_gb = int(membership["plan"]["storage_gb"] or 0)
        quota_bytes = quota_gb * 1024**3
        used_bytes = self.repository.get_storage_bytes(tenant_id)
        remaining_bytes = max(quota_bytes - used_bytes, 0)
        usage_percent = (
            round(min(used_bytes * 100 / quota_bytes, 100), 1)
            if quota_bytes > 0
            else 0.0
        )
        return {
            "used_bytes": used_bytes,
            "quota_bytes": quota_bytes,
            "remaining_bytes": remaining_bytes,
            "quota_gb": quota_gb,
            "usage_percent": usage_percent,
        }

    def get_external_asset(self, tenant_id: int, asset_id: int) -> dict | None:
        asset = self.repository.get_asset(tenant_id, asset_id)
        return self.external_asset(asset) if asset is not None else None

    def resolve_asset_paths(
        self,
        tenant_id: int,
        asset_ids: Iterable[int],
        required_file_type: str | None = None,
    ) -> list[str]:
        normalized_ids = list(dict.fromkeys(int(asset_id) for asset_id in asset_ids))
        assets = self.repository.get_assets(tenant_id, normalized_ids)
        if len(assets) != len(normalized_ids):
            raise MaterialLibraryNotFoundError("material asset not found")

        paths: list[str] = []
        for asset in assets:
            if required_file_type and asset["file_type"] != required_file_type:
                raise ValueError(
                    f"material asset must be {required_file_type}: {asset['file_name']}"
                )
            path = self._safe_asset_path(asset["file_path"])
            if not path.is_file():
                raise MaterialLibraryNotFoundError("material asset file is unavailable")
            paths.append(str(path))
        return paths

    def get_asset_content(self, tenant_id: int, asset_id: int) -> tuple[dict, Path]:
        asset = self.repository.get_asset(tenant_id, asset_id)
        if asset is None:
            raise MaterialLibraryNotFoundError("material asset not found")
        path = self._safe_asset_path(asset["file_path"])
        if not path.is_file():
            raise MaterialLibraryNotFoundError("material asset file is unavailable")
        return asset, path

    def get_video_thumbnail(self, tenant_id: int, asset_id: int) -> tuple[dict, Path]:
        asset, source_path = self.get_asset_content(tenant_id, asset_id)
        if asset["file_type"] != "video":
            raise MaterialLibraryPreviewError("material asset is not a video")

        cache_dir = self.storage_root / ".thumbnails" / f"tenant_{tenant_id}"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_key = source_path.stat().st_mtime_ns
        thumbnail_path = cache_dir / f"{asset_id}-{cache_key}.jpg"
        if thumbnail_path.is_file():
            return asset, thumbnail_path

        temporary_path = cache_dir / f".{asset_id}-{uuid.uuid4().hex}.jpg"
        try:
            self._generate_video_thumbnail(source_path, temporary_path)
            os.replace(temporary_path, thumbnail_path)
            for stale_path in cache_dir.glob(f"{asset_id}-*.jpg"):
                if stale_path != thumbnail_path:
                    stale_path.unlink(missing_ok=True)
        except MaterialLibraryPreviewError:
            raise
        except Exception as exc:
            raise MaterialLibraryPreviewError("video thumbnail could not be generated") from exc
        finally:
            temporary_path.unlink(missing_ok=True)
        return asset, thumbnail_path

    def delete_cached_thumbnails(self, tenant_id: int, asset_id: int) -> None:
        cache_dir = self.storage_root / ".thumbnails" / f"tenant_{tenant_id}"
        if not cache_dir.is_dir():
            return
        for thumbnail_path in cache_dir.glob(f"{asset_id}-*.jpg"):
            thumbnail_path.unlink(missing_ok=True)

    @staticmethod
    def _generate_video_thumbnail(source_path: Path, thumbnail_path: Path) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise MaterialLibraryPreviewError("video preview support is unavailable") from exc

        capture = cv2.VideoCapture(str(source_path))
        temporary_source_path: Path | None = None
        if not capture.isOpened():
            capture.release()
            file_descriptor, temporary_name = tempfile.mkstemp(
                prefix="karries-video-preview-",
                suffix=source_path.suffix,
            )
            os.close(file_descriptor)
            temporary_source_path = Path(temporary_name)
            try:
                shutil.copyfile(source_path, temporary_source_path)
                capture = cv2.VideoCapture(str(temporary_source_path))
            except Exception:
                temporary_source_path.unlink(missing_ok=True)
                raise
        try:
            if not capture.isOpened():
                raise MaterialLibraryPreviewError("video file could not be opened")

            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            frames_per_second = float(capture.get(cv2.CAP_PROP_FPS) or 0)
            if frame_count > 1:
                target_frame = min(
                    max(int(frames_per_second), 1),
                    max(frame_count - 1, 0),
                )
                capture.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            success, frame = capture.read()
            if not success or frame is None:
                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, frame = capture.read()
            if not success or frame is None:
                raise MaterialLibraryPreviewError("video frame could not be decoded")

            height, width = frame.shape[:2]
            scale = min(480 / max(width, 1), 270 / max(height, 1), 1.0)
            if scale < 1.0:
                frame = cv2.resize(
                    frame,
                    (max(1, round(width * scale)), max(1, round(height * scale))),
                    interpolation=cv2.INTER_AREA,
                )
            encoded, jpeg = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, 82],
            )
            if not encoded:
                raise MaterialLibraryPreviewError("video thumbnail could not be written")
            thumbnail_path.write_bytes(jpeg.tobytes())
        finally:
            capture.release()
            if temporary_source_path is not None:
                temporary_source_path.unlink(missing_ok=True)

    def external_asset(self, asset: dict) -> dict:
        safe = dict(asset)
        safe.pop("file_path", None)
        return safe

    def _safe_asset_path(self, relative_path: str) -> Path:
        path = (self.storage_root / relative_path).resolve()
        try:
            path.relative_to(self.storage_root)
        except ValueError as exc:
            raise ValueError("material asset path is invalid") from exc
        return path
