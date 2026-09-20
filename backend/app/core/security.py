import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any


class InvalidTokenError(ValueError):
    """Raised when an access token cannot be trusted."""


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return "pbkdf2_sha256$260000$" + _b64(salt) + "$" + _b64(digest)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, rounds, salt_text, digest_text = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = _unb64(salt_text)
        expected = _unb64(digest_text)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(rounds),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(
    payload: dict[str, Any],
    secret: str,
    expires_in_seconds: int,
    now: int | None = None,
) -> str:
    issued_at = int(time.time() if now is None else now)
    body = {**payload, "iat": issued_at, "exp": issued_at + expires_in_seconds}
    body_text = _b64(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = _sign(body_text, secret)
    return f"{body_text}.{signature}"


def verify_access_token(
    token: str,
    secret: str,
    now: int | None = None,
    expected_audience: str | None = None,
) -> dict[str, Any]:
    try:
        body_text, signature = token.split(".", 1)
    except ValueError as exc:
        raise InvalidTokenError("invalid token format") from exc

    if not hmac.compare_digest(_sign(body_text, secret), signature):
        raise InvalidTokenError("invalid token signature")

    payload = json.loads(_unb64(body_text).decode("utf-8"))
    current = int(time.time() if now is None else now)
    if int(payload.get("exp", 0)) <= current:
        raise InvalidTokenError("token expired")
    if expected_audience is not None and payload.get("aud") != expected_audience:
        raise InvalidTokenError("invalid token audience")
    return payload


def _sign(body_text: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body_text.encode("ascii"), hashlib.sha256).digest()
    return _b64(digest)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
