from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_customer_user
from app.core.responses import fail, ok
from app.repositories.content_draft_repository import ContentDraftRepository
from app.repositories.material_library_repository import MaterialLibraryNotFoundError
from app.repositories.product_repository import ProductRepository
from app.repositories.xhs_account_repository import XHSAccountRepository
from app.schemas.content_draft import (
    ContentDraftGenerateRequest,
    ContentDraftManualCreateRequest,
    ContentDraftUpdateRequest,
)
from app.services.material_library_service import MaterialLibraryService
from app.services.product_copy_service import generate_product_content_draft


router = APIRouter(prefix="/api/content-drafts", tags=["content-drafts"])


@router.post("/manual")
def create_manual_content_draft(
    payload: ContentDraftManualCreateRequest,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    account = XHSAccountRepository(conn).get_for_user(user["id"], payload.xhs_account_id)
    if account is None:
        return _not_found("xhs account not found")
    if int(account["status"]) != 1 or not str(account["login_state_path"] or "").strip():
        return _validation_error("xhs account login state is not ready")

    try:
        storage_root = Path(request.app.state.config.data_dir) / "product_materials"
        image_paths = MaterialLibraryService(conn, storage_root).resolve_asset_paths(
            user["tenant_id"],
            payload.material_ids,
            required_file_type="image",
        )
    except MaterialLibraryNotFoundError as exc:
        return _not_found(str(exc))
    except ValueError as exc:
        return _validation_error(str(exc))
    if not image_paths:
        return _validation_error("at least one image material is required")

    repo = ContentDraftRepository(conn)
    draft_id = repo.create_manual_draft(
        user["id"],
        payload,
        {
            "material_ids": payload.material_ids,
            "image_paths": image_paths,
        },
    )
    return ok(repo.get_for_user(user["id"], draft_id))


@router.post("/product-copy")
def generate_product_copy(
    payload: ContentDraftGenerateRequest,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    product_repo = ProductRepository(conn)
    product = product_repo.get_for_user(user["id"], payload.product_id)
    if product is None:
        return _not_found("product not found")

    account = None
    if payload.xhs_account_id > 0:
        account = XHSAccountRepository(conn).get_for_user(user["id"], payload.xhs_account_id)
        if account is None:
            return _not_found("xhs account not found")

    generated = generate_product_content_draft(product, account, payload)
    repo = ContentDraftRepository(conn)
    draft_id = repo.create_draft(user["id"], payload, generated)
    return ok(repo.get_for_user(user["id"], draft_id))


@router.get("")
def list_content_drafts(
    product_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None, pattern="^(draft|confirmed|rejected)$"),
    source_type: str | None = Query(default=None, max_length=30),
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = ContentDraftRepository(conn)
    return ok(
        repo.list_by_user(
            user["id"],
            product_id=product_id,
            status=status,
            source_type=source_type,
        )
    )


@router.patch("/{draft_id}")
def update_content_draft(
    draft_id: int,
    payload: ContentDraftUpdateRequest,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = ContentDraftRepository(conn)
    draft = repo.update_for_user(user["id"], draft_id, payload)
    if draft is None:
        return _not_found("content draft not found")
    return ok(draft)


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
