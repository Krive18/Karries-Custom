from types import SimpleNamespace
import time

import pymysql
import pytest

from app.core.security import create_access_token
from app.integrations.deepseek import TextGenerationResult
from app.repositories.inspiration_repository import (
    InspirationRepository,
    InspirationSessionStateError,
)
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
        cursor.execute("select count(*) as total from content_draft_source")
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


def test_generating_session_rejects_concurrent_send_and_archive(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "generating")
    session_id = create_session(mysql_app_client, headers)
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            update inspiration_session
            set status = 'generating', generation_token = 'live-token',
                generation_started_time = %s
            where id = %s
            """,
            (int(time.time()), session_id),
        )
    mysql_conn.commit()

    send_response = mysql_app_client.post(
        f"/api/inspiration/sessions/{session_id}/messages",
        headers=headers,
        json={"content": "This must not overlap"},
    )
    archive_response = mysql_app_client.post(
        f"/api/inspiration/sessions/{session_id}/archive", headers=headers
    )

    assert send_response.status_code == 409
    assert send_response.json()["error"]["code"] == "SESSION_GENERATING"
    assert archive_response.status_code == 409
    assert archive_response.json()["error"]["code"] == "SESSION_GENERATING"


def test_expired_generation_lease_can_send_again(monkeypatch, mysql_conn, mysql_app_client):
    configure_ai(monkeypatch)
    headers = auth_headers(mysql_conn, mysql_app_client, "expired-send")
    session_id = create_session(mysql_app_client, headers)
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            update inspiration_session
            set status = 'generating', generation_token = 'stale-token',
                generation_started_time = 1
            where id = %s
            """,
            (session_id,),
        )
    mysql_conn.commit()

    response = mysql_app_client.post(
        f"/api/inspiration/sessions/{session_id}/messages",
        headers=headers,
        json={"content": "Recover this generation"},
    )

    assert response.status_code == 200
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select status, generation_token, generation_started_time
            from inspiration_session where id = %s
            """,
            (session_id,),
        )
        assert cursor.fetchone() == {
            "status": "active",
            "generation_token": "",
            "generation_started_time": 0,
        }


def test_expired_generation_lease_can_archive(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "expired-archive")
    session_id = create_session(mysql_app_client, headers)
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            update inspiration_session
            set status = 'generating', generation_token = 'stale-token',
                generation_started_time = 1
            where id = %s
            """,
            (session_id,),
        )
    mysql_conn.commit()

    response = mysql_app_client.post(
        f"/api/inspiration/sessions/{session_id}/archive", headers=headers
    )

    assert response.status_code == 200
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select status, generation_token, generation_started_time
            from inspiration_session where id = %s
            """,
            (session_id,),
        )
        assert cursor.fetchone() == {
            "status": "archived",
            "generation_token": "",
            "generation_started_time": 0,
        }


def test_failed_finalization_generation_is_recoverable_after_lease(
    monkeypatch, mysql_conn, mysql_app_client
):
    from app.services import inspiration_service

    configure_ai(monkeypatch)

    class FailingUsageService:
        def __init__(self, _repository):
            pass

        def record_success(self, **_kwargs):
            raise RuntimeError("usage write failed")

    monkeypatch.setattr(inspiration_service, "AIUsageService", FailingUsageService)
    headers = auth_headers(mysql_conn, mysql_app_client, "failed-lease")
    session_id = create_session(mysql_app_client, headers)

    with pytest.raises(RuntimeError, match="usage write failed"):
        mysql_app_client.post(
            f"/api/inspiration/sessions/{session_id}/messages",
            headers=headers,
            json={"content": "This finalization will fail"},
        )

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select status, generation_token, generation_started_time
            from inspiration_session where id = %s
            """,
            (session_id,),
        )
        failed_state = cursor.fetchone()
        assert failed_state["status"] == "generating"
        assert failed_state["generation_token"]
        cursor.execute(
            """
            update inspiration_session set generation_started_time = 1 where id = %s
            """,
            (session_id,),
        )
    mysql_conn.commit()

    response = mysql_app_client.post(
        f"/api/inspiration/sessions/{session_id}/archive", headers=headers
    )

    assert response.status_code == 200


def test_late_generation_token_cannot_finalize_new_operation(
    mysql_conn, mysql_app_client
):
    headers = auth_headers(mysql_conn, mysql_app_client, "late-token")
    session_id = create_session(mysql_app_client, headers)
    started_at = int(time.time())
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select tenant_id, user_id from inspiration_session where id = %s",
            (session_id,),
        )
        owner = cursor.fetchone()
        cursor.execute(
            """
            update inspiration_session
            set status = 'generating', generation_token = 'new-token',
                generation_started_time = %s
            where id = %s
            """,
            (started_at, session_id),
        )
    mysql_conn.commit()

    with pytest.raises(InspirationSessionStateError):
        InspirationRepository(mysql_conn).finalize_generation(
            tenant_id=owner["tenant_id"],
            user_id=owner["user_id"],
            session_id=session_id,
            content="late assistant response",
            context={},
            ai_provider="deepseek",
            ai_model="deepseek-chat",
            generation_token="old-token",
            credit_cost=1,
            latency_ms=1,
            status="success",
        )
    mysql_conn.rollback()

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select status, generation_token, generation_started_time
            from inspiration_session where id = %s
            """,
            (session_id,),
        )
        assert cursor.fetchone() == {
            "status": "generating",
            "generation_token": "new-token",
            "generation_started_time": started_at,
        }
        cursor.execute(
            "select count(*) as total from inspiration_message where session_id = %s",
            (session_id,),
        )
        assert cursor.fetchone()["total"] == 0


def test_session_rejects_linked_resources_owned_by_another_user(mysql_conn, mysql_app_client):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "linked-owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "linked-other")
    product = mysql_app_client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "product_name": "Private product",
            "brand_name": "KARRIES",
            "category": "skincare",
            "selling_point": {"points": ["private"]},
            "ai_material": {},
        },
    )
    account = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=owner_headers,
        json={"display_name": "Private account", "profile": {}},
    )
    assert product.status_code == 200
    assert account.status_code == 200

    response = mysql_app_client.post(
        "/api/inspiration/sessions",
        headers=other_headers,
        json={
            "title": "Unauthorized links",
            "linked_product_id": product.json()["data"]["id"],
            "linked_xhs_account_id": account.json()["data"]["id"],
            "goal_type": "topic",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


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


class _DuplicateMappingCursor:
    def __init__(self, conn):
        self.conn = conn
        self.lastrowid = 0
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, _params):
        normalized = " ".join(sql.lower().split())
        self.conn.sql.append(normalized)
        if "select id from content_draft" in normalized:
            raise AssertionError("idempotency must be enforced by the mapping unique key")
        if "insert into content_draft (" in normalized:
            self.lastrowid = 22
            return
        if "insert into content_draft_source" in normalized:
            raise pymysql.err.IntegrityError(1062, "duplicate source mapping")
        if "select content_draft_id from content_draft_source" in normalized:
            self.row = {"content_draft_id": 41}
            return
        raise AssertionError(f"unexpected SQL: {normalized}")

    def fetchone(self):
        return self.row


class _DuplicateMappingConnection:
    def __init__(self):
        self.sql = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return _DuplicateMappingCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_save_draft_returns_existing_mapping_after_concurrent_unique_conflict():
    from app.repositories.content_draft_repository import ContentDraftRepository

    conn = _DuplicateMappingConnection()
    draft_id = ContentDraftRepository(conn).create_from_ai_text(
        tenant_id=7,
        user_id=3,
        source_type="inspiration",
        source_id=11,
        title="Generated title",
        body="Generated body",
        ai_provider="deepseek",
        model_name="deepseek-chat",
        context={"linked_product_id": 0, "linked_xhs_account_id": 0},
    )

    assert draft_id == 41
    assert conn.commits == 0
    assert conn.rollbacks == 1
    assert any("insert into content_draft_source" in sql for sql in conn.sql)


class _WorkflowConnection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _WorkflowRepository:
    def __init__(self, _conn):
        self.finalized = []

    def claim_and_store_user_message(self, *_args):
        return {
            "id": 9,
            "title": "Campaign",
            "linked_product_id": 0,
            "linked_xhs_account_id": 0,
            "goal_type": "topic",
            "tone": "natural",
            "extra_requirement": "",
        }, {"id": 20, "role": "user", "content": "ideas"}, "generation-token"

    def get_session_for_user(self, *_args):
        return {
            "id": 9,
            "title": "Campaign",
            "linked_product_id": 0,
            "linked_xhs_account_id": 0,
            "goal_type": "topic",
            "tone": "natural",
            "extra_requirement": "",
        }

    def list_successful_history(self, *_args):
        self.history_args = _args
        return [("user", "ideas")]

    def finalize_generation(self, *_args, **_kwargs):
        self.finalized.append((_args, _kwargs))
        return 21

    def get_message_for_user(self, *_args):
        return {"id": 21, "role": "assistant", "status": "success"}


def test_success_finalization_commits_assistant_session_and_usage_together(monkeypatch):
    from app.services import inspiration_service

    conn = _WorkflowConnection()
    repo = _WorkflowRepository(conn)
    usage_calls = []

    class FakeUsageService:
        def __init__(self, _repository):
            pass

        def record_success(self, **kwargs):
            usage_calls.append(kwargs)

    monkeypatch.setattr(inspiration_service, "InspirationRepository", lambda _conn: repo)
    monkeypatch.setattr(inspiration_service, "AIUsageService", FakeUsageService)
    service = inspiration_service.InspirationService(conn)
    monkeypatch.setattr(
        service,
        "_provider_from_settings_snapshot",
        lambda: (
            SimpleNamespace(provider="deepseek", model="deepseek-chat"),
            SimpleNamespace(
                generate_text=lambda *_args, **_kwargs: TextGenerationResult(
                    content="assistant reply",
                    provider="deepseek",
                    model_name="deepseek-chat",
                    latency_ms=3,
                    input_chars=8,
                    output_chars=15,
                )
            ),
        ),
    )

    result = service.send_message(
        {"tenant_id": 7, "id": 3}, 9, SimpleNamespace(content="ideas")
    )

    assert result["assistant_message"]["id"] == 21
    assert len(repo.finalized) == 1
    assert repo.finalized[0][1]["generation_token"] == "generation-token"
    assert repo.history_args[-1] == 20
    assert usage_calls[0]["commit"] is False
    assert conn.commits == 3
    assert conn.rollbacks == 0


def test_failed_finalization_rolls_back_assistant_session_and_usage(monkeypatch):
    from app.services import inspiration_service

    conn = _WorkflowConnection()
    repo = _WorkflowRepository(conn)

    class FailingUsageService:
        def __init__(self, _repository):
            pass

        def record_success(self, **_kwargs):
            raise RuntimeError("usage write failed")

    monkeypatch.setattr(inspiration_service, "InspirationRepository", lambda _conn: repo)
    monkeypatch.setattr(inspiration_service, "AIUsageService", FailingUsageService)
    service = inspiration_service.InspirationService(conn)
    monkeypatch.setattr(
        service,
        "_provider_from_settings_snapshot",
        lambda: (
            SimpleNamespace(provider="deepseek", model="deepseek-chat"),
            SimpleNamespace(
                generate_text=lambda *_args, **_kwargs: TextGenerationResult(
                    content="assistant reply",
                    provider="deepseek",
                    model_name="deepseek-chat",
                    latency_ms=3,
                    input_chars=8,
                    output_chars=15,
                )
            ),
        ),
    )

    with pytest.raises(RuntimeError, match="usage write failed"):
        service.send_message(
            {"tenant_id": 7, "id": 3}, 9, SimpleNamespace(content="ideas")
        )

    assert len(repo.finalized) == 1
    assert conn.rollbacks == 1


def test_service_rolls_back_when_late_generation_token_cannot_finalize(monkeypatch):
    from app.repositories.inspiration_repository import InspirationSessionStateError
    from app.services import inspiration_service

    conn = _WorkflowConnection()
    repo = _WorkflowRepository(conn)

    def reject_stale_finalize(*_args, **_kwargs):
        raise InspirationSessionStateError("generating")

    repo.finalize_generation = reject_stale_finalize
    monkeypatch.setattr(inspiration_service, "InspirationRepository", lambda _conn: repo)
    service = inspiration_service.InspirationService(conn)
    monkeypatch.setattr(
        service,
        "_provider_from_settings_snapshot",
        lambda: (
            SimpleNamespace(provider="deepseek", model="deepseek-chat"),
            SimpleNamespace(
                generate_text=lambda *_args, **_kwargs: TextGenerationResult(
                    content="assistant reply",
                    provider="deepseek",
                    model_name="deepseek-chat",
                    latency_ms=3,
                    input_chars=8,
                    output_chars=15,
                )
            ),
        ),
    )

    with pytest.raises(InspirationSessionStateError):
        service.send_message(
            {"tenant_id": 7, "id": 3}, 9, SimpleNamespace(content="ideas")
        )

    assert conn.rollbacks == 1


def test_provider_failure_finalization_commits_failed_message_session_and_usage(monkeypatch):
    from app.services import inspiration_service
    from app.services.ai_provider_service import AIProviderError

    conn = _WorkflowConnection()
    repo = _WorkflowRepository(conn)
    usage_calls = []

    class FakeUsageService:
        def __init__(self, _repository):
            pass

        def record_failure(self, **kwargs):
            usage_calls.append(kwargs)

    monkeypatch.setattr(inspiration_service, "InspirationRepository", lambda _conn: repo)
    monkeypatch.setattr(inspiration_service, "AIUsageService", FakeUsageService)
    service = inspiration_service.InspirationService(conn)
    monkeypatch.setattr(
        service,
        "_provider_from_settings_snapshot",
        lambda: (
            SimpleNamespace(provider="deepseek", model="deepseek-chat"),
            SimpleNamespace(
                generate_text=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    AIProviderError("timeout", "provider timeout")
                )
            ),
        ),
    )

    with pytest.raises(inspiration_service.InspirationProviderError):
        service.send_message(
            {"tenant_id": 7, "id": 3}, 9, SimpleNamespace(content="ideas")
        )

    assert repo.finalized[0][1]["status"] == "failed"
    assert usage_calls[0]["commit"] is False
    assert conn.commits == 3
    assert conn.rollbacks == 0


def test_provider_failure_finalization_rolls_back_when_usage_write_fails(monkeypatch):
    from app.services import inspiration_service
    from app.services.ai_provider_service import AIProviderError

    conn = _WorkflowConnection()
    repo = _WorkflowRepository(conn)

    class FailingUsageService:
        def __init__(self, _repository):
            pass

        def record_failure(self, **_kwargs):
            raise RuntimeError("failure usage write failed")

    monkeypatch.setattr(inspiration_service, "InspirationRepository", lambda _conn: repo)
    monkeypatch.setattr(inspiration_service, "AIUsageService", FailingUsageService)
    service = inspiration_service.InspirationService(conn)
    monkeypatch.setattr(
        service,
        "_provider_from_settings_snapshot",
        lambda: (
            SimpleNamespace(provider="deepseek", model="deepseek-chat"),
            SimpleNamespace(
                generate_text=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    AIProviderError("timeout", "provider timeout")
                )
            ),
        ),
    )

    with pytest.raises(RuntimeError, match="failure usage write failed"):
        service.send_message(
            {"tenant_id": 7, "id": 3}, 9, SimpleNamespace(content="ideas")
        )

    assert len(repo.finalized) == 1
    assert conn.rollbacks == 1
