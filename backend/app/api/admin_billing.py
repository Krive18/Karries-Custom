from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from app.core.dependencies import get_db_connection, require_management_user
from app.core.responses import fail, ok
from app.repositories.admin_billing_repository import (
    AdminBillingConflictError,
    AdminBillingNotFoundError,
    AdminBillingRepository,
)
from app.repositories.wallet_repository import WalletRepository
from app.repositories.membership_upgrade_repository import (
    MembershipUpgradeConflictError,
    MembershipUpgradeNotFoundError,
    MembershipUpgradeRepository,
)
from app.schemas.admin_billing import (
    AdminMembershipActivate,
    AdminMembershipOrderCreate,
    AdminRechargeOrderCreate,
    AdminRechargeOrderReject,
)


router = APIRouter(prefix="/api/admin/billing", tags=["admin-billing"])


def _payment_proof_root(request: Request) -> Path:
    return Path(request.app.state.config.data_dir) / "payment_proofs"


@router.get("/overview")
def overview(
    days: int = Query(default=30, ge=7, le=90),
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AdminBillingRepository(conn).overview(
            int(manager["tenant_id"]),
            int(manager["id"]),
            days,
        )
    )


@router.get("/membership-plans")
def list_membership_plans(
    _manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(WalletRepository(conn).list_membership_plans())


@router.post("/membership/activate")
def activate_membership(
    payload: AdminMembershipActivate,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    del payload, manager, conn
    return JSONResponse(
        status_code=409,
        content=fail(
            "MEMBERSHIP_REVIEW_REQUIRED",
            "paid membership must be approved by a developer",
        ),
    )


@router.get("/membership-orders")
def list_membership_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: int | None = Query(default=None, ge=1, le=5),
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        MembershipUpgradeRepository(conn).list_manager_orders(
            int(manager["tenant_id"]),
            page=page,
            page_size=page_size,
            status=status,
        )
    )


@router.post("/membership-orders")
def create_membership_order(
    payload: AdminMembershipOrderCreate,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            MembershipUpgradeRepository(conn).create_order(
                manager,
                plan_id=payload.plan_id,
                duration_months=payload.duration_months,
                payment_channel=payload.payment_channel,
            )
        )
    except MembershipUpgradeNotFoundError as exc:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", str(exc)))
    except MembershipUpgradeConflictError as exc:
        return JSONResponse(status_code=409, content=fail("CONFLICT", str(exc)))


@router.post("/membership-orders/{order_id}/confirm")
def confirm_membership_order(
    order_id: int,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            MembershipUpgradeRepository(conn).confirm_payment(manager, order_id)
        )
    except MembershipUpgradeNotFoundError as exc:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", str(exc)))
    except MembershipUpgradeConflictError as exc:
        return JSONResponse(status_code=409, content=fail("CONFLICT", str(exc)))


@router.post("/membership-orders/{order_id}/cancel")
def cancel_membership_order(
    order_id: int,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            MembershipUpgradeRepository(conn).cancel_by_manager(manager, order_id)
        )
    except MembershipUpgradeNotFoundError as exc:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", str(exc)))
    except MembershipUpgradeConflictError as exc:
        return JSONResponse(status_code=409, content=fail("CONFLICT", str(exc)))


@router.get("/recharge-packages")
def list_recharge_packages(
    _manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(WalletRepository(conn).list_recharge_packages())


@router.get("/recharge-orders")
def list_recharge_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    employee_id: int | None = Query(default=None, ge=1),
    status: int | None = Query(default=None, ge=1, le=6),
    keyword: str = Query(default="", max_length=100),
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AdminBillingRepository(conn).list_recharge_orders(
            int(manager["tenant_id"]),
            page=page,
            page_size=page_size,
            employee_id=employee_id,
            status=status,
            keyword=keyword.strip(),
        )
    )


@router.post("/recharge-orders")
def create_recharge_order(
    payload: AdminRechargeOrderCreate,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(AdminBillingRepository(conn).create_recharge_order(manager, payload))
    except AdminBillingNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", str(exc)),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_RECHARGE", str(exc)),
        )


@router.post("/recharge-orders/{order_id}/confirm")
def confirm_recharge_order(
    order_id: int,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            AdminBillingRepository(conn).confirm_recharge_order(manager, order_id)
        )
    except AdminBillingNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", str(exc)),
        )
    except AdminBillingConflictError as exc:
        return JSONResponse(
            status_code=409,
            content=fail("INVALID_STATUS", str(exc)),
        )


@router.post("/recharge-orders/{order_id}/reject")
def reject_recharge_order(
    order_id: int,
    payload: AdminRechargeOrderReject,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(
            AdminBillingRepository(conn).reject_recharge_order(
                manager,
                order_id,
                payload.reason,
            )
        )
    except AdminBillingNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", str(exc)),
        )
    except AdminBillingConflictError as exc:
        return JSONResponse(
            status_code=409,
            content=fail("INVALID_STATUS", str(exc)),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_REJECTION", str(exc)),
        )


@router.get("/recharge-orders/{order_id}/payment-proof")
def get_recharge_payment_proof(
    order_id: int,
    request: Request,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
):
    proof = AdminBillingRepository(conn).get_recharge_payment_proof(
        int(manager["tenant_id"]),
        order_id,
    )
    if proof is None:
        return JSONResponse(
            status_code=404,
            content=fail("PAYMENT_PROOF_NOT_FOUND", "payment proof not found"),
        )
    root = _payment_proof_root(request).resolve()
    path = (root / proof["proof_file_path"]).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return JSONResponse(
            status_code=404,
            content=fail("PAYMENT_PROOF_NOT_FOUND", "payment proof not found"),
        )
    if not path.is_file():
        return JSONResponse(
            status_code=404,
            content=fail("PAYMENT_PROOF_NOT_FOUND", "payment proof not found"),
        )
    return FileResponse(
        path,
        media_type=proof["proof_mime_type"] or "application/octet-stream",
        filename=proof["proof_file_name"] or "payment-proof",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/ledger")
def list_credit_ledger(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    employee_id: int | None = Query(default=None, ge=1),
    business_type: str = Query(default="", max_length=50),
    direction: Literal["", "income", "expense"] = Query(default=""),
    start_time: int | None = Query(default=None, ge=0),
    end_time: int | None = Query(default=None, ge=0),
    keyword: str = Query(default="", max_length=100),
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AdminBillingRepository(conn).list_ledger(
            int(manager["tenant_id"]),
            page=page,
            page_size=page_size,
            employee_id=employee_id,
            business_type=business_type.strip(),
            direction=direction,
            start_time=start_time,
            end_time=end_time,
            keyword=keyword.strip(),
        )
    )
