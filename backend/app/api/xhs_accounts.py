import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_customer_user
from app.core.responses import fail, ok
from app.repositories.xhs_account_login_repository import XHSAccountLoginRepository
from app.repositories.xhs_account_repository import XHSAccountRepository
from app.schemas.xhs_account import (
    XHSAccountCreate,
    XHSAccountProfile,
    XHSAccountProfileUpdate,
    XHSAccountUpdate,
)
from app.services.xhs_account_login_service import (
    LOGIN_SESSION_SECONDS,
    build_login_state_path,
    check_xhs_account_login,
    run_xhs_account_login,
    to_public_login_session,
)


router = APIRouter(prefix="/api/xhs-accounts", tags=["xhs-accounts"])


def _public_account(account: dict | None) -> dict | None:
    if account is None:
        return None
    result = account.copy()
    result["login_state_ready"] = bool(result.pop("login_state_path", ""))
    return result


@router.post("")
def create_xhs_account(
    payload: XHSAccountCreate,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = XHSAccountRepository(conn)
    account_id = repo.create(user["id"], payload)
    return ok(_public_account(repo.get_for_user(user["id"], account_id)))


@router.get("")
def list_xhs_accounts(
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = XHSAccountRepository(conn)
    return ok([_public_account(account) for account in repo.list_by_user(user["id"])])


@router.put("/{account_id}")
def update_xhs_account(
    account_id: int,
    payload: XHSAccountUpdate,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = XHSAccountRepository(conn)
    account = repo.get_for_user(user["id"], account_id)
    if account is None:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", "xhs account not found"),
        )

    values = {
        "display_name": account["display_name"],
        "account_group": account["account_group"],
        "daily_limit": account["daily_limit"],
        "min_interval_minutes": account["min_interval_minutes"],
        "profile": account["profile"].copy(),
    }
    updates = payload.model_dump(exclude_unset=True)
    profile_updates = updates.pop("profile", None)
    values.update(updates)
    if profile_updates:
        values["profile"].update(profile_updates)

    updated = repo.update(user["id"], account_id, XHSAccountCreate(**values))
    if not updated:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", "xhs account not found"),
        )
    return ok(_public_account(repo.get_for_user(user["id"], account_id)))


@router.delete("/{account_id}")
def delete_xhs_account(
    account_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    result = XHSAccountRepository(conn).delete(user["id"], account_id)
    if result == "not_found":
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", "xhs account not found"),
        )
    if result == "in_use":
        return JSONResponse(
            status_code=409,
            content=fail(
                "ACCOUNT_IN_USE",
                "账号仍有关联的发布或视频任务，请先完成或取消相关任务",
            ),
        )
    return ok({"deleted": True})


@router.put("/{account_id}/profile")
def update_xhs_account_profile(
    account_id: int,
    payload: XHSAccountProfileUpdate,
    user: dict = Depends(require_customer_user),
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

    return ok(_public_account(repo.get_for_user(user["id"], account_id)))


@router.post("/{account_id}/login/start")
def start_xhs_account_login(
    account_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    account = XHSAccountRepository(conn).get_for_user(user["id"], account_id)
    if account is None:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", "xhs account not found"),
        )

    operation_token = uuid.uuid4().hex
    now = int(time.time())
    login_state_path = build_login_state_path(
        request.app.state.config.data_dir,
        int(user["tenant_id"]),
        int(user["id"]),
        account_id,
    )
    session_repo = XHSAccountLoginRepository(conn)
    session_id = session_repo.create(
        tenant_id=int(user["tenant_id"]),
        user_id=int(user["id"]),
        account_id=account_id,
        operation_token=operation_token,
        login_state_path=str(login_state_path),
        expires_time=now + LOGIN_SESSION_SECONDS,
    )
    background_tasks.add_task(
        run_xhs_account_login,
        request.app.state.connect_db,
        user_id=int(user["id"]),
        account_id=account_id,
        session_id=session_id,
        operation_token=operation_token,
        login_state_path=str(login_state_path),
    )
    session = session_repo.get_for_user(user["id"], account_id, session_id)
    return JSONResponse(
        status_code=202,
        content=ok(to_public_login_session(session)),
    )


@router.get("/{account_id}/login/session")
def get_latest_xhs_account_login_session(
    account_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    account = XHSAccountRepository(conn).get_for_user(user["id"], account_id)
    if account is None:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", "xhs account not found"),
        )
    session = XHSAccountLoginRepository(conn).get_latest_for_user(
        user["id"],
        account_id,
    )
    return ok(to_public_login_session(session) if session else None)


@router.post("/{account_id}/login/check")
async def check_xhs_account_login_status(
    account_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    valid, account = await check_xhs_account_login(conn, user["id"], account_id)
    if account is None:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", "xhs account not found"),
        )
    return ok({
        "valid": valid,
        "account": _public_account(account),
    })
