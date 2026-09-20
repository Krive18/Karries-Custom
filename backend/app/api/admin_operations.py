from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_management_user
from app.core.responses import fail, ok
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.admin_operations_repository import AdminOperationsRepository
from app.repositories.matrix_plan_repository import MatrixPlanRepository


router = APIRouter(prefix="/api/admin/operations", tags=["admin-operations"])


@router.get("/overview")
def overview(
    days: int = Query(default=7, ge=7, le=30),
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AdminOperationsRepository(conn).overview(int(manager["tenant_id"]), days)
    )


@router.get("/xhs-accounts")
def list_xhs_accounts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    employee_id: int | None = Query(default=None, ge=1),
    status: int | None = Query(default=None, ge=1, le=4),
    keyword: str = Query(default="", max_length=100),
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AdminOperationsRepository(conn).list_accounts(
            int(manager["tenant_id"]),
            page=page,
            page_size=page_size,
            employee_id=employee_id,
            status=status,
            keyword=keyword.strip(),
        )
    )


@router.get("/publish-plans")
def list_publish_plans(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    employee_id: int | None = Query(default=None, ge=1),
    status: int | None = Query(default=None, ge=1, le=7),
    keyword: str = Query(default="", max_length=100),
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AdminOperationsRepository(conn).list_plans(
            int(manager["tenant_id"]),
            page=page,
            page_size=page_size,
            employee_id=employee_id,
            status=status,
            keyword=keyword.strip(),
        )
    )


@router.get("/publish-plans/{plan_id}")
def get_publish_plan(
    plan_id: int,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    plan = AdminOperationsRepository(conn).get_plan(int(manager["tenant_id"]), plan_id)
    if plan is None:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", "发布计划不存在"))
    return ok(plan)


@router.post("/publish-plans/{plan_id}/cancel")
def cancel_publish_plan(
    plan_id: int,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = AdminOperationsRepository(conn)
    user_id = repository.get_plan_owner(int(manager["tenant_id"]), plan_id)
    if user_id is None:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", "发布计划不存在"))
    result = MatrixPlanRepository(conn).cancel_plan(user_id, plan_id)
    if result is None:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", "发布计划不存在"))
    if "error" in result:
        return JSONResponse(status_code=409, content=fail("INVALID_STATUS", str(result["error"])))
    AdminAuditRepository(conn).create(
        tenant_id=int(manager["tenant_id"]),
        admin_user_id=int(manager["id"]),
        action="publish_plan.cancel",
        target_type="matrix_publish_plan",
        target_id=plan_id,
        detail={"employee_user_id": user_id},
    )
    return ok(result)


@router.post("/publish-plans/{plan_id}/retry")
def retry_publish_plan(
    plan_id: int,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = AdminOperationsRepository(conn)
    user_id = repository.get_plan_owner(int(manager["tenant_id"]), plan_id)
    if user_id is None:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", "发布计划不存在"))
    result = MatrixPlanRepository(conn).retry_failed_items(user_id, plan_id)
    if result is None:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", "发布计划不存在"))
    if "error" in result:
        return JSONResponse(status_code=409, content=fail("INVALID_STATUS", str(result["error"])))
    AdminAuditRepository(conn).create(
        tenant_id=int(manager["tenant_id"]),
        admin_user_id=int(manager["id"]),
        action="publish_plan.retry",
        target_type="matrix_publish_plan",
        target_id=plan_id,
        detail={"employee_user_id": user_id},
    )
    return ok(result)
