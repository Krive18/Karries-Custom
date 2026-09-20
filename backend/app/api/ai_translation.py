import time
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
from app.repositories.ai_translation_repository import AiTranslationRepository
from app.repositories.material_library_repository import MaterialLibraryNotFoundError
from app.schemas.ai_translation import (
    AiTranslationActionRequest,
    AiTranslationMaterialCreate,
    AiTranslationRevisionRequest,
)
from app.services.upload_storage_service import UploadStorageError, UploadStorageService


router = APIRouter(prefix="/api/ai-translations/tasks", tags=["ai-translations"])
internal_router = APIRouter(
    prefix="/api/internal/ai-translations/tasks",
    tags=["internal-ai-translations"],
    include_in_schema=False,
)

TranslationLanguage = Literal["auto", "vi", "en", "zh", "ms", "th", "tl", "ja", "ko", "es"]
TranslationTargetLanguage = Literal["vi", "en", "zh", "ms", "th", "tl", "ja", "ko", "es"]
TranslationStatus = Literal[
    "pending",
    "claimed",
    "in_progress",
    "awaiting_customer",
    "revision_requested",
    "completed",
    "cancelled",
    "failed",
]
TranslationDeliveryResourceType = Literal["video", "voiceover", "subtitle"]
MAX_TRANSLATION_BYTES = 500 * 1024 * 1024

DELIVERY_FILE_TYPES = {
    "video": "video",
    "voiceover": "audio",
    "subtitle": "subtitle",
}
DELIVERY_RESOURCE_LABELS = {
    "video": "translated video",
    "voiceover": "voiceover audio",
    "subtitle": "subtitle file",
}


@router.post("/upload")
def upload_translation_task(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_language: TranslationLanguage = Form(default="auto"),
    target_language: TranslationTargetLanguage = Form(...),
    client_request_id: str = Form(..., min_length=8, max_length=64),
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    if source_language != "auto" and source_language == target_language:
        return _validation_error("source and target languages must be different")
    storage = UploadStorageService(
        _source_upload_root(request),
        max_bytes=MAX_TRANSLATION_BYTES,
    )
    stored = None
    try:
        stored = storage.save(
            stream=file.file,
            original_name=file.filename or "translation-source.mp4",
            declared_mime_type=file.content_type or "",
            tenant_id=int(user["tenant_id"]),
            job_id=max(1, int(time.time() * 1000)),
        )
        if stored.file_type != "video":
            raise UploadStorageError("AI translation source must be a video")
        task, created = AiTranslationRepository(conn).create_from_upload(
            int(user["tenant_id"]),
            int(user["id"]),
            client_request_id.strip(),
            stored,
            source_language,
            target_language,
        )
        if not created:
            storage.delete(stored.storage_path)
        else:
            background_tasks.add_task(
                send_task_created_notification,
                TaskCreatedNotification.translation(task),
            )
        return ok(task)
    except UploadStorageError as exc:
        if stored is not None:
            storage.delete(stored.storage_path)
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_UPLOAD", str(exc)),
        )
    except Exception:
        if stored is not None:
            storage.delete(stored.storage_path)
        raise
    finally:
        file.file.close()


@router.post("")
def create_translation_task_from_material(
    payload: AiTranslationMaterialCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    try:
        task, created = AiTranslationRepository(conn).create_from_material(
            int(user["tenant_id"]),
            int(user["id"]),
            payload.client_request_id,
            payload.material_file_id,
            payload.source_language,
            payload.target_language,
        )
        if created:
            background_tasks.add_task(
                send_task_created_notification,
                TaskCreatedNotification.translation(task),
            )
        return ok(task)
    except MaterialLibraryNotFoundError:
        return _not_found("video material asset not found")


@router.get("")
def list_translation_tasks(
    status: TranslationStatus | None = None,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    return ok(
        AiTranslationRepository(conn).list_for_user(
            int(user["tenant_id"]),
            int(user["id"]),
            status or "",
        )
    )


@router.get("/{task_id}")
def get_translation_task(
    task_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    task = AiTranslationRepository(conn).get_for_user(
        int(user["tenant_id"]),
        int(user["id"]),
        task_id,
    )
    return ok(task) if task is not None else _not_found("AI translation task not found")


@router.post("/{task_id}/cancel")
def cancel_translation_task(
    task_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    result = AiTranslationRepository(conn).cancel(
        int(user["tenant_id"]), int(user["id"]), task_id
    )
    return _action_response(result)


@router.post("/{task_id}/accept")
def accept_translation_task(
    task_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    result = AiTranslationRepository(conn).accept(
        int(user["tenant_id"]), int(user["id"]), task_id
    )
    return _action_response(result)


@router.post("/{task_id}/revision")
def request_translation_revision(
    task_id: int,
    payload: AiTranslationRevisionRequest,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    result = AiTranslationRepository(conn).request_revision(
        int(user["tenant_id"]),
        int(user["id"]),
        task_id,
        payload.feedback,
    )
    return _action_response(result)


@router.get("/{task_id}/source/content")
def get_translation_source(
    task_id: int,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    task = AiTranslationRepository(conn).get_for_user(
        int(user["tenant_id"]), int(user["id"]), task_id
    )
    return _source_response(request, task)


@router.get("/{task_id}/deliveries/{delivery_id}/content")
def get_translation_delivery(
    task_id: int,
    delivery_id: int,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    repository = AiTranslationRepository(conn)
    task = repository.get_for_user(int(user["tenant_id"]), int(user["id"]), task_id)
    if task is None:
        return _not_found("AI translation task not found")
    return _delivery_response(request, repository.get_delivery(task_id, delivery_id))


@internal_router.get("")
def list_internal_translation_tasks(
    status: TranslationStatus | None = None,
    keyword: str = Query(default="", max_length=200),
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    return ok(
        AiTranslationRepository(conn).list_for_developer(
            status=status or "",
            keyword=keyword,
        )
    )


@internal_router.get("/{task_id}")
def get_internal_translation_task(
    task_id: int,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    task = AiTranslationRepository(conn).get_for_developer(task_id)
    return ok(task) if task is not None else _not_found("AI translation task not found")


@internal_router.post("/{task_id}/claim")
def claim_internal_translation_task(
    task_id: int,
    payload: AiTranslationActionRequest,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    repository = AiTranslationRepository(conn)
    result = repository.claim(task_id, int(developer["id"]), payload.note)
    _audit_action(conn, result, developer, "ai_translation_claimed", payload.note)
    return _action_response(result)


@internal_router.post("/{task_id}/start")
def start_internal_translation_task(
    task_id: int,
    payload: AiTranslationActionRequest,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    repository = AiTranslationRepository(conn)
    result = repository.start(task_id, int(developer["id"]), payload.note)
    _audit_action(conn, result, developer, "ai_translation_started", payload.note)
    return _action_response(result)


@internal_router.post("/{task_id}/fail")
def fail_internal_translation_task(
    task_id: int,
    payload: AiTranslationActionRequest,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    repository = AiTranslationRepository(conn)
    result = repository.fail(task_id, int(developer["id"]), payload.note)
    _audit_action(conn, result, developer, "ai_translation_failed", payload.note)
    return _action_response(result)


@internal_router.post("/{task_id}/delivery/upload")
def upload_internal_translation_delivery(
    task_id: int,
    request: Request,
    files: list[UploadFile] = File(...),
    note: str = Form(default="", max_length=1000),
    client_request_id: str = Form(default=""),
    resource_type: TranslationDeliveryResourceType = Form(default="video"),
    complete_delivery: bool = Form(default=False),
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    if not files or len(files) > 10:
        return _validation_error("one to ten delivery resources are required")
    if not 8 <= len(client_request_id.strip()) <= 64:
        return _validation_error("client_request_id must contain 8 to 64 characters")
    repository = AiTranslationRepository(conn)
    task = repository.get_for_developer(task_id)
    if task is None:
        return _not_found("AI translation task not found")
    storage = UploadStorageService(
        _delivery_root(request),
        max_bytes=MAX_TRANSLATION_BYTES,
    )
    stored_uploads = []
    accepted_paths: set[str] = set()
    try:
        for upload in files:
            stored = storage.save(
                stream=upload.file,
                original_name=upload.filename or f"translated-{resource_type}",
                declared_mime_type=upload.content_type or "",
                tenant_id=int(task["tenant_id"]),
                job_id=task_id,
            )
            if stored.file_type != DELIVERY_FILE_TYPES[resource_type]:
                storage.delete(stored.storage_path)
                raise UploadStorageError(
                    f"translation delivery must be a {DELIVERY_RESOURCE_LABELS[resource_type]}"
                )
            stored_uploads.append(stored)
        try:
            result, created = repository.deliver(
                task_id,
                int(developer["id"]),
                client_request_id.strip(),
                stored_uploads,
                note.strip(),
                resource_type=resource_type,
                complete_delivery=complete_delivery,
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=409,
                content=fail("INSUFFICIENT_CREDITS", str(exc)),
            )
        if result is not None and "error" in result:
            return _action_response(result)
        if created:
            accepted_paths.update(stored.storage_path for stored in stored_uploads)
            _audit_action(
                conn,
                result,
                developer,
                "ai_translation_delivered",
                note,
                {"delivery_count": len(stored_uploads)},
            )
        return _action_response(result)
    except UploadStorageError as exc:
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_UPLOAD", str(exc)),
        )
    finally:
        for stored in stored_uploads:
            if stored.storage_path not in accepted_paths:
                storage.delete(stored.storage_path)
        for upload in files:
            upload.file.close()


@internal_router.post("/{task_id}/delivery/complete")
def complete_internal_translation_delivery(
    task_id: int,
    payload: AiTranslationActionRequest,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    repository = AiTranslationRepository(conn)
    try:
        result = repository.complete_delivery(
            task_id,
            int(developer["id"]),
            payload.note,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=409,
            content=fail("INSUFFICIENT_CREDITS", str(exc)),
        )
    _audit_action(
        conn,
        result,
        developer,
        "ai_translation_delivery_completed",
        payload.note,
    )
    return _action_response(result)


@internal_router.get("/{task_id}/source/content")
def get_internal_translation_source(
    task_id: int,
    request: Request,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    task = AiTranslationRepository(conn).get_for_developer(task_id)
    return _source_response(request, task)


@internal_router.get("/{task_id}/deliveries/{delivery_id}/content")
def get_internal_translation_delivery(
    task_id: int,
    delivery_id: int,
    request: Request,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
):
    repository = AiTranslationRepository(conn)
    if repository.get_for_developer(task_id) is None:
        return _not_found("AI translation task not found")
    return _delivery_response(request, repository.get_delivery(task_id, delivery_id))


def _source_response(request: Request, task: dict | None):
    if task is None:
        return _not_found("AI translation task not found")
    root = (
        _material_root(request)
        if task["source_type"] == "material_library"
        else _source_upload_root(request)
    )
    path = _resolve_storage_path(root, str(task["source_file_path"]))
    if path is None:
        return _not_found("AI translation source video not found")
    return FileResponse(
        path,
        media_type=str(task["source_mime_type"] or "video/mp4"),
        filename=str(task["source_file_name"] or path.name),
        headers={"Cache-Control": "private, max-age=300"},
    )


def _delivery_response(request: Request, delivery: dict | None):
    if delivery is None:
        return _not_found("AI translation delivery not found")
    path = _resolve_storage_path(_delivery_root(request), str(delivery["file_path"]))
    if path is None:
        return _not_found("AI translation delivery not found")
    return FileResponse(
        path,
        media_type=str(delivery["mime_type"] or "video/mp4"),
        filename=str(delivery["file_name"] or path.name),
        headers={"Cache-Control": "private, max-age=300"},
    )


def _audit_action(
    conn,
    task: dict | None,
    developer: dict,
    action: str,
    note: str,
    detail: dict | None = None,
) -> None:
    if task is None or "error" in task:
        return
    AdminAuditRepository(conn).create(
        tenant_id=int(task["tenant_id"]),
        admin_user_id=int(developer["id"]),
        action=action,
        target_type="ai_translation_task",
        target_id=int(task["id"]),
        detail={"note": note, **(detail or {})},
    )


def _action_response(result: dict | None):
    if result is None:
        return _not_found("AI translation task not found")
    if "error" in result:
        return JSONResponse(
            status_code=409,
            content=fail("STATE_CONFLICT", result["error"]),
        )
    return ok(result)


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(status_code=404, content=fail("NOT_FOUND", message))


def _validation_error(message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content=fail("VALIDATION_ERROR", message))


def _resolve_storage_path(root: Path, relative_path: str) -> Path | None:
    if not relative_path.strip():
        return None
    safe_root = root.resolve()
    path = (safe_root / relative_path).resolve()
    try:
        path.relative_to(safe_root)
    except ValueError:
        return None
    return path if path.is_file() else None


def _source_upload_root(request: Request) -> Path:
    return Path(request.app.state.config.data_dir) / "ai_translation_uploads"


def _delivery_root(request: Request) -> Path:
    return Path(request.app.state.config.data_dir) / "ai_translation_deliveries"


def _material_root(request: Request) -> Path:
    return Path(request.app.state.config.data_dir) / "product_materials"
