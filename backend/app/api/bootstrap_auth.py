from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection
from app.core.responses import fail, ok
from app.schemas.auth import RegisterRequest
from app.services.auth_service import AuthError, AuthService


router = APIRouter(
    prefix="/api/auth",
    tags=["bootstrap-auth"],
    include_in_schema=False,
)


@router.post("/register")
def register(
    payload: RegisterRequest,
    request: Request,
    conn=Depends(get_db_connection),
) -> dict:
    try:
        result = AuthService(conn, request.app.state.config).register(payload)
    except AuthError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(exc.code, exc.message),
        )
    return ok(result.model_dump())
