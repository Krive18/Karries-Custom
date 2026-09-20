from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.dependencies import get_current_user, get_db_connection
from app.core.responses import fail, ok
from app.repositories.wallet_repository import WalletRepository
from app.schemas.auth import AuthPortal, AuthUser, LoginRequest
from app.services.auth_service import AuthError, AuthService


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/{portal}/login")
def login(
    portal: AuthPortal,
    payload: LoginRequest,
    request: Request,
    conn=Depends(get_db_connection),
) -> dict:
    surface = request.app.state.api_surface
    if surface != "all" and surface != portal:
        return JSONResponse(
            status_code=404,
            content=fail("PORTAL_NOT_FOUND", "当前登录入口不可用"),
        )
    try:
        result = AuthService(conn, request.app.state.config).login_for_portal(
            payload,
            portal,
        )
    except AuthError as exc:
        return JSONResponse(status_code=exc.status_code, content=fail(exc.code, exc.message))
    return ok(result.model_dump())


@router.get("/me")
def me(
    user: dict = Depends(get_current_user),
    conn=Depends(get_db_connection),
) -> dict:
    wallet = WalletRepository(conn).get_wallet(user["id"])
    wallet_balance = int(wallet["balance"]) if wallet is not None else 0
    return ok(
        AuthUser(
            id=user["id"],
            tenant_id=user["tenant_id"],
            login_name=user["login_name"],
            nickname=user["nickname"],
            user_role=user["user_role"],
            wallet_balance=wallet_balance,
        ).model_dump()
    )
