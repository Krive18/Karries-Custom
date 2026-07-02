from app.schemas.auth import RegisterRequest
from app.repositories.user_repository import UserRepository


def test_register_schema_accepts_optional_nickname_and_six_character_password():
    payload = RegisterRequest(
        login_name="operator_a",
        password="123456",
        invite_code="INV-A",
    )

    assert payload.nickname == ""


def test_register_with_invite_code_returns_token_user_and_wallet(mysql_app_client):
    users = UserRepository(mysql_app_client.app.state.conn)
    users.create_invite_code("INV-A", initial_credits=66, max_uses=1, expires_time=0, remark="customer")

    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "operator_a",
            "nickname": "operator A",
            "password": "matrix-secret",
            "invite_code": "INV-A",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert payload["data"]["access_token"]
    assert payload["data"]["token_type"] == "bearer"
    assert payload["data"]["expires_in"] > 0
    assert payload["data"]["user"]["login_name"] == "operator_a"
    assert payload["data"]["user"]["wallet_balance"] == 66
    assert "password" not in str(payload["data"]).lower()


def test_register_rejects_invalid_invite_code(mysql_app_client):
    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "operator_a",
            "nickname": "operator A",
            "password": "matrix-secret",
            "invite_code": "BAD",
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "INVALID_INVITE_CODE"


def test_login_returns_token_after_registration(mysql_app_client):
    users = UserRepository(mysql_app_client.app.state.conn)
    users.create_invite_code("INV-LOGIN", initial_credits=0, max_uses=1, expires_time=0, remark="customer")
    register = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "operator_login",
            "nickname": "operator Login",
            "password": "matrix-secret",
            "invite_code": "INV-LOGIN",
        },
    )

    response = mysql_app_client.post(
        "/api/auth/login",
        json={"login_name": "operator_login", "password": "matrix-secret"},
    )

    assert register.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["access_token"]
    assert payload["data"]["user"]["login_name"] == "operator_login"


def test_me_returns_current_user(mysql_app_client):
    users = UserRepository(mysql_app_client.app.state.conn)
    users.create_invite_code("INV-ME", initial_credits=12, max_uses=1, expires_time=0, remark="customer")
    register = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "operator_me",
            "nickname": "operator Me",
            "password": "matrix-secret",
            "invite_code": "INV-ME",
        },
    )
    token = register.json()["data"]["access_token"]

    response = mysql_app_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["login_name"] == "operator_me"
    assert payload["data"]["wallet_balance"] == 12


def test_me_requires_bearer_token(app_client_without_db):
    response = app_client_without_db.get("/api/auth/me")

    assert response.status_code == 401
