from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.dependencies import current_user
from app.core.responses import fail, ok
from app.schemas.auth import LoginRequest, RegisterRequest, UserView
from app.services.auth_service import AuthError, AuthService


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
def register(payload: RegisterRequest, request: Request) -> dict:
    try:
        result = AuthService(request.app.state.conn, request.app.state.config).register(
            payload.login_name,
            payload.nickname,
            payload.password,
            payload.invite_code,
        )
    except AuthError as exc:
        return JSONResponse(status_code=400, content=fail("AUTH_ERROR", str(exc)))
    return ok(result.model_dump())


@router.post("/login")
def login(payload: LoginRequest, request: Request) -> dict:
    try:
        result = AuthService(request.app.state.conn, request.app.state.config).login(
            payload.login_name,
            payload.password,
        )
    except AuthError as exc:
        return JSONResponse(status_code=400, content=fail("AUTH_ERROR", str(exc)))
    return ok(result.model_dump())


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    return ok(
        UserView(
            id=user["id"],
            login_name=user["login_name"],
            nickname=user["nickname"],
            user_role=user["user_role"],
            status=user["status"],
        ).model_dump()
    )
