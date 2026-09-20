from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_developer_user
from app.core.responses import fail, ok
from app.repositories.developer_billing_repository import (
    DeveloperBillingConflictError,
    DeveloperBillingNotFoundError,
    DeveloperBillingRepository,
)
from app.repositories.membership_upgrade_repository import (
    MembershipUpgradeConflictError,
    MembershipUpgradeNotFoundError,
    MembershipUpgradeRepository,
)
from app.schemas.developer_billing import (
    DeveloperCreditAdjustment,
    DeveloperCreditGrant,
    DeveloperMembershipOrderReject,
    DeveloperTenantMembershipUpdate,
)


router = APIRouter(
    prefix="/api/developer/billing",
    tags=["developer-billing"],
    include_in_schema=False,
)


@router.get("/membership-orders")
def list_membership_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: int | None = Query(default=2, ge=1, le=5),
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        MembershipUpgradeRepository(conn).list_developer_orders(
            page=page,
            page_size=page_size,
            status=status,
        )
    )


@router.post("/membership-orders/{order_id}/approve")
def approve_membership_order(
    order_id: int,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(MembershipUpgradeRepository(conn).approve(developer, order_id))
    except MembershipUpgradeNotFoundError as exc:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", str(exc)))
    except MembershipUpgradeConflictError as exc:
        return JSONResponse(status_code=409, content=fail("CONFLICT", str(exc)))


@router.post("/membership-orders/{order_id}/reject")
def reject_membership_order(
    order_id: int,
    payload: DeveloperMembershipOrderReject,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            MembershipUpgradeRepository(conn).reject(
                developer,
                order_id,
                payload.reason,
            )
        )
    except MembershipUpgradeNotFoundError as exc:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", str(exc)))
    except MembershipUpgradeConflictError as exc:
        return JSONResponse(status_code=409, content=fail("CONFLICT", str(exc)))


@router.get("/customers")
def list_customers(
    keyword: str = Query(default="", max_length=100),
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(DeveloperBillingRepository(conn).list_customers(keyword.strip()))


@router.get("/tenants/{tenant_id}/membership")
def get_tenant_membership(
    tenant_id: int,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(DeveloperBillingRepository(conn).get_tenant_membership(tenant_id))
    except DeveloperBillingNotFoundError as exc:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", str(exc)))


@router.post("/tenants/{tenant_id}/membership")
def adjust_tenant_membership(
    tenant_id: int,
    payload: DeveloperTenantMembershipUpdate,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            DeveloperBillingRepository(conn).adjust_tenant_membership(
                developer,
                tenant_id,
                plan_id=payload.plan_id,
                duration_months=payload.duration_months,
            )
        )
    except DeveloperBillingNotFoundError as exc:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", str(exc)))
    except DeveloperBillingConflictError as exc:
        return JSONResponse(status_code=400, content=fail("INVALID_PLAN", str(exc)))


@router.get("/recharge-orders")
def list_recharge_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: int | None = Query(default=6, ge=1, le=6),
    keyword: str = Query(default="", max_length=100),
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        DeveloperBillingRepository(conn).list_recharge_orders(
            page=page,
            page_size=page_size,
            status=status,
            keyword=keyword.strip(),
        )
    )


@router.post("/recharge-orders/{order_id}/grant")
def grant_recharge_order(
    order_id: int,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        result = DeveloperBillingRepository(conn).grant_recharge_order(
            developer, order_id
        )
    except DeveloperBillingNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", str(exc)),
        )
    except DeveloperBillingConflictError as exc:
        return JSONResponse(
            status_code=409,
            content=fail("CONFLICT", str(exc)),
        )
    return ok(result)


@router.post("/credits/grant")
def grant_credits(
    payload: DeveloperCreditGrant,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        result = DeveloperBillingRepository(conn).grant_credits(
            developer,
            user_id=payload.user_id,
            credits=payload.credits,
            reason=payload.reason,
        )
    except DeveloperBillingNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", str(exc)),
        )
    return ok(result)


@router.post("/credits/adjust")
def adjust_credits(
    payload: DeveloperCreditAdjustment,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    if payload.change_amount == 0:
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_ADJUSTMENT", "算力调整值不能为 0"),
        )
    try:
        result = DeveloperBillingRepository(conn).adjust_credits(
            developer,
            user_id=payload.user_id,
            change_amount=payload.change_amount,
            reason=payload.reason,
        )
    except DeveloperBillingNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", str(exc)),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=409,
            content=fail("INVALID_BALANCE", str(exc)),
        )
    return ok(result)


@router.get("/ledger")
def list_ledger(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    user_id: int | None = Query(default=None, ge=1),
    keyword: str = Query(default="", max_length=100),
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        DeveloperBillingRepository(conn).list_ledger(
            page=page,
            page_size=page_size,
            user_id=user_id,
            keyword=keyword.strip(),
        )
    )


@router.get("/payment-records")
def list_payment_records(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        DeveloperBillingRepository(conn).list_payment_records(
            page=page,
            page_size=page_size,
        )
    )
