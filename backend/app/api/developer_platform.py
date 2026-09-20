import time
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_developer_user
from app.core.responses import fail, ok
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.developer_alert_repository import DeveloperAlertRepository
from app.repositories.developer_platform_repository import DeveloperPlatformRepository
from app.repositories.matrix_plan_repository import MatrixPlanRepository
from app.schemas.developer_platform import DeveloperActionReason
from app.schemas.developer_platform import (
    DeveloperAccountCreate,
    DeveloperAccountPasswordReset,
    DeveloperAccountStatusUpdate,
)
from app.repositories.developer_access_repository import DeveloperAccessRepository
from app.services.developer_access_service import DeveloperAccessError, DeveloperAccessService
from app.services.developer_platform_service import DeveloperPlatformService
from app.services.admin_user_service import AdminUserError, AdminUserService


router = APIRouter(
    prefix="/api/developer/platform",
    tags=["developer-platform"],
    include_in_schema=False,
)


@router.get("/overview")
def get_overview(
    request: Request,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(DeveloperPlatformService(conn, request).overview())


@router.get("/tasks")
def list_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    kind: Literal["viral_analysis", "video_edit", "matrix_publish"] | None = None,
    status: Literal["pending", "running", "completed", "failed", "cancelled"] | None = None,
    keyword: str = Query(default="", max_length=100),
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        DeveloperPlatformRepository(conn).list_tasks(
            page=page,
            page_size=page_size,
            kind=kind,
            status=status,
            keyword=keyword.strip(),
        )
    )


def _matrix_action(
    *,
    action: Literal["cancel", "retry"],
    task_id: int,
    body: DeveloperActionReason,
    developer: dict,
    conn,
) -> dict | JSONResponse:
    owner = DeveloperPlatformRepository(conn).get_matrix_plan_owner(task_id)
    if owner is None:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", "Task not found"))
    matrix_repository = MatrixPlanRepository(conn)
    result = (
        matrix_repository.cancel_plan(int(owner["user_id"]), task_id)
        if action == "cancel"
        else matrix_repository.retry_failed_items(int(owner["user_id"]), task_id)
    )
    if result is None:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", "Task not found"))
    if "error" in result:
        return JSONResponse(
            status_code=409,
            content=fail("INVALID_STATUS", str(result["error"])),
        )
    AdminAuditRepository(conn).create(
        tenant_id=int(owner["tenant_id"]),
        admin_user_id=int(developer["id"]),
        action=f"developer.task.{action}",
        target_type="matrix_publish_plan",
        target_id=task_id,
        detail={"reason": body.reason.strip(), "previous_status": int(owner["status"])},
    )
    return ok(result)


@router.post("/tasks/matrix_publish/{task_id}/cancel", response_model=None)
def cancel_matrix_task(
    task_id: int,
    body: DeveloperActionReason,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> object:
    return _matrix_action(
        action="cancel",
        task_id=task_id,
        body=body,
        developer=developer,
        conn=conn,
    )


@router.post("/tasks/matrix_publish/{task_id}/retry", response_model=None)
def retry_matrix_task(
    task_id: int,
    body: DeveloperActionReason,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> object:
    return _matrix_action(
        action="retry",
        task_id=task_id,
        body=body,
        developer=developer,
        conn=conn,
    )


@router.get("/alerts")
def list_alerts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Literal["open", "acknowledged", "resolved"] | None = None,
    severity: Literal["page", "ticket"] | None = None,
    alert_type: str | None = Query(default=None, max_length=50),
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = DeveloperAlertRepository(conn)
    repository.sync()
    return ok(
        repository.list(
            page=page,
            page_size=page_size,
            status=status,
            severity=severity,
            alert_type=alert_type,
        )
    )


def _transition_alert(
    *,
    alert_id: int,
    action: Literal["acknowledge", "resolve"],
    body: DeveloperActionReason,
    developer: dict,
    conn,
) -> object:
    result = DeveloperAlertRepository(conn).transition(
        alert_id=alert_id,
        action=action,
        reason=body.reason.strip(),
        developer_id=int(developer["id"]),
    )
    if result is None:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", "Alert not found"))
    if "error" in result:
        return JSONResponse(
            status_code=409,
            content=fail("INVALID_STATUS", str(result["error"])),
        )
    return ok(result)


@router.post("/alerts/{alert_id}/acknowledge", response_model=None)
def acknowledge_alert(
    alert_id: int,
    body: DeveloperActionReason,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> object:
    return _transition_alert(
        alert_id=alert_id,
        action="acknowledge",
        body=body,
        developer=developer,
        conn=conn,
    )


@router.post("/alerts/{alert_id}/resolve", response_model=None)
def resolve_alert(
    alert_id: int,
    body: DeveloperActionReason,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> object:
    return _transition_alert(
        alert_id=alert_id,
        action="resolve",
        body=body,
        developer=developer,
        conn=conn,
    )


@router.get("/accounts")
def list_developer_accounts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str = Query(default="", max_length=100),
    status: Literal[1, 2] | None = None,
    role: Literal["platform_admin", "developer_admin"] | None = None,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        DeveloperAccessRepository(conn).list_accounts(
            page=page,
            page_size=page_size,
            keyword=keyword.strip(),
            status=status,
            role=role,
        )
    )


@router.get("/user-creation-requests")
def list_user_creation_requests(
    status: Literal["pending", "approved", "rejected"] | None = None,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AdminUserService(conn).list_creation_requests(status=status)
    )


@router.post("/user-creation-requests/{request_id}/{action}", response_model=None)
def review_user_creation_request(
    request_id: int,
    action: Literal["approve", "reject"],
    body: DeveloperActionReason,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> object:
    try:
        return ok(
            AdminUserService(conn).review_creation_request(
                developer,
                request_id,
                action=action,
                reason=body.reason,
            )
        )
    except AdminUserError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(exc.code, exc.message),
        )


@router.get("/customer-accounts")
def list_customer_accounts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    keyword: str = Query(default="", max_length=100),
    role: Literal["client_owner", "customer"] | None = None,
    status: Literal[1, 2] | None = None,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        DeveloperPlatformRepository(conn).list_customer_accounts(
            page=page,
            page_size=page_size,
            keyword=keyword.strip(),
            role=role,
            status=status,
        )
    )


@router.patch("/customer-accounts/{user_id}/status", response_model=None)
def update_customer_account_status(
    user_id: int,
    body: DeveloperAccountStatusUpdate,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> object:
    now = int(time.time())
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                select id, tenant_id, login_name, nickname, user_role, status
                from app_user
                where id = %s and user_role in ('client_owner', 'customer')
                for update
                """,
                (user_id,),
            )
            account = cursor.fetchone()
            if account is None:
                conn.rollback()
                return JSONResponse(
                    status_code=404,
                    content=fail("NOT_FOUND", "客户账号不存在"),
                )
            if (
                account["user_role"] == "client_owner"
                and body.status == 2
                and int(account["status"]) == 1
            ):
                cursor.execute(
                    """
                    select count(*) as total
                    from app_user
                    where tenant_id = %s
                      and user_role = 'client_owner'
                      and status = 1
                    """,
                    (int(account["tenant_id"]),),
                )
                if int(cursor.fetchone()["total"] or 0) <= 1:
                    conn.rollback()
                    return JSONResponse(
                        status_code=409,
                        content=fail(
                            "LAST_TENANT_OWNER",
                            "不能停用租户最后一个启用中的管理员",
                        ),
                    )
            cursor.execute(
                """
                update app_user
                set status = %s, auth_version = auth_version + 1,
                    update_time = %s
                where id = %s
                """,
                (body.status, now, user_id),
            )
            AdminAuditRepository(conn).create(
                tenant_id=int(account["tenant_id"]),
                admin_user_id=int(developer["id"]),
                action="developer.customer_account.status_update",
                target_type="app_user",
                target_id=user_id,
                detail={
                    "login_name": account["login_name"],
                    "status": body.status,
                    "reason": body.reason.strip(),
                },
                commit=False,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    result = DeveloperPlatformRepository(conn).list_customer_accounts(
        page=1,
        page_size=1,
        keyword=str(account["login_name"]),
        role=account["user_role"],
        status=None,
    )
    updated = next(
        item for item in result["items"] if int(item["id"]) == user_id
    )
    return ok(updated)


def _access_error(exc: DeveloperAccessError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(exc.code, exc.message),
    )


@router.post("/accounts", response_model=None)
def create_developer_account(
    body: DeveloperAccountCreate,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> object:
    try:
        return ok(DeveloperAccessService(conn).create_account(developer, body))
    except DeveloperAccessError as exc:
        return _access_error(exc)


@router.put("/accounts/{user_id}/password", response_model=None)
def reset_developer_password(
    user_id: int,
    body: DeveloperAccountPasswordReset,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> object:
    try:
        return ok(DeveloperAccessService(conn).reset_password(developer, user_id, body))
    except DeveloperAccessError as exc:
        return _access_error(exc)


@router.patch("/accounts/{user_id}/status", response_model=None)
def update_developer_status(
    user_id: int,
    body: DeveloperAccountStatusUpdate,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> object:
    try:
        return ok(DeveloperAccessService(conn).update_status(developer, user_id, body))
    except DeveloperAccessError as exc:
        return _access_error(exc)


@router.get("/audit-logs")
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None, max_length=100),
    target_type: str | None = Query(default=None, max_length=100),
    operator_id: int | None = Query(default=None, ge=1),
    tenant_id: int | None = Query(default=None, ge=0),
    keyword: str = Query(default="", max_length=100),
    start_time: int | None = Query(default=None, ge=0),
    end_time: int | None = Query(default=None, ge=0),
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AdminAuditRepository(conn).list_global(
            page=page,
            page_size=page_size,
            action=action,
            target_type=target_type,
            operator_id=operator_id,
            tenant_id=tenant_id,
            keyword=keyword.strip(),
            start_time=start_time,
            end_time=end_time,
        )
    )
