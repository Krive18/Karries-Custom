from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.dependencies import current_user, get_db_connection
from app.core.responses import fail, ok
from app.schemas.inspiration import InspirationMessageCreate, InspirationSessionCreate
from app.services.inspiration_service import InspirationProviderError, InspirationService


router = APIRouter(prefix="/api/inspiration", tags=["inspiration"])


@router.post("/sessions")
def create_session(
    payload: InspirationSessionCreate,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(InspirationService(conn).create_session(user, payload))


@router.get("/sessions")
def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(InspirationService(conn).list_sessions(user, page, page_size))


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    detail = InspirationService(conn).get_session(user, session_id)
    return ok(detail) if detail is not None else _not_found("inspiration session not found")


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: int,
    payload: InspirationMessageCreate,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(InspirationService(conn).send_message(user, session_id, payload))
    except LookupError:
        return _not_found("inspiration session not found")
    except ValueError:
        return JSONResponse(
            status_code=400,
            content=fail("SESSION_ARCHIVED", "inspiration session is archived"),
        )
    except InspirationProviderError:
        return JSONResponse(
            status_code=502,
            content=fail("AI_PROVIDER_ERROR", "AI provider request failed"),
        )


@router.post("/sessions/{session_id}/archive")
def archive_session(
    session_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    session = InspirationService(conn).archive_session(user, session_id)
    return ok(session) if session is not None else _not_found("inspiration session not found")


@router.post("/messages/{message_id}/save-draft")
def save_draft(
    message_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    draft_id = InspirationService(conn).save_draft(user, message_id)
    if draft_id is None:
        return _not_found("inspiration assistant message not found")
    return ok({"draft_id": draft_id})


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(status_code=404, content=fail("NOT_FOUND", message))
