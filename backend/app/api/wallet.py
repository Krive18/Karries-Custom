from fastapi import APIRouter, Depends

from app.core.dependencies import current_user, get_db_connection
from app.core.responses import ok
from app.repositories.wallet_repository import WalletRepository


router = APIRouter(prefix="/api/wallet", tags=["wallet"])


@router.get("")
def get_wallet(
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    wallet = WalletRepository(conn).get_wallet(user["id"])
    return ok(wallet)


@router.get("/ledger")
def list_ledger(
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    ledger = WalletRepository(conn).list_ledger(user["id"])
    return ok(ledger)
