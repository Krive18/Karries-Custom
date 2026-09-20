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


def test_ai_settings_api_uses_current_doubao_multimodal_defaults(
    mysql_conn, mysql_app_client
):
    headers = _auth_headers(mysql_conn, mysql_app_client, "defaults", "developer_admin")

    response = mysql_app_client.get("/api/settings/ai", headers=headers)

    assert response.status_code == 200
    vision = response.json()["data"]["vision"]
    assert vision["provider"] == "doubao"
    assert vision["base_url"] == (
        "https://ark.cn-beijing.volces.com/api/v3/responses"
    )
    assert vision["model"] == "doubao-seed-2-0-lite-260428"
    pro_copywriting = response.json()["data"]["pro_copywriting"]
    assert pro_copywriting["provider"] == "doubao"
    assert pro_copywriting["base_url"] == (
        "https://ark.cn-beijing.volces.com/api/v3/responses"
    )
    assert pro_copywriting["model"] == "doubao-seed-2-1-pro-260628"


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


def test_ai_settings_api_tests_stored_provider_key(
    monkeypatch, mysql_conn, mysql_app_client
):
    from app.api import settings as settings_api

    headers = _auth_headers(mysql_conn, mysql_app_client, "test-provider", "developer_admin")
    observed = {}

    def fake_test(repo, slot):
        observed["slot"] = slot
        return {
            "success": True,
            "slot": slot,
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "request_id": "req-provider-test",
            "latency_ms": 321,
        }

    monkeypatch.setattr(
        settings_api,
        "test_ai_setting_connection",
        fake_test,
        raising=False,
    )

    response = mysql_app_client.post(
        "/api/settings/ai/copywriting/test",
        headers=headers,
    )

    assert response.status_code == 200
    assert observed == {"slot": "copywriting"}
    assert response.json()["data"] == {
        "success": True,
        "slot": "copywriting",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "request_id": "req-provider-test",
        "latency_ms": 321,
    }
    assert "api_key" not in response.text


def test_ai_settings_api_rejects_test_without_stored_key(
    mysql_conn, mysql_app_client
):
    headers = _auth_headers(mysql_conn, mysql_app_client, "test-no-key", "platform_admin")

    response = mysql_app_client.post(
        "/api/settings/ai/vision/test",
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "AI_KEY_MISSING"


def test_ai_settings_api_rejects_oversized_provider_key(
    mysql_conn, mysql_app_client
):
    headers = _auth_headers(
        mysql_conn,
        mysql_app_client,
        "test-oversized-key",
        "developer_admin",
    )

    response = mysql_app_client.put(
        "/api/settings/ai/copywriting",
        headers=headers,
        json={
            "api_key": "x" * 513,
            "model": "deepseek-v4-flash",
            "enabled": True,
        },
    )

    assert response.status_code == 422
