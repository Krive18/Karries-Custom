from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_management_user
from app.core.responses import fail, ok
from app.services.inspiration_service import InspirationService


router = APIRouter(prefix="/api/admin/inspiration", tags=["admin-inspiration"])


@router.get("/sessions")
def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(InspirationService(conn).list_sessions_for_admin(user, page, page_size))


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    user: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    detail = InspirationService(conn).get_session_for_admin(user, session_id)
    if detail is None:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", "inspiration session not found"),
        )
    return ok(detail)
