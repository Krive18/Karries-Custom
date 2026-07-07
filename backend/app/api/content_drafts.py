from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.dependencies import current_user, get_db_connection
from app.core.responses import fail, ok
from app.repositories.content_draft_repository import ContentDraftRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.xhs_account_repository import XHSAccountRepository
from app.schemas.content_draft import ContentDraftGenerateRequest, ContentDraftUpdateRequest
from app.services.product_copy_service import generate_product_content_draft


router = APIRouter(prefix="/api/content-drafts", tags=["content-drafts"])


@router.post("/product-copy")
def generate_product_copy(
    payload: ContentDraftGenerateRequest,
    user: dict = Depends(current_user),
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
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = ContentDraftRepository(conn)
    return ok(repo.list_by_user(user["id"], product_id=product_id, status=status))


@router.patch("/{draft_id}")
def update_content_draft(
    draft_id: int,
    payload: ContentDraftUpdateRequest,
    user: dict = Depends(current_user),
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
