from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_management_user
from app.core.responses import fail, ok
from app.schemas.admin_users import (
    AdminEmployeeCreate,
    AdminEmployeePasswordReset,
    AdminEmployeeStatusUpdate,
    AdminEmployeeUpdate,
)
from app.services.admin_user_service import AdminUserError, AdminUserService


router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


def _error_response(exc: AdminUserError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(exc.code, exc.message),
    )


@router.get("")
def list_employees(
    keyword: str = "",
    status: int | None = Query(default=None, ge=1, le=2),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AdminUserService(conn).list_employees(
            manager,
            keyword=keyword,
            status=status,
            page=page,
            page_size=page_size,
        )
    )


@router.post("")
def create_employee(
    payload: AdminEmployeeCreate,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        result = AdminUserService(conn).create_employee(manager, payload)
        if result.get("approval_required"):
            return JSONResponse(status_code=202, content=ok(result))
        return ok(result)
    except AdminUserError as exc:
        return _error_response(exc)


@router.get("/summary")
def get_employee_summary(
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(AdminUserService(conn).get_summary(manager))


@router.get("/creation-requests")
def list_creation_requests(
    status: str | None = Query(default=None, pattern="^(pending|approved|rejected)$"),
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AdminUserService(conn).list_creation_requests(
            status=status,
            tenant_id=int(manager["tenant_id"]),
        )
    )


@router.get("/{user_id}")
def get_employee(
    user_id: int,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(AdminUserService(conn).get_employee(manager, user_id))
    except AdminUserError as exc:
        return _error_response(exc)


@router.patch("/{user_id}")
def update_employee(
    user_id: int,
    payload: AdminEmployeeUpdate,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(AdminUserService(conn).update_employee(manager, user_id, payload))
    except AdminUserError as exc:
        return _error_response(exc)


@router.put("/{user_id}/password")
def reset_employee_password(
    user_id: int,
    payload: AdminEmployeePasswordReset,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(AdminUserService(conn).reset_password(manager, user_id, payload))
    except AdminUserError as exc:
        return _error_response(exc)


@router.patch("/{user_id}/status")
def update_employee_status(
    user_id: int,
    payload: AdminEmployeeStatusUpdate,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(AdminUserService(conn).update_status(manager, user_id, payload))
    except AdminUserError as exc:
        return _error_response(exc)
