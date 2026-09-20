import os
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from app.core.dependencies import (
    get_db_connection,
    require_customer_user,
    require_developer_user,
)
from app.core.responses import fail, ok
from app.integrations.feishu_bot import (
    TaskCreatedNotification,
    send_task_created_notification,
)
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.material_library_repository import MaterialLibraryNotFoundError
from app.repositories.video_edit_repository import VideoEditRepository
from app.repositories.xhs_account_repository import XHSAccountRepository
from app.schemas.video_edit import (
    VideoEditJobClaimRequest,
    VideoEditJobCreate,
    VideoEditJobDeliverRequest,
    VideoEditPublishContentUpdate,
    VideoEditRevisionRequestCreate,
    VideoScriptOptimizeRequest,
)
from app.services.ai_provider_service import AIProviderError
from app.services.material_library_service import MaterialLibraryService
from app.services.upload_storage_service import UploadStorageError, UploadStorageService
from app.services.video_delivery_archive_service import (
    DeliveryArchiveError,
    VideoDeliveryArchiveService,
)
from app.services.video_script_optimization_service import (
    VideoScriptOptimizationService,
)


router = APIRouter(prefix="/api/video-edit/jobs", tags=["video-edit"])
internal_router = APIRouter(
    prefix="/api/internal/video-edit/jobs",
    tags=["internal-video-edit"],
    include_in_schema=False,
)


@router.post("")
def create_video_edit_job(
    payload: VideoEditJobCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    if (
        payload.planned_publish_time > 0
        and payload.planned_publish_time < int(time.time()) + 24 * 60 * 60
    ):
        return JSONResponse(
            status_code=400,
            content=fail(
                "INVALID_PUBLISH_TIME",
                "视频发布时间需至少安排在 24 小时后",
            ),
        )
    account = None
    if payload.xhs_account_id > 0:
        account = XHSAccountRepository(conn).get_for_user(
            int(user["id"]),
            payload.xhs_account_id,
        )
    if payload.xhs_account_id > 0 and account is None:
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_ACCOUNT", "请选择本人管理的小红书账号"),
        )
    try:
        job = VideoEditRepository(conn).create_job(
            user["tenant_id"],
            user["id"],
            payload,
        )
        background_tasks.add_task(
            send_task_created_notification,
            TaskCreatedNotification.video(job),
        )
        return ok(job)
    except MaterialLibraryNotFoundError:
        return _not_found("material asset not found")
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=fail("INSUFFICIENT_CREDITS", str(exc)),
        )


@router.post("/script-optimize")
def optimize_video_script(
    payload: VideoScriptOptimizeRequest,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        result = VideoScriptOptimizationService(conn).optimize(user, payload)
        return ok(result)
    except MaterialLibraryNotFoundError:
        return _not_found("material asset not found")
    except LookupError:
        return _not_found("material asset not found")
    except AIProviderError as exc:
        return JSONResponse(
            status_code=503,
            content=fail("AI_SERVICE_UNAVAILABLE", str(exc)),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=502,
            content=fail("AI_RESPONSE_INVALID", str(exc)),
        )


@router.get("")
def list_video_edit_jobs(
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(VideoEditRepository(conn).list_for_user(user["id"]))


@router.put("/{job_id}/publish-content")
def update_video_edit_publish_content(
    job_id: int,
    payload: VideoEditPublishContentUpdate,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    result = VideoEditRepository(conn).update_publish_content(
        int(user["id"]),
        job_id,
        payload,
    )
    return _job_action_response(result)


@router.post("/{job_id}/revisions")
def request_video_edit_revision(
    job_id: int,
    payload: VideoEditRevisionRequestCreate,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        result = VideoEditRepository(conn).request_revision(
            int(user["tenant_id"]),
            int(user["id"]),
            job_id,
            payload,
        )
        return _job_action_response(result)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=fail("INSUFFICIENT_CREDITS", str(exc)),
        )


@router.get("/{job_id}")
def get_video_edit_job(
    job_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    job = VideoEditRepository(conn).get_for_user(user["id"], job_id)
    if job is None:
        return _not_found("video edit job not found")
    return ok(job)


@router.get("/{job_id}/history")
def get_video_edit_job_history(
    job_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    job = VideoEditRepository(conn).get_for_user(int(user["id"]), job_id)
    if job is None:
        return _not_found("video edit job not found")
    return ok(
        {
            "id": job["id"],
            "request_snapshot": job["request_snapshot"],
            "creation_mode": job["creation_mode"],
            "creation_mode_label": job["creation_mode_label"],
            "credit_cost": job["credit_cost"],
            "status": job["status"],
            "status_name": job["status_name"],
            "status_text": job["status_text"],
            "delivery_versions": job["delivery_versions"],
            "delivery_assets": job["delivery_assets"],
            "revision_count": job["revision_count"],
            "create_time": job["create_time"],
            "update_time": job["update_time"],
            "delivered_time": job["delivered_time"],
        }
    )


@router.get("/{job_id}/delivery/content")
def get_video_edit_delivery_content(
    job_id: int,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    job = VideoEditRepository(conn).get_for_user(int(user["id"]), job_id)
    if job is None:
        return _not_found("video edit job not found")
    relative_path = str(job["delivery"].get("delivery_file_path", "")).strip()
    if job["status"] != 3 or not relative_path:
        return _not_found("video delivery file not found")

    root = _delivery_storage_root(request)
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return _not_found("video delivery file not found")
    if not path.is_file():
        return _not_found("video delivery file not found")

    media_type = "video/quicktime" if path.suffix.lower() == ".mov" else "video/mp4"
    return FileResponse(
        path,
        media_type=media_type,
        filename=str(job["delivery"].get("delivery_file_name", path.name)),
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/{job_id}/delivery/archive")
def get_video_edit_delivery_archive(
    job_id: int,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    job = VideoEditRepository(conn).get_for_user(int(user["id"]), job_id)
    if job is None:
        return _not_found("video edit job not found")
    try:
        built = VideoDeliveryArchiveService(_delivery_storage_root(request)).build(job)
    except DeliveryArchiveError as exc:
        return JSONResponse(
            status_code=409,
            content=fail(exc.code, exc.message),
        )
    return FileResponse(
        built.path,
        media_type="application/zip",
        filename=built.download_name,
        headers={"Cache-Control": "no-store"},
        background=BackgroundTask(os.unlink, built.path),
    )


@router.get("/{job_id}/delivery/versions/{version}/content")
def get_video_edit_delivery_version(
    job_id: int,
    version: int,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    job = VideoEditRepository(conn).get_for_user(int(user["id"]), job_id)
    if job is None:
        return _not_found("video edit job not found")
    version_item = next(
        (
            item
            for item in job["delivery_versions"]
            if int(item.get("version", 0)) == version
        ),
        None,
    )
    if version_item is None:
        return _not_found("video delivery version not found")
    path = _resolve_delivery_file(
        request,
        str(version_item.get("delivery_file_path", "")),
    )
    if path is None:
        return _not_found("video delivery version not found")
    return FileResponse(
        path,
        media_type=_video_media_type(path),
        filename=str(version_item.get("delivery_file_name", path.name)),
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/{job_id}/delivery/resources/{resource_type}/{version}/content")
def get_video_edit_delivery_resource(
    job_id: int,
    resource_type: Literal["voiceover", "subtitle"],
    version: int,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    job = VideoEditRepository(conn).get_for_user(int(user["id"]), job_id)
    if job is None:
        return _not_found("video edit job not found")
    resource = _find_delivery_resource(job, resource_type, version)
    if resource is None:
        return _not_found("delivery resource not found")
    return _delivery_resource_response(request, resource)


@internal_router.get("")
def list_internal_video_edit_jobs(
    status: int | None = None,
    keyword: str = Query(default="", max_length=200),
    sla_status: Literal["normal", "due_soon", "overdue", "completed", "returned"] | None = None,
    tenant_id: int | None = Query(default=None, ge=1),
    operator_user_id: int | None = Query(default=None, ge=1),
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        VideoEditRepository(conn).list_for_developer(
            status=status,
            keyword=keyword,
            sla_status=sla_status,
            tenant_id=tenant_id,
            operator_user_id=operator_user_id,
        )
    )


@internal_router.get("/{job_id}")
def get_internal_video_edit_job(
    job_id: int,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    job = VideoEditRepository(conn).get_for_developer(job_id)
    if job is None:
        return _not_found("video edit job not found")
    return ok(job)


@internal_router.get("/{job_id}/materials/{asset_id}/content")
def get_internal_video_edit_material_content(
    job_id: int,
    asset_id: int,
    request: Request,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    repository = VideoEditRepository(conn)
    job = repository.get_for_developer(job_id)
    scope = repository.get_owner_scope(job_id)
    if job is None or scope is None:
        return _not_found("video edit job not found")
    allowed_asset_ids = {
        int(material.get("material_file_id", 0))
        for material in job["materials"]
    }
    if asset_id not in allowed_asset_ids:
        return _not_found("video edit material not found")
    try:
        asset, path = MaterialLibraryService(
            conn,
            Path(request.app.state.config.data_dir) / "product_materials",
        ).get_asset_content(int(scope["tenant_id"]), asset_id)
    except MaterialLibraryNotFoundError:
        return _not_found("video edit material not found")
    return FileResponse(
        path,
        media_type=asset["mime_type"],
        filename=asset["file_name"],
        headers={"Cache-Control": "private, max-age=300"},
    )


@internal_router.get("/{job_id}/materials/archive")
def get_internal_video_edit_material_archive(
    job_id: int,
    request: Request,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    repository = VideoEditRepository(conn)
    job = repository.get_for_developer(job_id)
    scope = repository.get_owner_scope(job_id)
    if job is None or scope is None:
        return _not_found("video edit job not found")

    service = MaterialLibraryService(
        conn,
        Path(request.app.state.config.data_dir) / "product_materials",
    )
    archive_file = tempfile.NamedTemporaryFile(
        prefix=f"video-job-{job_id}-",
        suffix=".zip",
        delete=False,
    )
    archive_path = Path(archive_file.name)
    archive_file.close()
    used_names: set[str] = set()
    try:
        with zipfile.ZipFile(
            archive_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for index, material in enumerate(job["materials"], start=1):
                asset_id = int(material.get("material_file_id", 0))
                try:
                    asset, path = service.get_asset_content(
                        int(scope["tenant_id"]),
                        asset_id,
                    )
                except MaterialLibraryNotFoundError:
                    continue
                archive_name = _unique_archive_name(
                    Path(str(asset["file_name"])).name or f"material-{index}",
                    used_names,
                )
                archive.write(path, archive_name)
        return FileResponse(
            archive_path,
            media_type="application/zip",
            filename=f"video-job-{job_id}-materials.zip",
            background=BackgroundTask(os.unlink, archive_path),
        )
    except Exception:
        archive_path.unlink(missing_ok=True)
        raise


@internal_router.post("/{job_id}/claim")
def claim_internal_video_edit_job(
    job_id: int,
    payload: VideoEditJobClaimRequest,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = VideoEditRepository(conn)
    scope = repository.get_owner_scope(job_id)
    result = repository.claim_job(job_id, developer["id"], payload)
    if result is not None and "error" not in result and scope is not None:
        _write_video_job_audit(
            conn,
            scope,
            developer,
            job_id,
            "video_job_claimed",
            {"note": payload.note},
        )
    return _job_action_response(result)


@internal_router.post("/{job_id}/deliver")
def deliver_internal_video_edit_job(
    job_id: int,
    payload: VideoEditJobDeliverRequest,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = VideoEditRepository(conn)
    scope = repository.get_owner_scope(job_id)
    result = repository.deliver_job(job_id, developer["id"], payload)
    if result is not None and "error" not in result and scope is not None:
        _write_video_job_audit(
            conn,
            scope,
            developer,
            job_id,
            _delivery_audit_action(result),
            {
                "version": result["delivery_version_count"],
                "delivery_file_name": payload.delivery_file_name,
            },
        )
    return _job_action_response(result)


@internal_router.post("/{job_id}/delivery/upload")
def upload_internal_video_edit_delivery(
    job_id: int,
    request: Request,
    files: list[UploadFile] | None = File(default=None),
    file: UploadFile | None = File(default=None),
    note: str = Form(default=""),
    resource_type: Literal["video", "voiceover", "subtitle"] = Form(default="video"),
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    normalized_resource_type: Literal["video", "voiceover", "subtitle"] = (
        resource_type if isinstance(resource_type, str) else "video"
    )
    repository = VideoEditRepository(conn)
    scope = repository.get_owner_scope(job_id)
    if scope is None:
        return _not_found("video edit job not found")

    storage = UploadStorageService(_delivery_storage_root(request))
    uploads = list(files or [])
    if file is not None:
        uploads.append(file)
    if not uploads:
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_UPLOAD", "at least one delivery file is required"),
        )
    if len(uploads) > 20:
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_UPLOAD", "at most 20 delivery files are allowed"),
        )

    stored_uploads = []
    delivered_paths: set[str] = set()
    try:
        for upload in uploads:
            stored = storage.save(
                stream=upload.file,
                original_name=upload.filename or _default_delivery_file_name(normalized_resource_type),
                declared_mime_type=upload.content_type or "",
                tenant_id=int(scope["tenant_id"]),
                job_id=job_id,
            )
            expected_file_type = {
                "video": "video",
                "voiceover": "audio",
                "subtitle": "subtitle",
            }[normalized_resource_type]
            if stored.file_type != expected_file_type:
                storage.delete(stored.storage_path)
                raise UploadStorageError(
                    f"delivery file does not match resource type {normalized_resource_type}"
                )
            stored_uploads.append(stored)

        result = None
        for stored in stored_uploads:
            if normalized_resource_type == "video":
                result = repository.deliver_job(
                    job_id,
                    int(developer["id"]),
                    VideoEditJobDeliverRequest(
                        delivery_file_name=stored.file_name,
                        delivery_file_path=stored.storage_path,
                        delivery_url=f"/api/video-edit/jobs/{job_id}/delivery/content",
                        note=note,
                    ),
                    publish_video_path=str(
                        (_delivery_storage_root(request) / stored.storage_path).resolve()
                    ),
                )
            else:
                result = repository.add_delivery_resource(
                    job_id,
                    int(developer["id"]),
                    resource_type=normalized_resource_type,
                    delivery_file_name=stored.file_name,
                    delivery_file_path=stored.storage_path,
                    mime_type=stored.mime_type,
                    file_size=stored.file_size,
                    note=note,
                )
            if result is None or "error" in result:
                return _job_action_response(result)
            delivered_paths.add(stored.storage_path)
            _write_video_job_audit(
                conn,
                scope,
                developer,
                job_id,
                (
                    _delivery_audit_action(result)
                    if normalized_resource_type == "video"
                    else f"video_{normalized_resource_type}_uploaded"
                ),
                {
                    "resource_type": normalized_resource_type,
                    "version": (
                        result["delivery_version_count"]
                        if normalized_resource_type == "video"
                        else result["delivery_resource_counts"][normalized_resource_type]
                    ),
                    "delivery_file_name": stored.file_name,
                    "note": note,
                },
            )
        return ok(result)
    except UploadStorageError as exc:
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_UPLOAD", str(exc)),
        )
    finally:
        for stored in stored_uploads:
            if stored.storage_path not in delivered_paths:
                storage.delete(stored.storage_path)
        for upload in uploads:
            upload.file.close()


@internal_router.get("/{job_id}/delivery/versions/{version}/content")
def get_internal_video_edit_delivery_version(
    job_id: int,
    version: int,
    request: Request,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    job = VideoEditRepository(conn).get_for_developer(job_id)
    if job is None:
        return _not_found("video edit job not found")
    version_item = next(
        (
            item
            for item in job["delivery_versions"]
            if int(item.get("version", 0)) == version
        ),
        None,
    )
    if version_item is None:
        return _not_found("video delivery version not found")
    path = _resolve_delivery_file(
        request,
        str(version_item.get("delivery_file_path", "")),
    )
    if path is None:
        return _not_found("video delivery version not found")
    return FileResponse(
        path,
        media_type=_video_media_type(path),
        filename=str(version_item.get("delivery_file_name", path.name)),
        headers={"Cache-Control": "private, max-age=300"},
    )


@internal_router.get("/{job_id}/delivery/resources/{resource_type}/{version}/content")
def get_internal_video_edit_delivery_resource(
    job_id: int,
    resource_type: Literal["voiceover", "subtitle"],
    version: int,
    request: Request,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    job = VideoEditRepository(conn).get_for_developer(job_id)
    if job is None:
        return _not_found("video edit job not found")
    resource = _find_delivery_resource(job, resource_type, version)
    if resource is None:
        return _not_found("delivery resource not found")
    return _delivery_resource_response(request, resource)


@internal_router.get("/{job_id}/history")
def get_internal_video_edit_history(
    job_id: int,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    if VideoEditRepository(conn).get_owner_scope(job_id) is None:
        return _not_found("video edit job not found")
    return ok(
        AdminAuditRepository(conn).list_for_target(
            "video_edit_job",
            job_id,
        )
    )


def _job_action_response(result: dict | None):
    if result is None:
        return _not_found("video edit job not found")
    if "error" in result:
        return JSONResponse(
            status_code=400,
            content=fail("VALIDATION_ERROR", result["error"]),
        )
    return ok(result)


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(status_code=404, content=fail("NOT_FOUND", message))


def _delivery_storage_root(request: Request) -> Path:
    return Path(request.app.state.config.data_dir) / "video_deliveries"


def _write_video_job_audit(
    conn,
    scope: dict,
    developer: dict,
    job_id: int,
    action: str,
    detail: dict,
) -> None:
    AdminAuditRepository(conn).create(
        tenant_id=int(scope["tenant_id"]),
        admin_user_id=int(developer["id"]),
        action=action,
        target_type="video_edit_job",
        target_id=job_id,
        detail=detail,
    )


def _delivery_audit_action(job: dict) -> str:
    return (
        "video_delivery_replaced"
        if int(job.get("delivery_version_count", 0)) > 1
        else "video_delivery_uploaded"
    )


def _resolve_delivery_file(request: Request, relative_path: str) -> Path | None:
    if not relative_path.strip():
        return None
    root = _delivery_storage_root(request).resolve()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path if path.is_file() else None


def _video_media_type(path: Path) -> str:
    return "video/quicktime" if path.suffix.lower() == ".mov" else "video/mp4"


def _default_delivery_file_name(resource_type: str) -> str:
    return {
        "video": "delivery.mp4",
        "voiceover": "voiceover.mp3",
        "subtitle": "subtitle.srt",
    }[resource_type]


def _find_delivery_resource(
    job: dict,
    resource_type: str,
    version: int,
) -> dict | None:
    return next(
        (
            item
            for item in job.get("delivery_assets", [])
            if item.get("resource_type") == resource_type
            and int(item.get("version", 0)) == version
        ),
        None,
    )


def _delivery_resource_response(request: Request, resource: dict):
    path = _resolve_delivery_file(
        request,
        str(resource.get("delivery_file_path", "")),
    )
    if path is None:
        return _not_found("delivery resource not found")
    return FileResponse(
        path,
        media_type=str(resource.get("mime_type") or "application/octet-stream"),
        filename=str(resource.get("delivery_file_name") or path.name),
        headers={"Cache-Control": "private, max-age=300"},
    )


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
