from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.dependencies import get_current_user, get_db_connection
from app.core.responses import fail, ok
from app.repositories.wallet_repository import WalletRepository
from app.schemas.auth import AuthUser, LoginRequest, RegisterRequest
from app.services.auth_service import AuthError, AuthService


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
def register(payload: RegisterRequest, request: Request, conn=Depends(get_db_connection)) -> dict:
    try:
        result = AuthService(conn, request.app.state.config).register(payload)
    except AuthError as exc:
        return JSONResponse(status_code=exc.status_code, content=fail(exc.code, exc.message))
    return ok(result.model_dump())


@router.post("/login")
def login(payload: LoginRequest, request: Request, conn=Depends(get_db_connection)) -> dict:
    try:
        result = AuthService(conn, request.app.state.config).login(payload)
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
            login_name=user["login_name"],
            nickname=user["nickname"],
            user_role=user["user_role"],
            wallet_balance=wallet_balance,
        ).model_dump()
    )
