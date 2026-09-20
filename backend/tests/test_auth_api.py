import pytest

from app.core.config import default_config
from app.core.security import hash_password, verify_access_token
from app.schemas.auth import AuthUser, RegisterRequest
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthError, AuthService


class FakeAuthCursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = 0
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
        self.rowcount = 0
        if normalized.startswith("select id from app_user"):
            self._row = self.conn.existing_user
        elif "from invite_code" in normalized and "for update" in normalized:
            self._row = self.conn.invite
        elif normalized.startswith("insert into app_user"):
            self.lastrowid = 101
        elif normalized.startswith("insert into credit_wallet"):
            self.lastrowid = 201
        elif normalized.startswith("update invite_code"):
            self.rowcount = self.conn.invite_update_rowcount

    def fetchone(self):
        return self._row


class FakeAuthConnection:
    def __init__(self, invite_update_rowcount=1):
        self.existing_user = None
        self.invite = {
            "id": 1,
            "tenant_id": 1,
            "code": "INV-A",
            "initial_credits": 66,
            "max_uses": 1,
            "used_count": 0,
            "expires_time": 0,
            "status": 1,
            "remark": "",
            "create_time": 0,
            "update_time": 0,
        }
        self.invite_update_rowcount = invite_update_rowcount
        self.statements = []
        self.commit_count = 0
        self.rollback_count = 0

    def cursor(self):
        return FakeAuthCursor(self)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def test_register_schema_accepts_optional_nickname_and_six_character_password():
    payload = RegisterRequest(
        login_name="operator_a",
        password="123456",
        invite_code="INV-A",
    )

    assert payload.nickname == ""


def test_auth_user_includes_tenant_id():
    user = AuthUser(
        id=7,
        tenant_id=3,
        login_name="tenant_user",
        nickname="Tenant User",
        user_role="customer",
        wallet_balance=0,
    )

    assert user.model_dump()["tenant_id"] == 3


def test_register_rolls_back_when_invite_update_loses_race():
    conn = FakeAuthConnection(invite_update_rowcount=0)
    service = AuthService(conn, default_config())

    with pytest.raises(AuthError) as exc:
        service.register(
            RegisterRequest(
                login_name="operator_a",
                password="123456",
                invite_code="INV-A",
            )
        )

    assert exc.value.code == "INVALID_INVITE_CODE"
    assert conn.commit_count == 0
    assert conn.rollback_count == 1
    assert any("for update" in statement for statement in conn.statements)
    assert any("insert into app_user" in statement for statement in conn.statements)
    assert any("insert into credit_wallet" in statement for statement in conn.statements)


def test_register_with_invite_code_returns_token_user_and_wallet(mysql_conn, mysql_app_client):
    users = UserRepository(mysql_conn)
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


def test_register_inherits_tenant_from_invite_code(mysql_conn, mysql_app_client):
    repo = UserRepository(mysql_conn)
    repo.create_invite_code(
        "TENANT-INVITE",
        initial_credits=0,
        max_uses=2,
        expires_time=0,
        remark="tenant test",
        tenant_id=7,
    )

    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "tenant_user",
            "nickname": "Tenant User",
            "password": "matrix-secret",
            "invite_code": "TENANT-INVITE",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["user"]["tenant_id"] == 7
    assert repo.get_by_login_name("tenant_user")["tenant_id"] == 7


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


def test_register_rejects_duplicate_login_name(mysql_conn, mysql_app_client):
    users = UserRepository(mysql_conn)
    users.create_invite_code(
        "INV-DUPLICATE",
        initial_credits=0,
        max_uses=2,
        expires_time=0,
        remark="customer",
    )
    payload = {
        "login_name": "operator_duplicate",
        "nickname": "operator Duplicate",
        "password": "matrix-secret",
        "invite_code": "INV-DUPLICATE",
    }

    first = mysql_app_client.post("/api/auth/register", json=payload)
    second = mysql_app_client.post("/api/auth/register", json=payload)

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "USER_EXISTS"


def test_register_rejects_used_invite_code(mysql_conn, mysql_app_client):
    users = UserRepository(mysql_conn)
    users.create_invite_code("INV-USED", initial_credits=0, max_uses=1, expires_time=0, remark="customer")
    first = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "operator_used_a",
            "nickname": "operator Used A",
            "password": "matrix-secret",
            "invite_code": "INV-USED",
        },
    )
    second = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "operator_used_b",
            "nickname": "operator Used B",
            "password": "matrix-secret",
            "invite_code": "INV-USED",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "INVALID_INVITE_CODE"


def test_login_returns_token_after_registration(mysql_conn, mysql_app_client):
    users = UserRepository(mysql_conn)
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
        "/api/auth/customer/login",
        json={"login_name": "operator_login", "password": "matrix-secret"},
    )

    assert register.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["access_token"]
    assert payload["data"]["user"]["login_name"] == "operator_login"


def test_login_rejects_wrong_password(mysql_conn, mysql_app_client):
    users = UserRepository(mysql_conn)
    users.create_invite_code("INV-WRONG", initial_credits=0, max_uses=1, expires_time=0, remark="customer")
    register = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "operator_wrong",
            "nickname": "operator Wrong",
            "password": "matrix-secret",
            "invite_code": "INV-WRONG",
        },
    )

    response = mysql_app_client.post(
        "/api/auth/customer/login",
        json={"login_name": "operator_wrong", "password": "wrong-secret"},
    )

    assert register.status_code == 200
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_returns_current_user(mysql_conn, mysql_app_client):
    users = UserRepository(mysql_conn)
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
    assert payload["data"]["tenant_id"] == 1


def test_me_requires_bearer_token(app_client_without_db):
    response = app_client_without_db.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize(
    ("portal", "role", "expected_status"),
    [
        ("customer", "customer", 200),
        ("customer", "client_owner", 403),
        ("manager", "client_owner", 200),
        ("manager", "client_admin", 403),
        ("manager", "customer", 403),
        ("developer", "platform_admin", 200),
        ("developer", "developer_admin", 200),
        ("developer", "customer", 403),
    ],
)
def test_portal_login_enforces_role(
    mysql_conn,
    mysql_app_client,
    portal,
    role,
    expected_status,
):
    login_name = f"{portal}_{role}"
    UserRepository(mysql_conn).create_user(
        login_name=login_name,
        nickname=login_name,
        password_hash=hash_password("strong-password"),
        user_role=role,
        invite_code="",
        tenant_id=17,
    )

    response = mysql_app_client.post(
        f"/api/auth/{portal}/login",
        json={"login_name": login_name, "password": "strong-password"},
    )

    assert response.status_code == expected_status
    if expected_status == 200:
        token = response.json()["data"]["access_token"]
        claims = verify_access_token(
            token,
            mysql_app_client.app.state.config.auth.token_secret,
        )
        assert claims["aud"] == portal
        assert claims["tenant_id"] == 17
    else:
        assert response.json()["error"]["code"] == "PORTAL_FORBIDDEN"
