import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.core.dependencies import get_db_connection, require_customer_user
from app.core.responses import fail, ok
from app.repositories.material_library_repository import (
    MaterialLibraryConflictError,
    MaterialLibraryNotFoundError,
    MaterialLibraryRepository,
)
from app.schemas.material_library import (
    MaterialAssetUpdate,
    MaterialFolderCreate,
    MaterialFolderRename,
    MaterialProjectGroupCreate,
    MaterialProjectGroupRename,
)
from app.services.material_library_service import (
    MaterialLibraryPreviewError,
    MaterialLibraryService,
)
from app.services.upload_storage_service import UploadStorageError, UploadStorageService


router = APIRouter(prefix="/api/material-library", tags=["material-library"])
logger = logging.getLogger(__name__)


def _storage_root(request: Request) -> Path:
    return Path(request.app.state.config.data_dir) / "product_materials"


@router.get("/items")
def list_items(
    request: Request,
    project_group_id: int = Query(default=0, ge=0),
    folder_id: int = Query(default=0, ge=0),
    keyword: str = Query(default="", max_length=100),
    file_type: Literal["", "image", "video", "word", "excel", "other"] = Query(default=""),
    recursive: bool = Query(default=False),
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        repository = MaterialLibraryRepository(conn)
        resolved_group_id = repository.resolve_project_group_id(
            int(user["tenant_id"]),
            int(user["id"]),
            project_group_id,
            folder_id,
        )
        return ok(
            MaterialLibraryService(conn, _storage_root(request)).list_items(
                int(user["tenant_id"]),
                resolved_group_id,
                folder_id,
                keyword=keyword,
                file_type=file_type,
                recursive=recursive,
            )
        )
    except MaterialLibraryNotFoundError:
        return _not_found("material project group or folder not found")


@router.get("/project-groups")
def list_project_groups(
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = MaterialLibraryRepository(conn)
    repository.ensure_default_project_group(
        int(user["tenant_id"]),
        int(user["id"]),
    )
    return ok(repository.list_project_groups(int(user["tenant_id"])))


@router.post("/project-groups")
def create_project_group(
    payload: MaterialProjectGroupCreate,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = MaterialLibraryRepository(conn)
    try:
        repository.ensure_default_project_group(
            int(user["tenant_id"]),
            int(user["id"]),
        )
        return ok(
            repository.create_project_group(
                int(user["tenant_id"]),
                int(user["id"]),
                payload.group_name,
            )
        )
    except ValueError as exc:
        return _project_group_validation_error(str(exc))


@router.patch("/project-groups/{project_group_id}")
def rename_project_group(
    project_group_id: int,
    payload: MaterialProjectGroupRename,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            MaterialLibraryRepository(conn).rename_project_group(
                int(user["tenant_id"]),
                project_group_id,
                payload.group_name,
            )
        )
    except MaterialLibraryNotFoundError:
        return _not_found("material project group not found")
    except ValueError as exc:
        return _project_group_validation_error(str(exc))


@router.delete("/project-groups/{project_group_id}")
def delete_project_group(
    project_group_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        MaterialLibraryRepository(conn).delete_empty_project_group(
            int(user["tenant_id"]),
            project_group_id,
        )
        return ok({"deleted": True})
    except MaterialLibraryNotFoundError:
        return _not_found("material project group not found")
    except MaterialLibraryConflictError as exc:
        return JSONResponse(
            status_code=409,
            content=fail("PROJECT_GROUP_NOT_EMPTY", str(exc)),
        )


@router.get("/storage-usage")
def get_storage_usage(
    request: Request,
    response: Response,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return ok(
        MaterialLibraryService(conn, _storage_root(request)).get_storage_usage(
            int(user["tenant_id"]),
            int(user["id"]),
        )
    )


@router.post("/folders")
def create_folder(
    payload: MaterialFolderCreate,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        repository = MaterialLibraryRepository(conn)
        project_group_id = repository.resolve_project_group_id(
            int(user["tenant_id"]),
            int(user["id"]),
            payload.project_group_id,
            payload.parent_id,
        )
        folder = repository.create_folder(
            int(user["tenant_id"]),
            int(user["id"]),
            project_group_id,
            payload.parent_id,
            payload.folder_name,
        )
        return ok(folder)
    except MaterialLibraryNotFoundError:
        return _not_found("material project group or parent folder not found")
    except ValueError as exc:
        return _validation_error(str(exc))


@router.patch("/folders/{folder_id}")
def rename_folder(
    folder_id: int,
    payload: MaterialFolderRename,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            MaterialLibraryRepository(conn).rename_folder(
                user["tenant_id"],
                folder_id,
                payload.folder_name,
            )
        )
    except MaterialLibraryNotFoundError:
        return _not_found("material folder not found")
    except ValueError as exc:
        return _validation_error(str(exc))


@router.delete("/folders/{folder_id}")
def delete_folder(
    folder_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        MaterialLibraryRepository(conn).delete_empty_folder(
            user["tenant_id"],
            folder_id,
        )
        return ok({"deleted": True})
    except MaterialLibraryNotFoundError:
        return _not_found("material folder not found")
    except MaterialLibraryConflictError as exc:
        return JSONResponse(
            status_code=409,
            content=fail("FOLDER_NOT_EMPTY", str(exc)),
        )


@router.post("/assets/upload")
def upload_asset(
    request: Request,
    folder_id: int = Query(default=0, ge=0),
    file: UploadFile = File(...),
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    if folder_id == 0:
        return JSONResponse(
            status_code=400,
            content=fail(
                "ROOT_UPLOAD_FORBIDDEN",
                "请先新建或进入产品文件夹后再上传素材",
            ),
        )

    storage = UploadStorageService(_storage_root(request))
    stored = None
    asset_saved = False
    try:
        stored = storage.save(
            stream=file.file,
            original_name=file.filename or "upload",
            declared_mime_type=file.content_type or "",
            tenant_id=user["tenant_id"],
            job_id=folder_id + 1,
        )
        repository = MaterialLibraryRepository(conn)
        asset = repository.create_asset(
            user["tenant_id"],
            user["id"],
            folder_id,
            stored.__dict__,
        )
        asset_saved = True
        return ok(
            MaterialLibraryService(conn, _storage_root(request)).external_asset(asset)
        )
    except MaterialLibraryNotFoundError:
        return _not_found("material folder not found")
    except UploadStorageError as exc:
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_UPLOAD", str(exc)),
        )
    finally:
        if stored is not None and not asset_saved:
            (storage.root_dir / stored.storage_path).unlink(missing_ok=True)
        file.file.close()


@router.patch("/assets/{asset_id}")
def update_asset(
    asset_id: int,
    payload: MaterialAssetUpdate,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        asset = MaterialLibraryRepository(conn).update_asset(
            user["tenant_id"],
            asset_id,
            folder_id=payload.folder_id,
            file_name=payload.file_name,
        )
        return ok(
            MaterialLibraryService(conn, _storage_root(request)).external_asset(asset)
        )
    except MaterialLibraryNotFoundError:
        return _not_found("material asset or target folder not found")
    except ValueError as exc:
        return _validation_error(str(exc))


@router.get("/assets/{asset_id}/content")
def get_asset_content(
    asset_id: int,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    try:
        asset, path = MaterialLibraryService(
            conn,
            _storage_root(request),
        ).get_asset_content(user["tenant_id"], asset_id)
        return FileResponse(
            path,
            media_type=asset["mime_type"],
            headers={"Cache-Control": "private, max-age=300"},
        )
    except MaterialLibraryNotFoundError:
        return _not_found("material asset not found")


@router.get("/assets/{asset_id}/thumbnail")
def get_asset_thumbnail(
    asset_id: int,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    try:
        _, path = MaterialLibraryService(
            conn,
            _storage_root(request),
        ).get_video_thumbnail(user["tenant_id"], asset_id)
        return FileResponse(
            path,
            media_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=86400"},
        )
    except MaterialLibraryNotFoundError:
        return _not_found("material asset not found")
    except MaterialLibraryPreviewError as exc:
        return JSONResponse(
            status_code=422,
            content=fail("PREVIEW_UNAVAILABLE", str(exc)),
        )


@router.delete("/assets/{asset_id}")
def delete_asset(
    asset_id: int,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = MaterialLibraryRepository(conn)
    try:
        asset = repository.delete_asset(user["tenant_id"], asset_id)
    except MaterialLibraryNotFoundError:
        return _not_found("material asset not found")

    storage = UploadStorageService(_storage_root(request))
    try:
        storage.delete(asset["file_path"])
        MaterialLibraryService(
            conn,
            _storage_root(request),
        ).delete_cached_thumbnails(user["tenant_id"], asset_id)
    except (OSError, UploadStorageError):
        logger.warning(
            "failed to remove deleted product material asset",
            extra={"tenant_id": user["tenant_id"], "asset_id": asset_id},
        )
    return ok({"deleted": True})


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=fail("NOT_FOUND", message),
    )


def _validation_error(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=fail("VALIDATION_ERROR", message),
    )


def _project_group_validation_error(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=fail("INVALID_PROJECT_GROUP", message),
    )
