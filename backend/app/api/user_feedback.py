from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_customer_user, require_developer_user
from app.core.responses import fail, ok
from app.repositories.user_feedback_repository import (
    UserFeedbackNotFoundError,
    UserFeedbackRepository,
)
from app.schemas.user_feedback import DeveloperFeedbackUpdate, UserFeedbackCreate


customer_router = APIRouter(prefix="/api/user-feedback", tags=["user-feedback"])
developer_router = APIRouter(
    prefix="/api/developer/user-feedback",
    tags=["developer-user-feedback"],
    include_in_schema=False,
)


@customer_router.post("")
def create_feedback(
    payload: UserFeedbackCreate,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        UserFeedbackRepository(conn).create(
            int(user["tenant_id"]),
            int(user["id"]),
            payload,
        )
    )


@customer_router.get("")
def list_feedback(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Literal["", "pending", "in_progress", "completed"] = "",
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        UserFeedbackRepository(conn).list_for_user(
            int(user["tenant_id"]),
            int(user["id"]),
            page,
            page_size,
            status,
        )
    )


@developer_router.get("")
def list_developer_feedback(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Literal["", "pending", "in_progress", "completed"] = "",
    keyword: str = Query(default="", max_length=100),
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        UserFeedbackRepository(conn).list_for_developer(
            page,
            page_size,
            status,
            keyword.strip(),
        )
    )


@developer_router.put("/{feedback_id}")
def update_developer_feedback(
    feedback_id: int,
    payload: DeveloperFeedbackUpdate,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            UserFeedbackRepository(conn).update_for_developer(
                feedback_id,
                int(developer["id"]),
                payload,
            )
        )
    except UserFeedbackNotFoundError:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", "需求反馈不存在"),
        )
