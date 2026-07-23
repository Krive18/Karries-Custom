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
    user_id: int | None = Query(default=None, ge=1),
    start_time: int | None = Query(default=None, ge=0),
    end_time: int | None = Query(default=None, ge=0),
    product_id: int | None = Query(default=None, ge=1),
    keyword: str | None = Query(default=None, min_length=1, max_length=200),
    user: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        InspirationService(conn).list_sessions_for_admin(
            user,
            page,
            page_size,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            product_id=product_id,
            keyword=keyword,
        )
    )


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
