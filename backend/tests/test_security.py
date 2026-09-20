import pytest

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    hash_password,
    verify_access_token,
    verify_password,
)


def test_password_hash_verifies_original_password():
    password_hash = hash_password("matrix-secret")

    assert password_hash != "matrix-secret"
    assert verify_password("matrix-secret", password_hash) is True
    assert verify_password("wrong-secret", password_hash) is False


def test_access_token_round_trip():
    token = create_access_token(
        {"user_id": 12, "role": "customer"},
        secret="unit-secret",
        expires_in_seconds=60,
        now=1_800_000_000,
    )

    payload = verify_access_token(
        token,
        secret="unit-secret",
        now=1_800_000_030,
    )

    assert payload["user_id"] == 12
    assert payload["role"] == "customer"


def test_access_token_accepts_positional_secret_and_expiration():
    token = create_access_token(
        {"user_id": 13},
        "unit-secret",
        60,
        now=1_800_000_000,
    )

    payload = verify_access_token(
        token,
        "unit-secret",
        now=1_800_000_030,
    )

    assert payload["user_id"] == 13


def test_access_token_rejects_tampering():
    token = create_access_token(
        {"user_id": 12},
        secret="unit-secret",
        expires_in_seconds=60,
        now=1_800_000_000,
    )

    with pytest.raises(InvalidTokenError, match="invalid token signature"):
        verify_access_token(token + "x", secret="unit-secret", now=1_800_000_001)


def test_access_token_rejects_expired_token():
    token = create_access_token(
        {"user_id": 12},
        secret="unit-secret",
        expires_in_seconds=10,
        now=1_800_000_000,
    )

    with pytest.raises(InvalidTokenError, match="token expired"):
        verify_access_token(token, secret="unit-secret", now=1_800_000_011)


def test_access_token_rejects_token_at_expiration_boundary():
    token = create_access_token(
        {"user_id": 12},
        secret="unit-secret",
        expires_in_seconds=10,
        now=1_800_000_000,
    )

    with pytest.raises(InvalidTokenError, match="token expired"):
        verify_access_token(token, secret="unit-secret", now=1_800_000_010)


def test_access_token_can_require_expected_audience():
    token = create_access_token(
        {"user_id": 12, "aud": "customer"},
        secret="unit-secret",
        expires_in_seconds=60,
        now=1_800_000_000,
    )

    payload = verify_access_token(
        token,
        secret="unit-secret",
        now=1_800_000_030,
        expected_audience="customer",
    )

    assert payload["aud"] == "customer"


def test_access_token_rejects_wrong_audience():
    token = create_access_token(
        {"user_id": 12, "aud": "customer"},
        secret="unit-secret",
        expires_in_seconds=60,
        now=1_800_000_000,
    )

    with pytest.raises(InvalidTokenError, match="invalid token audience"):
        verify_access_token(
            token,
            secret="unit-secret",
            now=1_800_000_030,
            expected_audience="manager",
        )
