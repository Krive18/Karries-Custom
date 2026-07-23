import pytest

from app.core.secret_cipher import (
    SecretDecryptionError,
    decrypt_secret,
    encrypt_secret,
    validate_secret_encryption_configuration,
)


def test_secret_cipher_round_trip_does_not_store_plaintext(monkeypatch):
    monkeypatch.setenv("AI_SETTINGS_ENCRYPTION_KEY", "unit-test-encryption-key")

    encrypted = encrypt_secret("sk-private-value")

    assert encrypted.startswith("enc:v1:")
    assert "sk-private-value" not in encrypted
    assert decrypt_secret(encrypted) == "sk-private-value"


def test_secret_cipher_rejects_wrong_key(monkeypatch):
    monkeypatch.setenv("AI_SETTINGS_ENCRYPTION_KEY", "first-key")
    encrypted = encrypt_secret("sk-private-value")
    monkeypatch.setenv("AI_SETTINGS_ENCRYPTION_KEY", "second-key")

    with pytest.raises(SecretDecryptionError):
        decrypt_secret(encrypted)


def test_production_requires_secret_encryption_key(monkeypatch):
    monkeypatch.setenv("XHS_ENV", "production")
    monkeypatch.delenv("AI_SETTINGS_ENCRYPTION_KEY", raising=False)

    with pytest.raises(ValueError, match="AI_SETTINGS_ENCRYPTION_KEY"):
        validate_secret_encryption_configuration()
