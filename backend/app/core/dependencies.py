import hmac
from collections.abc import Generator
from typing import Any

from fastapi import Depends, Header, HTTPException, Request

from app.core.security import InvalidTokenError, verify_access_token
from app.repositories.user_repository import UserRepository


def get_db_connection(request: Request) -> Generator[Any, None, None]:
    conn = request.app.state.connect_db()
    request.state.db_conn = conn
    try:
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        request.state.db_conn = None
        conn.close()


def get_current_user(
    request: Request,
    authorization: str = Header(default=""),
    conn=Depends(get_db_connection),
) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing bearer token")

    try:
        surface = request.app.state.api_surface
        expected_audience = None if surface == "all" else surface
        payload = verify_access_token(
            token,
            request.app.state.config.auth.token_secret,
            expected_audience=expected_audience,
        )
        user_id = int(payload["user_id"])
        auth_version = int(payload.get("auth_version", 1))
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc

    user = UserRepository(conn).get_by_id(user_id)
    if user is None or user["status"] != 1:
        raise HTTPException(status_code=401, detail="invalid user")
    if int(user.get("auth_version", 1)) != auth_version:
        raise HTTPException(status_code=401, detail="expired login session")
    return user


def verify_worker_token(
    request: Request,
    x_worker_token: str = Header(default="", alias="X-Worker-Token"),
) -> None:
    configured_token = request.app.state.config.worker_api_token
    if not configured_token:
        raise HTTPException(status_code=503, detail="worker api token is not configured")
    if not x_worker_token or not hmac.compare_digest(x_worker_token, configured_token):
        raise HTTPException(status_code=401, detail="invalid worker token")


current_user = get_current_user


MANAGEMENT_ROLES = {"client_owner"}
DEVELOPER_ROLES = {"platform_admin", "developer_admin"}


def require_customer_user(user: dict = Depends(current_user)) -> dict:
    if user["user_role"] != "customer":
        raise HTTPException(status_code=403, detail="customer role required")
    return user


def require_management_user(user: dict = Depends(current_user)) -> dict:
    if user["user_role"] not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="management role required")
    return user


def require_developer_user(user: dict = Depends(current_user)) -> dict:
    if user["user_role"] not in DEVELOPER_ROLES:
        raise HTTPException(status_code=403, detail="developer role required")
    return user
