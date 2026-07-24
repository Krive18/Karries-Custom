import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


ENCRYPTED_SECRET_PREFIX = "enc:v1:"
_DEVELOPMENT_SECRET = "dev-insecure-ai-settings-key"
_NON_PRODUCTION_ENVIRONMENTS = {"development", "dev", "local", "test"}


class SecretDecryptionError(ValueError):
    pass


def validate_secret_encryption_configuration() -> None:
    environment = _environment()
    if (
        environment not in _NON_PRODUCTION_ENVIRONMENTS
        and not os.environ.get("AI_SETTINGS_ENCRYPTION_KEY", "").strip()
    ):
        raise ValueError(
            "AI_SETTINGS_ENCRYPTION_KEY must be set outside development and test"
        )


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    token = _cipher().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{ENCRYPTED_SECRET_PREFIX}{token}"


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    if not value.startswith(ENCRYPTED_SECRET_PREFIX):
        raise SecretDecryptionError("plaintext AI key is not allowed")
    token = value.removeprefix(ENCRYPTED_SECRET_PREFIX)
    try:
        return _cipher().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise SecretDecryptionError("encrypted AI key cannot be decrypted") from exc


def _cipher() -> Fernet:
    material = os.environ.get("AI_SETTINGS_ENCRYPTION_KEY", "").strip()
    if not material:
        material = _DEVELOPMENT_SECRET
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _environment() -> str:
    return os.environ.get("XHS_ENV", os.environ.get("APP_ENV", "development")).lower()
