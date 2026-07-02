from fastapi import Header, HTTPException, Request

from app.core.security import InvalidTokenError, verify_access_token
from app.repositories.user_repository import UserRepository


def current_user(request: Request, authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = verify_access_token(token, request.app.state.config.auth.token_secret)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user = UserRepository(request.app.state.conn).get_by_id(int(payload["user_id"]))
    if user is None or user["status"] != 1:
        raise HTTPException(status_code=401, detail="invalid user")
    return user
