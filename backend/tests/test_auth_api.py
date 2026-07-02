from app.repositories.user_repository import UserRepository


def test_register_with_invite_code_creates_user_and_wallet(mysql_conn, mysql_app_client):
    users = UserRepository(mysql_conn)
    users.create_invite_code("INV-A", initial_credits=66, max_uses=1, expires_time=0, remark="客户")

    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "operator_a",
            "nickname": "运营 A",
            "password": "matrix-secret",
            "invite_code": "INV-A",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["access_token"]
    assert payload["data"]["user"]["login_name"] == "operator_a"
    assert payload["data"]["wallet"]["balance"] == 66


def test_register_rejects_invalid_invite_code(mysql_app_client):
    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "operator_a",
            "nickname": "运营 A",
            "password": "matrix-secret",
            "invite_code": "BAD",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "AUTH_ERROR"


def test_login_and_me(mysql_conn, mysql_app_client):
    users = UserRepository(mysql_conn)
    users.create_invite_code("INV-A", initial_credits=0, max_uses=1, expires_time=0, remark="客户")

    register = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "operator_a",
            "nickname": "运营 A",
            "password": "matrix-secret",
            "invite_code": "INV-A",
        },
    )
    login = mysql_app_client.post(
        "/api/auth/login",
        json={"login_name": "operator_a", "password": "matrix-secret"},
    )
    token = login.json()["data"]["access_token"]
    me = mysql_app_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert register.status_code == 200
    assert login.status_code == 200
    assert me.status_code == 200
    assert me.json()["data"]["login_name"] == "operator_a"
