from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.responses import ok
from app.repositories.account_repository import AccountRepository


router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountCreateRequest(BaseModel):
    account_name: str
    cookie_path: str


def account_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "account_name": row["account_name"],
        "platform": row["platform"],
        "cookie_path": row["cookie_path"],
        "status": row["status"],
        "last_checked_time": row["last_checked_time"],
        "create_time": row["create_time"],
        "update_time": row["update_time"],
    }


@router.post("")
def create_account(request: Request, payload: AccountCreateRequest) -> dict:
    repo = AccountRepository(request.app.state.conn)
    account_id = repo.create(payload.account_name, payload.cookie_path)
    row = repo.get(account_id)
    return ok(account_to_dict(row))


@router.get("")
def list_accounts(request: Request) -> dict:
    repo = AccountRepository(request.app.state.conn)
    return ok([account_to_dict(row) for row in repo.list_all()])
