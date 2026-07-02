from fastapi import Header, HTTPException, Request

from app.core.security import InvalidTokenError, verify_access_token
from app.repositories.user_repository import UserRepository


def get_current_user(request: Request, authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing bearer token")

    try:
        payload = verify_access_token(token, request.app.state.config.auth.token_secret)
        user_id = int(payload["user_id"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc

    user = UserRepository(request.app.state.conn).get_by_id(user_id)
    if user is None or user["status"] != 1:
        raise HTTPException(status_code=401, detail="invalid user")
    return user


current_user = get_current_user
