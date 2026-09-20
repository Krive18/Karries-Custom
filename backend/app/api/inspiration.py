from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.core.dependencies import get_db_connection, require_customer_user
from app.core.responses import fail, ok
from app.schemas.inspiration import (
    InspirationMessageCreate,
    InspirationMessageRevisionCreate,
    InspirationPersonalizationPreferenceUpdate,
    InspirationPersonalizationTemplateCreate,
    InspirationPersonalizationTemplateUpdate,
    InspirationPersonalizationUpdate,
    InspirationSessionCreate,
    InspirationSessionPin,
    InspirationSessionRename,
)
from app.services.ai_personalization_service import AIPersonalizationService
from app.repositories.inspiration_repository import (
    InspirationRequestConflictError,
    InspirationSessionNotFoundError,
    InspirationSessionStateError,
)
from app.services.inspiration_service import (
    InspirationCreditError,
    InspirationProviderError,
    InspirationService,
)
from app.services.upload_storage_service import UploadStorageError, UploadStorageService


router = APIRouter(prefix="/api/inspiration", tags=["inspiration"])


def _attachment_root(request: Request) -> Path:
    return Path(request.app.state.config.data_dir) / "inspiration_attachments"


def _without_internal_attachment_paths(value):
    if isinstance(value, dict):
        return {
            key: _without_internal_attachment_paths(item)
            for key, item in value.items()
            if key != "storage_path"
        }
    if isinstance(value, list):
        return [_without_internal_attachment_paths(item) for item in value]
    return value


@router.get("/personalization")
def get_personalization(
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(AIPersonalizationService(conn).get_for_user(user))


@router.put("/personalization")
def update_personalization(
    payload: InspirationPersonalizationUpdate,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(AIPersonalizationService(conn).update_for_user(user, payload))


@router.get("/personalization/templates")
def list_personalization_templates(
    include_archived: bool = Query(default=False),
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AIPersonalizationService(conn).list_templates(
            user, include_archived=include_archived
        )
    )


@router.post("/personalization/templates")
def create_personalization_template(
    payload: InspirationPersonalizationTemplateCreate,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(AIPersonalizationService(conn).create_template(user, payload))


@router.put("/personalization/templates/{template_id}")
def update_personalization_template(
    template_id: int,
    payload: InspirationPersonalizationTemplateUpdate,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    template = AIPersonalizationService(conn).update_template(
        user, template_id, payload
    )
    return ok(template) if template is not None else _not_found(
        "personalization template not found"
    )


@router.post("/personalization/templates/{template_id}/duplicate")
def duplicate_personalization_template(
    template_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    template = AIPersonalizationService(conn).duplicate_template(user, template_id)
    return ok(template) if template is not None else _not_found(
        "personalization template not found"
    )


@router.delete("/personalization/templates/{template_id}")
def archive_personalization_template(
    template_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    template = AIPersonalizationService(conn).archive_template(user, template_id)
    return ok(template) if template is not None else _not_found(
        "personalization template not found"
    )


@router.get("/personalization/preference")
def get_personalization_preference(
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(AIPersonalizationService(conn).get_preference(user))


@router.put("/personalization/preference")
def update_personalization_preference(
    payload: InspirationPersonalizationPreferenceUpdate,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(AIPersonalizationService(conn).update_preference(user, payload))
    except LookupError:
        return _not_found("personalization template not found")


@router.post("/sessions")
def create_session(
    payload: InspirationSessionCreate,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(InspirationService(conn).create_session(user, payload))
    except LookupError:
        return _not_found("linked product or xhs account not found")


@router.get("/sessions")
def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    interaction_mode: str | None = Query(default=None, pattern="^(normal|personalized)$"),
    personalization_template_id: int | None = Query(default=None, ge=0),
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        InspirationService(conn).list_sessions(
            user,
            page,
            page_size,
            interaction_mode=interaction_mode,
            personalization_template_id=personalization_template_id,
        )
    )


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    detail = InspirationService(conn).get_session(user, session_id)
    return (
        ok(_without_internal_attachment_paths(detail))
        if detail is not None
        else _not_found("inspiration session not found")
    )


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: int,
    payload: InspirationMessageCreate,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            _without_internal_attachment_paths(
                InspirationService(conn).send_message(
                    user,
                    session_id,
                    payload,
                    _attachment_root(request),
                )
            )
        )
    except InspirationSessionNotFoundError:
        return _not_found("inspiration session not found")
    except InspirationSessionStateError as exc:
        if exc.status == "generating":
            return JSONResponse(
                status_code=409,
                content=fail("SESSION_GENERATING", "inspiration session is generating"),
            )
        return JSONResponse(
            status_code=400,
            content=fail("SESSION_ARCHIVED", "inspiration session is archived"),
        )
    except InspirationRequestConflictError:
        return JSONResponse(
            status_code=409,
            content=fail(
                "IDEMPOTENCY_CONFLICT",
                "client request id was already used with different content",
            ),
        )
    except InspirationCreditError as exc:
        return JSONResponse(
            status_code=402,
            content=fail("INSUFFICIENT_CREDITS", str(exc)),
        )
    except InspirationProviderError:
        return JSONResponse(
            status_code=502,
            content=fail("AI_PROVIDER_ERROR", "AI provider request failed"),
        )


@router.post("/sessions/{session_id}/messages/{message_id}/revisions")
def revise_message(
    session_id: int,
    message_id: int,
    payload: InspirationMessageRevisionCreate,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            _without_internal_attachment_paths(
                InspirationService(conn).revise_message(
                    user,
                    session_id,
                    message_id,
                    payload,
                    _attachment_root(request),
                )
            )
        )
    except InspirationSessionNotFoundError:
        return _not_found("inspiration message not found")
    except InspirationSessionStateError as exc:
        if exc.status == "generating":
            return JSONResponse(
                status_code=409,
                content=fail("SESSION_GENERATING", "inspiration session is generating"),
            )
        return JSONResponse(
            status_code=400,
            content=fail("SESSION_ARCHIVED", "inspiration session is archived"),
        )
    except InspirationRequestConflictError:
        return JSONResponse(
            status_code=409,
            content=fail(
                "IDEMPOTENCY_CONFLICT",
                "client request id was already used with different content",
            ),
        )
    except InspirationCreditError as exc:
        return JSONResponse(
            status_code=402,
            content=fail("INSUFFICIENT_CREDITS", str(exc)),
        )
    except InspirationProviderError:
        return JSONResponse(
            status_code=502,
            content=fail("AI_PROVIDER_ERROR", "AI provider request failed"),
        )


@router.post("/sessions/{session_id}/messages/{message_id}/activate")
def activate_message_branch(
    session_id: int,
    message_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            _without_internal_attachment_paths(
                InspirationService(conn).activate_message_branch(
                    user, session_id, message_id
                )
            )
        )
    except InspirationSessionNotFoundError:
        return _not_found("inspiration message not found")
    except InspirationSessionStateError:
        return JSONResponse(
            status_code=409,
            content=fail("SESSION_GENERATING", "inspiration session is generating"),
        )


@router.post("/sessions/{session_id}/attachments")
def upload_attachment(
    session_id: int,
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = InspirationService(conn).repository
    session = repository.get_session_for_user(
        int(user["tenant_id"]), int(user["id"]), session_id
    )
    if session is None:
        return _not_found("inspiration session not found")
    if session["status"] != "active":
        return JSONResponse(
            status_code=409,
            content=fail("SESSION_NOT_ACTIVE", "inspiration session is not active"),
        )

    storage = UploadStorageService(
        _attachment_root(request),
        max_bytes=10 * 1024 * 1024,
    )
    stored = None
    try:
        stored = storage.save(
            stream=file.file,
            original_name=file.filename or "image",
            declared_mime_type=file.content_type or "",
            tenant_id=int(user["tenant_id"]),
            job_id=session_id,
        )
        if stored.file_type != "image":
            storage.delete(stored.storage_path)
            return JSONResponse(
                status_code=400,
                content=fail("IMAGE_REQUIRED", "only JPG, PNG and WEBP images are supported"),
            )
        attachment = repository.create_attachment(
            int(user["tenant_id"]),
            int(user["id"]),
            session_id,
            file_name=stored.file_name,
            mime_type=stored.mime_type,
            file_size=stored.file_size,
            storage_path=stored.storage_path,
        )
        attachment.pop("storage_path", None)
        return ok(attachment)
    except UploadStorageError as exc:
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_ATTACHMENT", str(exc)),
        )
    except Exception:
        conn.rollback()
        if stored is not None:
            storage.delete(stored.storage_path)
        raise
    finally:
        file.file.close()


@router.get("/attachments/{attachment_id}/content")
def get_attachment_content(
    attachment_id: int,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    attachment = InspirationService(conn).repository.get_attachment_for_user(
        int(user["tenant_id"]), int(user["id"]), attachment_id
    )
    if attachment is None:
        return _not_found("inspiration attachment not found")
    root = _attachment_root(request).resolve()
    path = (root / attachment["storage_path"]).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return _not_found("inspiration attachment not found")
    if not path.is_file():
        return _not_found("inspiration attachment not found")
    return FileResponse(
        path,
        media_type=attachment["mime_type"],
        filename=attachment["file_name"],
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.post("/sessions/{session_id}/archive")
def archive_session(
    session_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(InspirationService(conn).archive_session(user, session_id))
    except InspirationSessionNotFoundError:
        return _not_found("inspiration session not found")
    except InspirationSessionStateError as exc:
        if exc.status == "generating":
            return JSONResponse(
                status_code=409,
                content=fail("SESSION_GENERATING", "inspiration session is generating"),
            )
        return JSONResponse(
            status_code=400,
            content=fail("SESSION_ARCHIVED", "inspiration session is archived"),
        )


@router.patch("/sessions/{session_id}/pin")
def pin_session(
    session_id: int,
    payload: InspirationSessionPin,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            InspirationService(conn).set_session_pinned(
                user,
                session_id,
                payload.is_pinned,
            )
        )
    except InspirationSessionNotFoundError:
        return _not_found("inspiration session not found")


@router.patch("/sessions/{session_id}")
def rename_session(
    session_id: int,
    payload: InspirationSessionRename,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            InspirationService(conn).rename_session(
                user,
                session_id,
                payload.title,
            )
        )
    except InspirationSessionNotFoundError:
        return _not_found("inspiration session not found")


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        InspirationService(conn).delete_session(user, session_id)
        return ok({"deleted": True})
    except InspirationSessionNotFoundError:
        return _not_found("inspiration session not found")
    except InspirationSessionStateError:
        return JSONResponse(
            status_code=409,
            content=fail(
                "SESSION_GENERATING",
                "inspiration session is generating",
            ),
        )


@router.post("/messages/{message_id}/save-collection")
@router.post("/messages/{message_id}/save-draft", deprecated=True)
def save_to_collection(
    message_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    collection_id = InspirationService(conn).save_to_collection(user, message_id)
    if collection_id is None:
        return _not_found("inspiration assistant message not found")
    return ok({"collection_id": collection_id})


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(status_code=404, content=fail("NOT_FOUND", message))
