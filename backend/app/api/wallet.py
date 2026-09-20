import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.core.dependencies import get_db_connection, require_customer_user
from app.core.responses import fail, ok
from app.repositories.wallet_repository import (
    RechargeOrderConflictError,
    RechargeOrderNotFoundError,
    WalletRepository,
)
from app.schemas.wallet import RechargeOrderCreate
from app.services.upload_storage_service import UploadStorageError, UploadStorageService


router = APIRouter(prefix="/api/wallet", tags=["wallet"])
logger = logging.getLogger(__name__)


def _payment_proof_root(request: Request) -> Path:
    return Path(request.app.state.config.data_dir) / "payment_proofs"


@router.get("")
def get_wallet(
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = WalletRepository(conn)
    repository.get_current_membership(user["tenant_id"], user["id"])
    wallet = repository.get_wallet(user["id"])
    return ok(wallet)


@router.get("/ledger")
def list_ledger(
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = WalletRepository(conn)
    repository.get_current_membership(user["tenant_id"], user["id"])
    ledger = repository.list_ledger(user["id"])
    return ok(ledger)


@router.get("/membership-plans")
def list_membership_plans(
    _user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(WalletRepository(conn).list_membership_plans())


@router.get("/membership")
def get_current_membership(
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    membership = WalletRepository(conn).get_current_membership(
        user["tenant_id"],
        user["id"],
    )
    return ok(membership)


@router.get("/check-in")
def get_checkin_status(
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        WalletRepository(conn).get_checkin_status(
            user["tenant_id"],
            user["id"],
        )
    )


@router.post("/check-in")
def check_in(
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        WalletRepository(conn).check_in(
            user["tenant_id"],
            user["id"],
        )
    )


@router.get("/recharge-packages")
def list_recharge_packages(
    _user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(WalletRepository(conn).list_recharge_packages())


@router.get("/recharge-orders")
def list_recharge_orders(
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(WalletRepository(conn).list_recharge_orders(user["id"]))


@router.post("/recharge-orders")
def create_recharge_order(
    payload: RechargeOrderCreate,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    try:
        order = WalletRepository(conn).create_recharge_order(
            user["tenant_id"],
            user["id"],
            payload,
        )
        return ok(order)
    except ValueError as error:
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_RECHARGE_REQUEST", str(error)),
        )


@router.post("/recharge-orders/{order_id}/payment-proof")
def submit_recharge_payment_proof(
    order_id: int,
    request: Request,
    payer_note: str = Form(..., min_length=1, max_length=100),
    proof: UploadFile = File(...),
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    payer_note = payer_note.strip()
    if not payer_note:
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_PAYMENT_PROOF", "payer note is required"),
        )
    storage = UploadStorageService(
        _payment_proof_root(request),
        max_bytes=10 * 1024 * 1024,
    )
    stored = None
    try:
        stored = storage.save(
            proof.file,
            proof.filename or "payment-proof",
            proof.content_type or "",
            int(user["tenant_id"]),
            order_id,
        )
        if stored.file_type != "image":
            raise UploadStorageError("payment proof must be an image")
        order, previous_storage_path = WalletRepository(
            conn
        ).submit_recharge_payment_proof(
            int(user["tenant_id"]),
            int(user["id"]),
            order_id,
            payer_note,
            stored,
        )
        if previous_storage_path and previous_storage_path != stored.storage_path:
            try:
                storage.delete(previous_storage_path)
            except (OSError, UploadStorageError):
                logger.warning(
                    "failed to remove replaced payment proof: %s",
                    previous_storage_path,
                    exc_info=True,
                )
        return ok(order)
    except RechargeOrderNotFoundError as error:
        if stored is not None:
            storage.delete(stored.storage_path)
        return JSONResponse(
            status_code=404,
            content=fail("RECHARGE_ORDER_NOT_FOUND", str(error)),
        )
    except RechargeOrderConflictError as error:
        if stored is not None:
            storage.delete(stored.storage_path)
        return JSONResponse(
            status_code=409,
            content=fail("INVALID_RECHARGE_STATUS", str(error)),
        )
    except UploadStorageError as error:
        if stored is not None:
            storage.delete(stored.storage_path)
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_PAYMENT_PROOF", str(error)),
        )
    finally:
        proof.file.close()


@router.get("/recharge-orders/{order_id}/payment-proof")
def get_recharge_payment_proof(
    order_id: int,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    proof = WalletRepository(conn).get_recharge_payment_proof(
        int(user["tenant_id"]),
        int(user["id"]),
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
