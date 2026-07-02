from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.dependencies import current_user, get_db_connection
from app.core.responses import fail, ok
from app.repositories.xhs_account_repository import XHSAccountRepository
from app.schemas.xhs_account import XHSAccountCreate, XHSAccountProfile, XHSAccountProfileUpdate


router = APIRouter(prefix="/api/xhs-accounts", tags=["xhs-accounts"])


@router.post("")
def create_xhs_account(
    payload: XHSAccountCreate,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = XHSAccountRepository(conn)
    account_id = repo.create(user["id"], payload)
    return ok(repo.get_for_user(user["id"], account_id))


@router.get("")
def list_xhs_accounts(
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = XHSAccountRepository(conn)
    return ok(repo.list_by_user(user["id"]))


@router.put("/{account_id}/profile")
def update_xhs_account_profile(
    account_id: int,
    payload: XHSAccountProfileUpdate,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = XHSAccountRepository(conn)
    account = repo.get_for_user(user["id"], account_id)
    if account is None:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", "xhs account not found"),
        )

    profile_data = account["profile"].copy()
    profile_data.update(payload.model_dump(exclude_unset=True))
    updated = repo.update_profile(user["id"], account_id, XHSAccountProfile(**profile_data))
    if not updated:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", "xhs account not found"),
        )

    return ok(repo.get_for_user(user["id"], account_id))
