from app.core.security import create_access_token
from app.repositories.user_repository import UserRepository


def _auth_headers(mysql_conn, client, suffix: str, role: str) -> dict[str, str]:
    user_id = UserRepository(mysql_conn).create_user(
        login_name=f"settings_{role}_{suffix}",
        nickname=f"Settings {role}",
        password_hash="not-used-by-token-auth",
        user_role=role,
        invite_code="",
        tenant_id=1,
    )
    token = create_access_token(
        {"user_id": user_id, "tenant_id": 1, "role": role},
        client.app.state.config.auth.token_secret,
        client.app.state.config.auth.access_token_seconds,
    )
    return {"Authorization": f"Bearer {token}"}


def test_ai_settings_api_requires_authentication(mysql_app_client):
    response = mysql_app_client.get("/api/settings/ai")

    assert response.status_code == 401


def test_ai_settings_api_requires_developer_role(mysql_conn, mysql_app_client):
    headers = _auth_headers(mysql_conn, mysql_app_client, "member", "client_member")

    response = mysql_app_client.get("/api/settings/ai", headers=headers)

    assert response.status_code == 403


def test_ai_settings_api_saves_encrypted_key_and_masks_it(
    monkeypatch, mysql_conn, mysql_app_client
):
    monkeypatch.setenv("AI_SETTINGS_ENCRYPTION_KEY", "settings-test-encryption-key")
    headers = _auth_headers(mysql_conn, mysql_app_client, "developer", "developer_admin")

    response = mysql_app_client.put(
        "/api/settings/ai/copywriting",
        headers=headers,
        json={
            "api_key": "sk-copy-secret",
            "model": "deepseek-chat",
            "enabled": True,
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["copywriting"]["provider"] == "deepseek"
    assert body["copywriting"]["base_url"] == (
        "https://api.deepseek.com/chat/completions"
    )
    assert body["copywriting"]["has_key"] is True
    assert body["copywriting"]["masked_key"] == "sk-c********cret"
    assert "sk-copy-secret" not in response.text

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select setting_value
            from app_setting
            where setting_key = %s
            """,
            ("ai.copywriting.api_key",),
        )
        stored = cursor.fetchone()["setting_value"]
    assert stored.startswith("enc:v1:")
    assert "sk-copy-secret" not in stored


def test_ai_settings_api_rejects_client_controlled_endpoint(
    mysql_conn, mysql_app_client
):
    headers = _auth_headers(mysql_conn, mysql_app_client, "endpoint", "developer_admin")

    response = mysql_app_client.put(
        "/api/settings/ai/copywriting",
        headers=headers,
        json={
            "api_key": "sk-copy-secret",
            "base_url": "http://127.0.0.1:9999/steal",
            "model": "deepseek-chat",
            "enabled": True,
        },
    )

    assert response.status_code == 422


def test_ai_settings_api_rejects_unknown_slot(mysql_conn, mysql_app_client):
    headers = _auth_headers(mysql_conn, mysql_app_client, "slot", "developer_admin")

    response = mysql_app_client.put(
        "/api/settings/ai/not-real",
        headers=headers,
        json={
            "api_key": "sk",
            "model": "deepseek-chat",
            "enabled": True,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_ai_settings_api_clears_key_only(
    monkeypatch, mysql_conn, mysql_app_client
):
    monkeypatch.setenv("AI_SETTINGS_ENCRYPTION_KEY", "settings-test-encryption-key")
    headers = _auth_headers(mysql_conn, mysql_app_client, "clear", "platform_admin")
    mysql_app_client.put(
        "/api/settings/ai/copywriting",
        headers=headers,
        json={
            "api_key": "sk-copy-secret",
            "model": "deepseek-chat",
            "enabled": True,
        },
    )

    response = mysql_app_client.delete(
        "/api/settings/ai/copywriting/key", headers=headers
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["copywriting"]["provider"] == "deepseek"
    assert body["copywriting"]["has_key"] is False
