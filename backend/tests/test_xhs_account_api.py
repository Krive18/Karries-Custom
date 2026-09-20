import pytest
from pydantic import ValidationError

from app.repositories.xhs_account_repository import XHSAccountRepository
from app.repositories.user_repository import UserRepository
from app.schemas.xhs_account import (
    XHSAccountCreate,
    XHSAccountProfile,
    XHSAccountProfileUpdate,
)


class FakeXHSCursor:
    def __init__(self, conn):
        self.conn = conn
        self.lastrowid = 0
        self._row = None

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def execute(self, sql, _params=()):
        normalized = " ".join(sql.lower().split())
        self.conn.statements.append(normalized)
        self._row = None
        if normalized.startswith("insert into xhs_account "):
            self.lastrowid = 42
        elif normalized.startswith("insert into xhs_account_profile"):
            if self.conn.fail_profile_insert:
                raise RuntimeError("profile insert failed")
            self.lastrowid = 43
        elif normalized.startswith("select id from xhs_account where"):
            self._row = {"id": 42}
        elif normalized.startswith("select id from xhs_account_profile"):
            self._row = {"id": 43}
        elif normalized.startswith("update xhs_account_profile"):
            if self.conn.fail_profile_update:
                raise RuntimeError("profile update failed")

    def fetchone(self):
        return self._row


class FakeXHSConnection:
    def __init__(self, fail_profile_insert=False, fail_profile_update=False):
        self.fail_profile_insert = fail_profile_insert
        self.fail_profile_update = fail_profile_update
        self.statements = []
        self.commit_count = 0
        self.rollback_count = 0

    def cursor(self):
        return FakeXHSCursor(self)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def auth_headers(mysql_conn, mysql_app_client, suffix: str) -> dict[str, str]:
    invite_code = f"INV-XHS-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=0,
        max_uses=1,
        expires_time=0,
        remark="xhs-account-api",
    )

    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": f"xhs_user_{suffix}",
            "nickname": f"XHS User {suffix}",
            "password": "matrix-secret",
            "invite_code": invite_code,
        },
    )

    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_xhs_profile_update_rejects_explicit_null_values():
    with pytest.raises(ValidationError):
        XHSAccountProfileUpdate(persona=None)


def test_xhs_profile_rejects_unreasonable_word_count():
    with pytest.raises(ValidationError):
        XHSAccountProfile(word_count_preference=-1)


def test_xhs_account_create_rolls_back_when_profile_insert_fails():
    conn = FakeXHSConnection(fail_profile_insert=True)

    with pytest.raises(RuntimeError, match="profile insert failed"):
        XHSAccountRepository(conn).create(
            12,
            XHSAccountCreate(display_name="Matrix account"),
        )

    assert conn.commit_count == 0
    assert conn.rollback_count == 1
    assert any("insert into xhs_account " in statement for statement in conn.statements)
    assert any("insert into xhs_account_profile" in statement for statement in conn.statements)


def test_xhs_account_update_rolls_back_when_profile_update_fails():
    conn = FakeXHSConnection(fail_profile_update=True)

    with pytest.raises(RuntimeError, match="profile update failed"):
        XHSAccountRepository(conn).update_profile(
            12,
            42,
            XHSAccountProfile(persona="updated"),
        )

    assert conn.commit_count == 0
    assert conn.rollback_count == 1


def test_create_xhs_account_with_profile_and_list(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "create")

    response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=headers,
        json={
            "display_name": "Karries main",
            "account_group": "beauty",
            "daily_limit": 3,
            "min_interval_minutes": 240,
            "profile": {
                "domain_name": "beauty care",
                "persona": "gentle product consultant",
                "tag_preferences": "[\"#Karries\", \"#skincare\"]",
                "word_count_preference": 450,
            },
        },
    )

    assert response.status_code == 200
    created = response.json()["data"]
    assert created["id"] > 0
    assert created["display_name"] == "Karries main"
    assert created["profile"]["domain_name"] == "beauty care"
    assert created["profile"]["persona"] == "gentle product consultant"
    assert created["profile"]["tag_preferences"] == "[\"#Karries\", \"#skincare\"]"
    assert created["profile"]["word_count_preference"] == 450
    assert created["login_state_ready"] is False
    assert "login_state_path" not in created

    list_response = mysql_app_client.get("/api/xhs-accounts", headers=headers)

    assert list_response.status_code == 200
    accounts = list_response.json()["data"]
    assert len(accounts) == 1
    assert accounts[0]["id"] == created["id"]
    assert accounts[0]["account_group"] == "beauty"
    assert accounts[0]["daily_limit"] == 3
    assert accounts[0]["min_interval_minutes"] == 240
    assert accounts[0]["profile"]["domain_name"] == "beauty care"
    assert accounts[0]["profile"]["persona"] == "gentle product consultant"
    assert accounts[0]["profile"]["tag_preferences"] == "[\"#Karries\", \"#skincare\"]"


def test_start_xhs_login_session_and_get_latest(
    mysql_conn,
    mysql_app_client,
    monkeypatch,
):
    headers = auth_headers(mysql_conn, mysql_app_client, "login-start")
    create_response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=headers,
        json={"display_name": "Login account"},
    )
    account_id = create_response.json()["data"]["id"]

    async def fake_login_runner(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.api.xhs_accounts.run_xhs_account_login",
        fake_login_runner,
    )
    start_response = mysql_app_client.post(
        f"/api/xhs-accounts/{account_id}/login/start",
        headers=headers,
    )

    assert start_response.status_code == 202
    session = start_response.json()["data"]
    assert session["xhs_account_id"] == account_id
    assert session["status"] == "starting"
    assert session["qrcode_image_data"] == ""
    assert "operation_token" not in session
    assert "login_state_path" not in session

    latest_response = mysql_app_client.get(
        f"/api/xhs-accounts/{account_id}/login/session",
        headers=headers,
    )
    assert latest_response.status_code == 200
    assert latest_response.json()["data"]["id"] == session["id"]


def test_xhs_login_session_is_user_isolated(
    mysql_conn,
    mysql_app_client,
    monkeypatch,
):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "login-owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "login-other")
    create_response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=owner_headers,
        json={"display_name": "Owner login account"},
    )
    account_id = create_response.json()["data"]["id"]

    async def fake_login_runner(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.api.xhs_accounts.run_xhs_account_login",
        fake_login_runner,
    )
    response = mysql_app_client.post(
        f"/api/xhs-accounts/{account_id}/login/start",
        headers=other_headers,
    )
    assert response.status_code == 404


def test_check_xhs_login_updates_public_status(
    mysql_conn,
    mysql_app_client,
    monkeypatch,
):
    headers = auth_headers(mysql_conn, mysql_app_client, "login-check")
    create_response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=headers,
        json={"display_name": "Checked account"},
    )
    account_id = create_response.json()["data"]["id"]
    user_id = create_response.json()["data"]["user_id"]
    XHSAccountRepository(mysql_conn).update_login_state(
        user_id,
        account_id,
        status=2,
        login_state_path="data/xhs_accounts/test/storage_state.json",
    )

    async def valid_cookie(_account_file: str) -> bool:
        return True

    monkeypatch.setattr(
        "app.services.xhs_account_login_service.check_cookie",
        valid_cookie,
    )
    response = mysql_app_client.post(
        f"/api/xhs-accounts/{account_id}/login/check",
        headers=headers,
    )

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["valid"] is True
    assert result["account"]["status"] == 1
    assert result["account"]["login_state_ready"] is True
    assert "login_state_path" not in result["account"]


def test_xhs_accounts_are_user_isolated(mysql_conn, mysql_app_client):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "other")
    create_response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=owner_headers,
        json={
            "display_name": "Owner account",
            "profile": {"persona": "owner persona"},
        },
    )
    assert create_response.status_code == 200
    account_id = create_response.json()["data"]["id"]

    list_response = mysql_app_client.get("/api/xhs-accounts", headers=other_headers)

    assert list_response.status_code == 200
    assert list_response.json()["data"] == []

    update_response = mysql_app_client.put(
        f"/api/xhs-accounts/{account_id}/profile",
        headers=other_headers,
        json={"persona": "should not update"},
    )

    assert update_response.status_code == 404
    payload = update_response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_update_xhs_account_profile(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "update")
    create_response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=headers,
        json={
            "display_name": "Profile account",
            "profile": {
                "persona": "initial persona",
                "tone": "warm",
                "tag_preferences": "[\"#before\"]",
            },
        },
    )
    assert create_response.status_code == 200
    account_id = create_response.json()["data"]["id"]

    update_response = mysql_app_client.put(
        f"/api/xhs-accounts/{account_id}/profile",
        headers=headers,
        json={
            "persona": "updated persona",
            "tone": "professional",
            "tag_preferences": "[\"#after\", \"#matrix\"]",
            "word_count_preference": 520,
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["id"] == account_id
    assert updated["profile"]["persona"] == "updated persona"
    assert updated["profile"]["tone"] == "professional"
    assert updated["profile"]["tag_preferences"] == "[\"#after\", \"#matrix\"]"
    assert updated["profile"]["word_count_preference"] == 520

    list_response = mysql_app_client.get("/api/xhs-accounts", headers=headers)

    assert list_response.status_code == 200
    account = list_response.json()["data"][0]
    assert account["id"] == account_id
    assert account["profile"]["persona"] == "updated persona"
    assert account["profile"]["tone"] == "professional"
    assert account["profile"]["tag_preferences"] == "[\"#after\", \"#matrix\"]"
    assert account["profile"]["word_count_preference"] == 520


def test_update_and_delete_xhs_account(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "full-update-delete")
    create_response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=headers,
        json={
            "display_name": "Original account",
            "account_group": "original",
            "daily_limit": 1,
            "min_interval_minutes": 360,
            "profile": {"domain_name": "original domain"},
        },
    )
    assert create_response.status_code == 200
    account_id = create_response.json()["data"]["id"]

    update_response = mysql_app_client.put(
        f"/api/xhs-accounts/{account_id}",
        headers=headers,
        json={
            "display_name": "Updated account",
            "account_group": "flagship",
            "daily_limit": 4,
            "min_interval_minutes": 180,
            "profile": {
                "domain_name": "beauty care",
                "persona": "professional beauty consultant",
                "tone": "warm and clear",
            },
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["display_name"] == "Updated account"
    assert updated["account_group"] == "flagship"
    assert updated["daily_limit"] == 4
    assert updated["min_interval_minutes"] == 180
    assert updated["profile"]["domain_name"] == "beauty care"
    assert updated["profile"]["persona"] == "professional beauty consultant"

    delete_response = mysql_app_client.delete(
        f"/api/xhs-accounts/{account_id}",
        headers=headers,
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["data"] == {"deleted": True}
    list_response = mysql_app_client.get("/api/xhs-accounts", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["data"] == []


def test_update_and_delete_xhs_account_are_user_isolated(
    mysql_conn,
    mysql_app_client,
):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "edit-owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "edit-other")
    create_response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=owner_headers,
        json={"display_name": "Owner account"},
    )
    account_id = create_response.json()["data"]["id"]

    update_response = mysql_app_client.put(
        f"/api/xhs-accounts/{account_id}",
        headers=other_headers,
        json={"display_name": "Cross user update"},
    )
    delete_response = mysql_app_client.delete(
        f"/api/xhs-accounts/{account_id}",
        headers=other_headers,
    )

    assert update_response.status_code == 404
    assert delete_response.status_code == 404


def test_xhs_account_requires_auth(app_client_without_db):
    response = app_client_without_db.get("/api/xhs-accounts")

    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNAUTHORIZED"
