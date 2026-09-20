import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.core.dependencies import get_db_connection, require_management_user
from app.core.responses import fail, ok
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.admin_product_library_repository import (
    AdminProductLibraryRepository,
)
from app.repositories.material_library_repository import (
    MaterialLibraryConflictError,
    MaterialLibraryNotFoundError,
    MaterialLibraryRepository,
)
from app.schemas.admin_product_library import AdminProductStatusUpdate
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


router = APIRouter(
    prefix="/api/admin/product-library",
    tags=["admin-product-library"],
)
logger = logging.getLogger(__name__)


def _storage_root(request: Request) -> Path:
    return Path(request.app.state.config.data_dir) / "product_materials"


@router.get("/summary")
def summary(
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AdminProductLibraryRepository(conn).summary(int(manager["tenant_id"]))
    )


@router.get("/products")
def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    employee_id: int | None = Query(default=None, ge=1),
    status: int | None = Query(default=None, ge=1, le=2),
    keyword: str = Query(default="", max_length=100),
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AdminProductLibraryRepository(conn).list_products(
            int(manager["tenant_id"]),
            page=page,
            page_size=page_size,
            employee_id=employee_id,
            status=status,
            keyword=keyword.strip(),
        )
    )


@router.patch("/products/{product_id}/status")
def update_product_status(
    product_id: int,
    payload: AdminProductStatusUpdate,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    product = AdminProductLibraryRepository(conn).update_product_status(
        int(manager["tenant_id"]),
        product_id,
        payload.status,
    )
    if product is None:
        return _not_found("product not found")
    AdminAuditRepository(conn).create(
        tenant_id=int(manager["tenant_id"]),
        admin_user_id=int(manager["id"]),
        action="product.status_update",
        target_type="product",
        target_id=product_id,
        detail={"status": payload.status},
    )
    return ok(product)


@router.get("/project-groups")
def list_project_groups(
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = MaterialLibraryRepository(conn)
    repository.ensure_default_project_group(
        int(manager["tenant_id"]),
        int(manager["id"]),
    )
    return ok(repository.list_project_groups(int(manager["tenant_id"])))


@router.post("/project-groups")
def create_project_group(
    payload: MaterialProjectGroupCreate,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = MaterialLibraryRepository(conn)
    try:
        repository.ensure_default_project_group(
            int(manager["tenant_id"]),
            int(manager["id"]),
        )
        group = repository.create_project_group(
            int(manager["tenant_id"]),
            int(manager["id"]),
            payload.group_name,
        )
        _audit(
            manager,
            conn,
            "material_project_group.create",
            "material_project_group",
            group["id"],
        )
        return ok(group)
    except ValueError as exc:
        return _project_group_validation_error(str(exc))


@router.patch("/project-groups/{project_group_id}")
def rename_project_group(
    project_group_id: int,
    payload: MaterialProjectGroupRename,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        group = MaterialLibraryRepository(conn).rename_project_group(
            int(manager["tenant_id"]),
            project_group_id,
            payload.group_name,
        )
        _audit(
            manager,
            conn,
            "material_project_group.rename",
            "material_project_group",
            project_group_id,
        )
        return ok(group)
    except MaterialLibraryNotFoundError:
        return _not_found("material project group not found")
    except ValueError as exc:
        return _project_group_validation_error(str(exc))


@router.delete("/project-groups/{project_group_id}")
def delete_project_group(
    project_group_id: int,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        MaterialLibraryRepository(conn).delete_empty_project_group(
            int(manager["tenant_id"]),
            project_group_id,
        )
        _audit(
            manager,
            conn,
            "material_project_group.delete",
            "material_project_group",
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


@router.get("/items")
def list_items(
    request: Request,
    project_group_id: int = Query(default=0, ge=0),
    folder_id: int = Query(default=0, ge=0),
    keyword: str = Query(default="", max_length=100),
    file_type: Literal["", "image", "video", "word", "excel", "other"] = Query(default=""),
    recursive: bool = Query(default=False),
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        repository = MaterialLibraryRepository(conn)
        resolved_group_id = repository.resolve_project_group_id(
            int(manager["tenant_id"]),
            int(manager["id"]),
            project_group_id,
            folder_id,
        )
        return ok(
            MaterialLibraryService(conn, _storage_root(request)).list_items(
                int(manager["tenant_id"]),
                resolved_group_id,
                folder_id,
                keyword=keyword,
                file_type=file_type,
                recursive=recursive,
            )
        )
    except MaterialLibraryNotFoundError:
        return _not_found("material project group or folder not found")


@router.post("/folders")
def create_folder(
    payload: MaterialFolderCreate,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        repository = MaterialLibraryRepository(conn)
        project_group_id = repository.resolve_project_group_id(
            int(manager["tenant_id"]),
            int(manager["id"]),
            payload.project_group_id,
            payload.parent_id,
        )
        folder = repository.create_folder(
            int(manager["tenant_id"]),
            int(manager["id"]),
            project_group_id,
            payload.parent_id,
            payload.folder_name,
        )
        _audit(manager, conn, "material_folder.create", "material_folder", folder["id"])
        return ok(folder)
    except MaterialLibraryNotFoundError:
        return _not_found("material project group or parent folder not found")
    except ValueError as exc:
        return _validation_error(str(exc))


@router.patch("/folders/{folder_id}")
def rename_folder(
    folder_id: int,
    payload: MaterialFolderRename,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        folder = MaterialLibraryRepository(conn).rename_folder(
            int(manager["tenant_id"]),
            folder_id,
            payload.folder_name,
        )
        _audit(manager, conn, "material_folder.rename", "material_folder", folder_id)
        return ok(folder)
    except MaterialLibraryNotFoundError:
        return _not_found("material folder not found")
    except ValueError as exc:
        return _validation_error(str(exc))


@router.delete("/folders/{folder_id}")
def delete_folder(
    folder_id: int,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        MaterialLibraryRepository(conn).delete_empty_folder(
            int(manager["tenant_id"]),
            folder_id,
        )
        _audit(manager, conn, "material_folder.delete", "material_folder", folder_id)
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
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    storage = UploadStorageService(_storage_root(request))
    stored = None
    asset_saved = False
    try:
        stored = storage.save(
            stream=file.file,
            original_name=file.filename or "upload",
            declared_mime_type=file.content_type or "",
            tenant_id=int(manager["tenant_id"]),
            job_id=folder_id + 1,
        )
        asset = MaterialLibraryRepository(conn).create_asset(
            int(manager["tenant_id"]),
            int(manager["id"]),
            folder_id,
            stored.__dict__,
        )
        asset_saved = True
        _audit(manager, conn, "material_asset.upload", "material_file", asset["id"])
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
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        asset = MaterialLibraryRepository(conn).update_asset(
            int(manager["tenant_id"]),
            asset_id,
            folder_id=payload.folder_id,
            file_name=payload.file_name,
        )
        _audit(manager, conn, "material_asset.update", "material_file", asset_id)
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
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
):
    try:
        asset, path = MaterialLibraryService(
            conn,
            _storage_root(request),
        ).get_asset_content(int(manager["tenant_id"]), asset_id)
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
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
):
    try:
        _, path = MaterialLibraryService(
            conn,
            _storage_root(request),
        ).get_video_thumbnail(int(manager["tenant_id"]), asset_id)
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
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = MaterialLibraryRepository(conn)
    try:
        asset = repository.delete_asset(int(manager["tenant_id"]), asset_id)
    except MaterialLibraryNotFoundError:
        return _not_found("material asset not found")
    try:
        UploadStorageService(_storage_root(request)).delete(asset["file_path"])
        MaterialLibraryService(
            conn,
            _storage_root(request),
        ).delete_cached_thumbnails(int(manager["tenant_id"]), asset_id)
    except (OSError, UploadStorageError):
        logger.warning(
            "failed to remove deleted manager product material asset",
            extra={"tenant_id": manager["tenant_id"], "asset_id": asset_id},
        )
    _audit(manager, conn, "material_asset.delete", "material_file", asset_id)
    return ok({"deleted": True})


def _audit(
    manager: dict,
    conn,
    action: str,
    target_type: str,
    target_id: int,
) -> None:
    AdminAuditRepository(conn).create(
        tenant_id=int(manager["tenant_id"]),
        admin_user_id=int(manager["id"]),
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail={},
    )


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
