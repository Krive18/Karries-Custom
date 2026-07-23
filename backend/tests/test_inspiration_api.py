from app.core.security import create_access_token
from app.repositories.user_repository import UserRepository


def auth_headers(mysql_conn, mysql_app_client, suffix: str, tenant_id: int = 1) -> dict[str, str]:
    invite_code = f"INV-INSP-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=0,
        max_uses=1,
        expires_time=0,
        remark="inspiration-api",
        tenant_id=tenant_id,
    )
    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": f"inspiration_user_{suffix}",
            "nickname": f"Inspiration User {suffix}",
            "password": "inspiration-secret",
            "invite_code": invite_code,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def management_headers(mysql_conn, suffix: str, tenant_id: int) -> dict[str, str]:
    user_id = UserRepository(mysql_conn).create_user(
        login_name=f"inspiration_admin_{suffix}",
        nickname="Inspiration Admin",
        password_hash="not-used-by-token-auth",
        user_role="client_admin",
        invite_code="",
        tenant_id=tenant_id,
    )
    token = create_access_token(
        {"user_id": user_id, "role": "client_admin"},
        "dev-secret",
    )
    return {"Authorization": f"Bearer {token}"}


def create_session(mysql_app_client, headers: dict[str, str]) -> int:
    response = mysql_app_client.post(
        "/api/inspiration/sessions",
        headers=headers,
        json={
            "title": "New product inspiration",
            "linked_product_id": 0,
            "linked_xhs_account_id": 0,
            "goal_type": "topic",
            "tone": "natural and sincere",
            "extra_requirement": "",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def configure_ai(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-inspiration-test")

    def fake_transport(_url, _headers, _payload, _timeout):
        return {
            "choices": [
                {
                    "message": {
                        "content": "Five topic ideas for a friendly product post"
                    }
                }
            ]
        }

    monkeypatch.setattr("app.integrations.deepseek._post_json", fake_transport)


def test_inspiration_sessions_require_auth(app_client_without_db):
    response = app_client_without_db.post("/api/inspiration/sessions", json={})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_employee_can_create_session_send_message_and_save_assistant_as_draft(
    monkeypatch, mysql_conn, mysql_app_client
):
    configure_ai(monkeypatch)
    headers = auth_headers(mysql_conn, mysql_app_client, "flow")
    session_id = create_session(mysql_app_client, headers)

    reply = mysql_app_client.post(
        f"/api/inspiration/sessions/{session_id}/messages",
        headers=headers,
        json={"content": "Give me five topic ideas"},
    )

    assert reply.status_code == 200
    payload = reply.json()["data"]
    assert payload["assistant_message"]["role"] == "assistant"
    assert payload["credit_cost"] == 1
    assert payload["assistant_message"]["status"] == "success"

    message_id = payload["assistant_message"]["id"]
    first_save = mysql_app_client.post(
        f"/api/inspiration/messages/{message_id}/save-draft",
        headers=headers,
    )
    second_save = mysql_app_client.post(
        f"/api/inspiration/messages/{message_id}/save-draft",
        headers=headers,
    )

    assert first_save.status_code == 200
    assert second_save.status_code == 200
    assert first_save.json()["data"]["draft_id"] == second_save.json()["data"]["draft_id"]
    with mysql_conn.cursor() as cursor:
        cursor.execute("select count(*) as total from content_draft where source_type = 'inspiration'")
        assert cursor.fetchone()["total"] == 1
        cursor.execute("select total_credit_cost from inspiration_session where id = %s", (session_id,))
        assert cursor.fetchone()["total_credit_cost"] == 1


def test_employee_sessions_are_user_isolated(mysql_conn, mysql_app_client):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "other")
    session_id = create_session(mysql_app_client, owner_headers)

    response = mysql_app_client.get(
        f"/api/inspiration/sessions/{session_id}", headers=other_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_management_can_read_own_tenant_complete_session_but_not_other_tenant(
    monkeypatch, mysql_conn, mysql_app_client
):
    configure_ai(monkeypatch)
    employee_headers = auth_headers(mysql_conn, mysql_app_client, "admin-read", tenant_id=7)
    session_id = create_session(mysql_app_client, employee_headers)
    mysql_app_client.post(
        f"/api/inspiration/sessions/{session_id}/messages",
        headers=employee_headers,
        json={"content": "Give me five topic ideas"},
    )
    same_tenant_admin = management_headers(mysql_conn, "same", tenant_id=7)
    other_tenant_admin = management_headers(mysql_conn, "other", tenant_id=8)

    response = mysql_app_client.get(
        f"/api/admin/inspiration/sessions/{session_id}", headers=same_tenant_admin
    )
    hidden = mysql_app_client.get(
        f"/api/admin/inspiration/sessions/{session_id}", headers=other_tenant_admin
    )

    assert response.status_code == 200
    assert len(response.json()["data"]["messages"]) == 2
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "NOT_FOUND"


def test_archived_session_rejects_new_messages(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "archived")
    session_id = create_session(mysql_app_client, headers)

    archived = mysql_app_client.post(
        f"/api/inspiration/sessions/{session_id}/archive", headers=headers
    )
    response = mysql_app_client.post(
        f"/api/inspiration/sessions/{session_id}/messages",
        headers=headers,
        json={"content": "This must not be sent"},
    )

    assert archived.status_code == 200
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SESSION_ARCHIVED"


def test_provider_failure_persists_failed_message_without_credit_charge(
    monkeypatch, mysql_conn, mysql_app_client
):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    headers = auth_headers(mysql_conn, mysql_app_client, "provider-failure")
    session_id = create_session(mysql_app_client, headers)

    response = mysql_app_client.post(
        f"/api/inspiration/sessions/{session_id}/messages",
        headers=headers,
        json={"content": "Give me five topic ideas"},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_PROVIDER_ERROR"
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select status, credit_cost from inspiration_message where session_id = %s order by id desc",
            (session_id,),
        )
        failed = cursor.fetchone()
        assert failed == {"status": "failed", "credit_cost": 0}
        cursor.execute(
            "select credit_cost from ai_usage_log where business_type = 'inspiration_chat' order by id desc"
        )
        assert cursor.fetchone()["credit_cost"] == 0
        cursor.execute("select total_credit_cost from inspiration_session where id = %s", (session_id,))
        assert cursor.fetchone()["total_credit_cost"] == 0
