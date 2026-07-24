# Three-Portal Auth and Employee Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the current mixed customer/manager experience into three independently built applications with portal-specific login, then add the first production manager workflow: creating, listing, disabling, enabling, and resetting passwords for employee accounts that can log into the customer application.

**Architecture:** Keep one FastAPI and MySQL codebase, but register customer, manager, developer, and bootstrap route surfaces independently. Issue audience-bound access tokens from portal-specific login endpoints. Build customer, manager, and developer React entry points separately; each origin stores only its own temporary development token until the later cookie-hardening phase.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, PyMySQL, MySQL 8.0, pytest, React, TypeScript, Vite, Vitest, Testing Library, lucide-react.

## Global Constraints

- Customer, manager, and developer are separate applications with separate HTML entry points and login screens.
- Customer users must not see registration, manager navigation, or developer navigation.
- Manager login accepts only `client_owner` and `client_admin`.
- Developer login accepts only `platform_admin` and `developer_admin`.
- Manager-created employees always receive role `customer` and the manager's `tenant_id`.
- Both `client_owner` and `client_admin` can create employees and set long-term passwords.
- Only `client_owner` can grant or revoke `client_admin`; role management is outside this first foundation plan.
- Public registration is removed from customer, manager, and developer surfaces. It remains available only on the `all` test/bootstrap surface until seed tooling replaces it.
- New MySQL columns and indexes must have accurate comments and follow the existing MySQL 8.0 schema conventions.
- Never place API keys, real passwords, or production credentials in source, tests, logs, or commits.
- Use TDD for every behavior change and commit each task independently.

## Delivery Roadmap

This plan is the first independently testable batch. Later plans are executed in this order:

1. **Foundation, this plan:** three applications, portal login, managed employees, logout.
2. **Content workspace:** merge image creation and video production into one `智能创作` page with two tabs and reorder customer navigation.
3. **Xiaohe:** DeepSeek V4 quick/deep modes, streaming messages, product context, document attachments, product-variable extraction.
4. **Manager operations:** account matrix, content review, publish monitoring, product oversight, video monitoring, audit search.
5. **Commerce and production hardening:** recharge orders, wallet allocation, secure cookies, refresh sessions, rate limiting, Tencent Cloud deployment.

---

### Task 1: Split Backend Route Surfaces

**Files:**
- Create: `backend/app/api/bootstrap_auth.py`
- Create: `backend/app/manager_main.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/test_app_startup.py`

**Interfaces:**
- Produces: `ApiSurface = Literal["all", "customer", "manager", "developer"]`
- Produces: `POST /api/auth/{portal}/login`
- Produces: `GET /api/auth/me`
- Produces: bootstrap-only `POST /api/auth/register`
- Produces: `create_app("manager")`

- [ ] **Step 1: Write failing route-surface tests**

Add these assertions to `backend/tests/test_app_startup.py`:

```python
def test_customer_surface_excludes_manager_and_internal_routes():
    paths = route_paths(create_app("customer"))
    assert "/api/inspiration/sessions" in paths
    assert "/api/admin/summary" not in paths
    assert "/api/admin/users" not in paths
    assert "/api/settings/ai" not in paths
    assert "/api/auth/register" not in paths


def test_manager_surface_only_registers_management_business_routes():
    paths = route_paths(create_app("manager"))
    assert "/api/admin/summary" in paths
    assert "/api/admin/inspiration/sessions" in paths
    assert "/api/admin/viral-analysis/jobs" in paths
    assert "/api/inspiration/sessions" not in paths
    assert "/api/settings/ai" not in paths
    assert "/api/auth/register" not in paths


def test_all_surface_keeps_bootstrap_registration_for_test_seed_flows():
    paths = route_paths(create_app("all"))
    assert "/api/auth/register" in paths
```

- [ ] **Step 2: Run the startup tests and verify RED**

Run from `backend`:

```powershell
python -m pytest tests/test_app_startup.py -q
```

Expected: FAIL because `manager` is not a valid surface, customer still contains admin routes, and registration is present everywhere.

- [ ] **Step 3: Move registration into a bootstrap-only router**

Create `backend/app/api/bootstrap_auth.py`:

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection
from app.core.responses import fail, ok
from app.schemas.auth import RegisterRequest
from app.services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/api/auth", tags=["bootstrap-auth"], include_in_schema=False)


@router.post("/register")
def register(
    payload: RegisterRequest,
    request: Request,
    conn=Depends(get_db_connection),
) -> dict:
    try:
        result = AuthService(conn, request.app.state.config).register(payload)
    except AuthError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(exc.code, exc.message),
        )
    return ok(result.model_dump())
```

Remove the registration route and `RegisterRequest` import from `backend/app/api/auth.py`.

- [ ] **Step 4: Register four explicit backend surfaces**

Update `backend/app/main.py` so the surface contract and route groups are explicit:

```python
ApiSurface = Literal["all", "customer", "manager", "developer"]

app.state.api_surface = surface
app.include_router(auth_router)

if surface == "all":
    app.include_router(bootstrap_auth_router)

if surface in {"all", "customer"}:
    for router in customer_routers:
        app.include_router(router)

if surface in {"all", "manager"}:
    for router in manager_routers:
        app.include_router(router)

if surface in {"all", "developer"}:
    for router in developer_routers:
        app.include_router(router)
```

Use these exact groups:

```python
customer_routers = (
    ai_router,
    accounts_router,
    content_drafts_router,
    inspiration_router,
    viral_analysis_router,
    matrix_plans_router,
    products_router,
    runtime_router,
    tasks_router,
    video_edit_router,
    wallet_router,
    xhs_accounts_router,
)
manager_routers = (
    admin_router,
    admin_inspiration_router,
    admin_viral_analysis_router,
)
developer_routers = (
    developer_viral_analysis_router,
    settings_router,
    internal_video_edit_router,
    worker_matrix_publish_router,
)
```

Add local CORS origins for `5176` and `5177`.

- [ ] **Step 5: Add the manager ASGI entry**

Create `backend/app/manager_main.py`:

```python
from app.main import create_app

app = create_app("manager")
```

- [ ] **Step 6: Run route-surface tests and verify GREEN**

```powershell
python -m pytest tests/test_app_startup.py -q
```

Expected: all startup tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/api/bootstrap_auth.py backend/app/api/auth.py backend/app/main.py backend/app/manager_main.py backend/tests/test_app_startup.py
git commit -m "feat: split customer manager and developer API surfaces"
```

---

### Task 2: Add Portal-Specific Login and Audience-Bound Tokens

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/services/auth_service.py`
- Modify: `backend/app/core/dependencies.py`
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/test_auth_api.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Produces: `AuthPortal = Literal["customer", "manager", "developer"]`
- Produces: `AuthService.login_for_portal(payload, portal) -> AuthResponse`
- Produces token claim: `aud` equal to the authenticated portal
- Consumes: `request.app.state.api_surface`

- [ ] **Step 1: Write failing portal-login tests**

Add to `backend/tests/test_auth_api.py`:

```python
@pytest.mark.parametrize(
    ("portal", "role", "expected_status"),
    [
        ("customer", "customer", 200),
        ("customer", "client_owner", 403),
        ("manager", "client_owner", 200),
        ("manager", "client_admin", 200),
        ("manager", "customer", 403),
        ("developer", "developer_admin", 200),
        ("developer", "customer", 403),
    ],
)
def test_portal_login_enforces_role(mysql_conn, mysql_app_client, portal, role, expected_status):
    suffix = f"{portal}_{role}"
    user_id = UserRepository(mysql_conn).create_user(
        login_name=suffix,
        nickname=suffix,
        password_hash=hash_password("strong-password"),
        user_role=role,
        invite_code="",
        tenant_id=1,
    )
    WalletRepository(mysql_conn).create_wallet(user_id, 0, "portal login test")

    response = mysql_app_client.post(
        f"/api/auth/{portal}/login",
        json={"login_name": suffix, "password": "strong-password"},
    )

    assert response.status_code == expected_status
    if expected_status == 200:
        token = response.json()["data"]["access_token"]
        claims = verify_access_token(
            token,
            mysql_app_client.app.state.config.auth.token_secret,
        )
        assert claims["aud"] == portal
```

Add to `backend/tests/test_security.py`:

```python
def test_access_token_can_require_expected_audience():
    token = create_access_token(
        {"user_id": 1, "tenant_id": 1, "role": "customer", "aud": "customer"},
        secret="unit-secret",
        expires_in_seconds=60,
        now=1_800_000_000,
    )
    claims = verify_access_token(
        token,
        secret="unit-secret",
        now=1_800_000_001,
        expected_audience="customer",
    )
    assert claims["aud"] == "customer"


def test_access_token_rejects_wrong_audience():
    token = create_access_token(
        {"user_id": 1, "tenant_id": 1, "role": "customer", "aud": "customer"},
        secret="unit-secret",
        expires_in_seconds=60,
        now=1_800_000_000,
    )
    with pytest.raises(InvalidTokenError):
        verify_access_token(
            token,
            secret="unit-secret",
            now=1_800_000_001,
            expected_audience="manager",
        )
```

- [ ] **Step 2: Run focused tests and verify RED**

```powershell
python -m pytest tests/test_auth_api.py tests/test_security.py -q
```

Expected: FAIL because portal login and audience verification do not exist.

- [ ] **Step 3: Define portal roles**

Add to `backend/app/schemas/auth.py`:

```python
from typing import Literal

AuthPortal = Literal["customer", "manager", "developer"]
```

Add to `backend/app/services/auth_service.py`:

```python
PORTAL_ROLES = {
    "customer": {"customer"},
    "manager": {"client_owner", "client_admin"},
    "developer": {"platform_admin", "developer_admin"},
}


def login_for_portal(self, payload: LoginRequest, portal: AuthPortal) -> AuthResponse:
    user = self.users.get_by_login_name(payload.login_name)
    if user is None or user["status"] != 1:
        raise AuthError("INVALID_CREDENTIALS", "invalid login credentials", 401)
    if not verify_password(payload.password, user["password_hash"]):
        raise AuthError("INVALID_CREDENTIALS", "invalid login credentials", 401)
    if user["user_role"] not in PORTAL_ROLES[portal]:
        raise AuthError("PORTAL_FORBIDDEN", "account cannot access this portal", 403)
    self.users.update_last_login(user["id"])
    return self._auth_response(user, audience=portal)
```

Update `_auth_response` to add `"aud": audience` to the token payload. Keep `register` using audience `"customer"` so bootstrap-created customer accounts continue to work.

- [ ] **Step 4: Add audience verification**

Update `backend/app/core/security.py`:

Add the keyword parameter `expected_audience: str | None = None` to the existing `verify_access_token` signature.

Keep the existing format, signature, JSON, and expiry validation unchanged. Immediately after the expiry check and before the existing `return payload`, insert exactly:

```python
if expected_audience is not None and payload.get("aud") != expected_audience:
    raise InvalidTokenError("invalid token audience")
```

Update `backend/app/core/dependencies.py`:

```python
surface = request.app.state.api_surface
expected_audience = None if surface == "all" else surface
payload = verify_access_token(
    token,
    request.app.state.config.auth.token_secret,
    expected_audience=expected_audience,
)
```

- [ ] **Step 5: Expose portal-specific login**

Replace the generic login route in `backend/app/api/auth.py`:

```python
@router.post("/{portal}/login")
def login(
    portal: AuthPortal,
    payload: LoginRequest,
    request: Request,
    conn=Depends(get_db_connection),
) -> dict:
    surface = request.app.state.api_surface
    if surface != "all" and surface != portal:
        return JSONResponse(
            status_code=404,
            content=fail("PORTAL_NOT_FOUND", "login portal is unavailable"),
        )
    try:
        result = AuthService(conn, request.app.state.config).login_for_portal(
            payload,
            portal,
        )
    except AuthError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(exc.code, exc.message),
        )
    return ok(result.model_dump())
```

Add a test that starts `create_app("customer")`, posts valid manager credentials to `/api/auth/manager/login`, and asserts `404` with `error.code == "PORTAL_NOT_FOUND"`. This proves a non-bootstrap ASGI surface cannot issue another portal's token.

- [ ] **Step 6: Run auth and security tests and verify GREEN**

```powershell
python -m pytest tests/test_auth_api.py tests/test_security.py -q
```

Expected: all focused tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/schemas/auth.py backend/app/services/auth_service.py backend/app/core/dependencies.py backend/app/core/security.py backend/app/api/auth.py backend/tests/test_auth_api.py backend/tests/test_security.py
git commit -m "feat: enforce portal-specific authentication"
```

---

### Task 3: Add Tenant-Scoped Employee Persistence and Audit Fields

**Files:**
- Modify: `backend/app/db/schema.py`
- Modify: `backend/app/db/migrations.py`
- Modify: `backend/app/repositories/user_repository.py`
- Modify: `backend/app/repositories/wallet_repository.py`
- Modify: `backend/app/repositories/admin_audit_repository.py`
- Test: `backend/tests/test_database_schema.py`
- Test: `backend/tests/test_user_wallet_repositories.py`

**Interfaces:**
- Produces: `UserRepository.list_employees(tenant_id, keyword, status, offset, limit)`
- Produces: `UserRepository.count_employees(tenant_id, keyword, status)`
- Produces: `UserRepository.update_status_for_tenant(tenant_id, user_id, status)`
- Produces: `UserRepository.update_password_for_tenant(tenant_id, user_id, password_hash)`
- Produces optional `commit=False` for transaction composition
- Produces `admin_audit_log.tenant_id`

- [ ] **Step 1: Write failing schema tests**

Add to `backend/tests/test_database_schema.py`:

```python
def test_admin_audit_log_has_tenant_scope(mysql_conn):
    columns = table_columns(mysql_conn, "admin_audit_log")
    assert columns["tenant_id"]["comment"] == "所属租户 ID，平台级操作为 0"
    indexes = table_indexes(mysql_conn, "admin_audit_log")
    assert indexes["idx_admin_audit_log_tenant_time"]["columns"] == [
        "tenant_id",
        "create_time",
        "id",
    ]


def test_app_user_has_tenant_employee_listing_index(mysql_conn):
    indexes = table_indexes(mysql_conn, "app_user")
    assert indexes["idx_app_user_tenant_role_status_id"]["columns"] == [
        "tenant_id",
        "user_role",
        "status",
        "id",
    ]
```

- [ ] **Step 2: Run schema tests and verify RED**

```powershell
python -m pytest tests/test_database_schema.py -q
```

Expected: FAIL because the tenant audit column and indexes do not exist.

- [ ] **Step 3: Update canonical schema and idempotent migration**

Update `admin_audit_log` in `backend/app/db/schema.py`:

```sql
tenant_id bigint unsigned not null default 0 comment '所属租户 ID，平台级操作为 0',
key idx_admin_audit_log_tenant_time (tenant_id, create_time, id)
```

Add to `_ensure_tenant_compatibility` in `backend/app/db/migrations.py`:

```python
if not _column_exists(cursor, "admin_audit_log", "tenant_id"):
    cursor.execute(
        "alter table `admin_audit_log` "
        "add column tenant_id bigint unsigned not null default 0 "
        "comment '所属租户 ID，平台级操作为 0' after id"
    )
if not _index_exists(cursor, "admin_audit_log", "idx_admin_audit_log_tenant_time"):
    cursor.execute(
        "alter table `admin_audit_log` "
        "add key `idx_admin_audit_log_tenant_time` (tenant_id, create_time, id)"
    )
if not _index_exists(cursor, "app_user", "idx_app_user_tenant_role_status_id"):
    cursor.execute(
        "alter table `app_user` "
        "add key `idx_app_user_tenant_role_status_id` "
        "(tenant_id, user_role, status, id)"
    )
```

- [ ] **Step 4: Add tenant-scoped repository methods**

Add methods to `UserRepository` using parameterized SQL:

```python
def _employee_filters(
    self,
    tenant_id: int,
    keyword: str,
    status: int | None,
) -> tuple[str, tuple]:
    clauses = ["tenant_id = %s", "user_role = 'customer'"]
    params: list[object] = [tenant_id]
    normalized_keyword = keyword.strip()
    if normalized_keyword:
        clauses.append("(login_name like %s or nickname like %s)")
        pattern = f"%{normalized_keyword}%"
        params.extend([pattern, pattern])
    if status is not None:
        clauses.append("status = %s")
        params.append(status)
    return " and ".join(clauses), tuple(params)


def list_employees(
    self,
    tenant_id: int,
    keyword: str,
    status: int | None,
    offset: int,
    limit: int,
) -> list[dict]:
    where_sql, params = self._employee_filters(tenant_id, keyword, status)
    with self.conn.cursor() as cursor:
        cursor.execute(
            f"""
            select id, tenant_id, login_name, nickname, user_role, status,
                   last_login_time, create_time, update_time
            from app_user
            where {where_sql}
            order by id desc
            limit %s offset %s
            """,
            (*params, limit, offset),
        )
        return list(cursor.fetchall())


def count_employees(
    self,
    tenant_id: int,
    keyword: str,
    status: int | None,
) -> int:
    where_sql, params = self._employee_filters(tenant_id, keyword, status)
    with self.conn.cursor() as cursor:
        cursor.execute(
            f"select count(*) as total from app_user where {where_sql}",
            params,
        )
        return int(cursor.fetchone()["total"])


def update_status_for_tenant(
    self,
    tenant_id: int,
    user_id: int,
    status: int,
    *,
    commit: bool = True,
) -> bool:
    with self.conn.cursor() as cursor:
        affected = cursor.execute(
            """
            update app_user
            set status = %s, update_time = unix_timestamp()
            where id = %s and tenant_id = %s and user_role = 'customer'
            """,
            (status, user_id, tenant_id),
        )
    if commit:
        self.conn.commit()
    return affected == 1


def update_password_for_tenant(
    self,
    tenant_id: int,
    user_id: int,
    password_hash: str,
    *,
    commit: bool = True,
) -> bool:
    with self.conn.cursor() as cursor:
        affected = cursor.execute(
            """
            update app_user
            set password_hash = %s, update_time = unix_timestamp()
            where id = %s and tenant_id = %s and user_role = 'customer'
            """,
            (password_hash, user_id, tenant_id),
        )
    if commit:
        self.conn.commit()
    return affected == 1
```

The generated filter must always include:

```sql
tenant_id = %s and user_role = 'customer'
```

Add transaction-friendly keyword-only parameters:

- `UserRepository.create_user` keeps every current parameter and appends `*, commit: bool = True`.
- `WalletRepository.create_wallet` keeps every current parameter and appends `*, commit: bool = True`.

Keep the existing SQL bodies. In each method, replace the unconditional `self.conn.commit()` with:

```python
if commit:
    self.conn.commit()
```

Update `AdminAuditRepository.create` to require `tenant_id` and write it to the new column.

- [ ] **Step 5: Add repository behavior tests**

Add focused MySQL tests to `backend/tests/test_user_wallet_repositories.py`:

```python
def test_employee_listing_is_tenant_scoped(mysql_conn):
    users = UserRepository(mysql_conn)
    first = users.create_user("tenant_a_employee", "A", hash_password("password-a"), "customer", "", tenant_id=101)
    users.create_user("tenant_b_employee", "B", hash_password("password-b"), "customer", "", tenant_id=202)

    rows = users.list_employees(101, "", 1, 0, 20)

    assert [row["id"] for row in rows] == [first]


def test_employee_status_update_rejects_other_tenant(mysql_conn):
    users = UserRepository(mysql_conn)
    employee_id = users.create_user("tenant_b_status", "B", hash_password("password-b"), "customer", "", tenant_id=202)

    assert users.update_status_for_tenant(101, employee_id, 2) is False
```

- [ ] **Step 6: Run schema and repository tests and verify GREEN**

```powershell
python -m pytest tests/test_database_schema.py tests/test_user_wallet_repositories.py -q
```

Expected: all focused tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/db/schema.py backend/app/db/migrations.py backend/app/repositories/user_repository.py backend/app/repositories/wallet_repository.py backend/app/repositories/admin_audit_repository.py backend/tests/test_database_schema.py backend/tests/test_user_wallet_repositories.py
git commit -m "feat: add tenant-scoped employee persistence"
```

---

### Task 4: Implement Manager Employee APIs

**Files:**
- Create: `backend/app/schemas/admin_users.py`
- Create: `backend/app/services/admin_user_service.py`
- Create: `backend/app/api/admin_users.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_admin_users_api.py`

**Interfaces:**
- Produces: `GET /api/admin/users`
- Produces: `POST /api/admin/users`
- Produces: `PUT /api/admin/users/{user_id}/password`
- Produces: `PATCH /api/admin/users/{user_id}/status`
- Consumes: tenant-scoped repository methods from Task 3

- [ ] **Step 1: Write failing employee API tests**

Create `backend/tests/test_admin_users_api.py` with these core cases:

```python
def test_manager_creates_employee_that_can_login_customer_portal(
    mysql_conn,
    mysql_app_client,
):
    create_portal_user(
        mysql_conn,
        login_name="owner_create",
        password="owner-password",
        user_role="client_owner",
        tenant_id=101,
    )
    manager_headers = login_headers(
        mysql_app_client,
        "manager",
        "owner_create",
        "owner-password",
    )
    response = mysql_app_client.post(
        "/api/admin/users",
        headers=manager_headers,
        json={
            "login_name": "new_employee",
            "nickname": "新员工",
            "password": "employee-password",
            "status": 1,
        },
    )
    assert response.status_code == 200
    employee = response.json()["data"]
    manager_me = mysql_app_client.get(
        "/api/auth/me",
        headers=manager_headers,
    ).json()["data"]
    assert employee["user_role"] == "customer"
    assert employee["tenant_id"] == manager_me["tenant_id"]
    assert "password" not in str(employee).lower()

    login = mysql_app_client.post(
        "/api/auth/customer/login",
        json={"login_name": "new_employee", "password": "employee-password"},
    )
    assert login.status_code == 200


def test_manager_cannot_create_employee_in_another_tenant(
    mysql_conn,
    mysql_app_client,
):
    create_portal_user(
        mysql_conn,
        login_name="owner_scope",
        password="owner-password",
        user_role="client_owner",
        tenant_id=101,
    )
    manager_headers = login_headers(
        mysql_app_client,
        "manager",
        "owner_scope",
        "owner-password",
    )
    response = mysql_app_client.post(
        "/api/admin/users",
        headers=manager_headers,
        json={
            "tenant_id": 999,
            "login_name": "cross_tenant",
            "nickname": "越权",
            "password": "employee-password",
            "status": 1,
        },
    )
    assert response.status_code == 422


def test_manager_can_disable_employee_and_login_is_rejected(
    mysql_conn,
    mysql_app_client,
):
    create_portal_user(
        mysql_conn,
        login_name="owner_disable",
        password="owner-password",
        user_role="client_owner",
        tenant_id=101,
    )
    manager_headers = login_headers(
        mysql_app_client,
        "manager",
        "owner_disable",
        "owner-password",
    )
    created = mysql_app_client.post(
        "/api/admin/users",
        headers=manager_headers,
        json={
            "login_name": "employee_disable",
            "nickname": "待停用员工",
            "password": "employee-password",
            "status": 1,
        },
    ).json()["data"]
    response = mysql_app_client.patch(
        f"/api/admin/users/{created['id']}/status",
        headers=manager_headers,
        json={"status": 2},
    )
    assert response.status_code == 200
    login = mysql_app_client.post(
        "/api/auth/customer/login",
        json={
            "login_name": created["login_name"],
            "password": "employee-password",
        },
    )
    assert login.status_code == 401
```

In the same file, add these exact boundary cases:

| Test name | Request | Required assertion |
|---|---|---|
| `test_create_employee_rejects_duplicate_login_name` | Submit the same `login_name` twice to `POST /api/admin/users` | First response is `200`; second is `400` with `error.code == "USER_EXISTS"` |
| `test_create_employee_rejects_short_password` | Submit a seven-character password | Response is `422`; no `app_user` row is inserted |
| `test_employee_list_filters_keyword_and_status` | Create one enabled matching employee, one disabled matching employee, and one non-matching employee; call `GET /api/admin/users?keyword=match&status=1&page=1&page_size=20` | Response contains only the enabled matching employee and reports `total == 1` |
| `test_password_reset_rejects_employee_from_other_tenant` | Call `PUT /api/admin/users/{other_tenant_user_id}/password` | Response is `404` with `error.code == "EMPLOYEE_NOT_FOUND"` |
| `test_client_admin_can_manage_employees` | Authenticate as `client_admin`, then call list and create | Both responses are `200` |
| `test_customer_cannot_manage_employees` | Call all four employee endpoints with a customer token | Every response is `403` |

Define local test helpers in `test_admin_users_api.py` rather than adding global fixtures:

```python
def create_portal_user(
    mysql_conn,
    *,
    login_name: str,
    password: str,
    user_role: str,
    tenant_id: int,
) -> int:
    return UserRepository(mysql_conn).create_user(
        login_name=login_name,
        nickname=login_name,
        password_hash=hash_password(password),
        user_role=user_role,
        invite_code="",
        tenant_id=tenant_id,
    )


def login_headers(mysql_app_client, portal: str, login_name: str, password: str) -> dict[str, str]:
    response = mysql_app_client.post(
        f"/api/auth/{portal}/login",
        json={"login_name": login_name, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}
```

Build `manager_headers`, `customer_headers`, and tenant employees inside each test from these helpers so tenant IDs and roles remain explicit.

- [ ] **Step 2: Run the new tests and verify RED**

```powershell
python -m pytest tests/test_admin_users_api.py -q
```

Expected: FAIL because the schemas, service, and routes do not exist.

- [ ] **Step 3: Define request and response schemas**

Create `backend/app/schemas/admin_users.py`:

```python
from pydantic import BaseModel, Field


class AdminEmployeeCreate(BaseModel):
    login_name: str = Field(min_length=3, max_length=100)
    nickname: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    status: int = Field(default=1, ge=1, le=2)


class AdminEmployeePasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class AdminEmployeeStatusUpdate(BaseModel):
    status: int = Field(ge=1, le=2)


class AdminEmployeeView(BaseModel):
    id: int
    tenant_id: int
    login_name: str
    nickname: str
    user_role: str
    status: int
    wallet_balance: int
    last_login_time: int
    create_time: int
    update_time: int
```

- [ ] **Step 4: Implement the transaction-safe service**

Create `backend/app/services/admin_user_service.py`:

```python
class AdminUserService:
    def __init__(self, conn) -> None:
        self.conn = conn
        self.users = UserRepository(conn)
        self.wallets = WalletRepository(conn)
        self.audit = AdminAuditRepository(conn)

    def create_employee(self, manager: dict, payload: AdminEmployeeCreate) -> dict:
        if self.users.get_by_login_name(payload.login_name) is not None:
            raise AdminUserError("USER_EXISTS", "登录账号已存在", 400)
        try:
            user_id = self.users.create_user(
                login_name=payload.login_name,
                nickname=payload.nickname,
                password_hash=hash_password(payload.password),
                user_role="customer",
                invite_code="",
                tenant_id=manager["tenant_id"],
                commit=False,
            )
            self.wallets.create_wallet(
                user_id,
                initial_credits=0,
                reason="管理员创建员工",
                commit=False,
            )
            self.audit.create(
                tenant_id=manager["tenant_id"],
                admin_user_id=manager["id"],
                action="employee.create",
                target_type="app_user",
                target_id=user_id,
                detail={"login_name": payload.login_name, "status": payload.status},
                commit=False,
            )
            if payload.status == 2:
                self.users.update_status_for_tenant(
                    manager["tenant_id"],
                    user_id,
                    2,
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_employee(manager, user_id)
```

Password values and password hashes must never enter audit details.

- [ ] **Step 5: Add the admin router**

Create `backend/app/api/admin_users.py` with `require_management_user` on every route:

```python
router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


@router.post("")
def create_employee(
    payload: AdminEmployeeCreate,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(AdminUserService(conn).create_employee(manager, payload))
    except AdminUserError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(exc.code, exc.message),
        )


@router.get("")
def list_employees(
    keyword: str = "",
    status: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        AdminUserService(conn).list_employees(
            manager,
            keyword=keyword,
            status=status,
            page=page,
            page_size=page_size,
        )
    )


@router.put("/{user_id}/password")
def reset_employee_password(
    user_id: int,
    payload: AdminEmployeePasswordReset,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(AdminUserService(conn).reset_password(manager, user_id, payload))


@router.patch("/{user_id}/status")
def update_employee_status(
    user_id: int,
    payload: AdminEmployeeStatusUpdate,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(AdminUserService(conn).update_status(manager, user_id, payload))
```

For all service methods:

- derive `tenant_id` exclusively from `manager["tenant_id"]`;
- query or update only users with `user_role = 'customer'`;
- raise `AdminUserError("EMPLOYEE_NOT_FOUND", "员工不存在", 404)` when a tenant-scoped target is absent;
- write audit actions `employee.password_reset` and `employee.status_update`;
- store only target ID, new status, and non-secret metadata in audit details;
- commit the business update and audit row in one transaction, rolling back on every exception.

Register `admin_users_router` only in manager and all surfaces.

- [ ] **Step 6: Run API tests and verify GREEN**

```powershell
python -m pytest tests/test_admin_users_api.py tests/test_auth_api.py -q
```

Expected: all focused tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/schemas/admin_users.py backend/app/services/admin_user_service.py backend/app/api/admin_users.py backend/app/main.py backend/tests/test_admin_users_api.py
git commit -m "feat: add manager employee administration API"
```

---

### Task 5: Add Three Independent Frontend Build Entries

**Files:**
- Create: `apps/desktop/manager.html`
- Create: `apps/desktop/src/renderer/manager-main.tsx`
- Create: `apps/desktop/src/renderer/ManagerApp.tsx`
- Modify: `apps/desktop/vite.config.ts`
- Modify: `apps/desktop/package.json`
- Test: `apps/desktop/src/renderer/test/BuildEntries.test.ts`

**Interfaces:**
- Produces: `npm run dev` for customer
- Produces: `npm run dev:manager` for manager
- Produces: `npm run dev:developer` for developer
- Produces: `npm run build:customer`, `build:manager`, `build:developer`

- [ ] **Step 1: Write the failing build-entry test**

Create `apps/desktop/src/renderer/test/BuildEntries.test.ts`:

```typescript
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("portal build entries", () => {
  it.each([
    ["index.html", "/src/renderer/main.tsx"],
    ["manager.html", "/src/renderer/manager-main.tsx"],
    ["developer.html", "/src/renderer/developer-main.tsx"]
  ])("%s loads only its own renderer entry", (fileName, expectedEntry) => {
    const html = readFileSync(resolve(process.cwd(), fileName), "utf8");
    expect(html).toContain(expectedEntry);
    expect((html.match(/<script type="module"/g) ?? []).length).toBe(1);
  });
});
```

- [ ] **Step 2: Run the entry test and verify RED**

```powershell
npm.cmd test -- src/renderer/test/BuildEntries.test.ts
```

Expected: FAIL because `manager.html` does not exist.

- [ ] **Step 3: Add the manager entry**

Create `apps/desktop/manager.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>禾一斯运营管理中心</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/renderer/manager-main.tsx"></script>
  </body>
</html>
```

Create `apps/desktop/src/renderer/manager-main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ManagerApp } from "./ManagerApp";
import "./styles.css";

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <ManagerApp />
  </StrictMode>
);
```

Create `apps/desktop/src/renderer/ManagerApp.tsx` with a build-safe loading gate. Task 8 replaces this body with authentication and the manager shell:

```tsx
export function ManagerApp() {
  return (
    <main className="portal-loading" aria-label="管理端正在加载">
      正在加载管理端...
    </main>
  );
}
```

- [ ] **Step 4: Make Vite mode-driven**

Use an explicit map in `vite.config.ts`:

```typescript
const portalBuilds = {
  customer: { input: "index.html", outDir: "dist/customer-renderer" },
  manager: { input: "manager.html", outDir: "dist/manager-renderer" },
  developer: { input: "developer.html", outDir: "dist/developer-renderer" }
} as const;

const portal = mode === "manager" || mode === "developer" ? mode : "customer";
const portalBuild = portalBuilds[portal];
```

Update scripts in `package.json`:

```json
{
  "dev": "vite --mode customer --host 127.0.0.1",
  "dev:manager": "vite --mode manager --host 127.0.0.1",
  "dev:developer": "vite --mode developer --host 127.0.0.1",
  "build": "npm run build:customer",
  "build:customer": "vite build --mode customer && tsc -p tsconfig.main.json",
  "build:manager": "vite build --mode manager",
  "build:developer": "vite build --mode developer"
}
```

- [ ] **Step 5: Run tests and all three builds**

```powershell
npm.cmd test -- src/renderer/test/BuildEntries.test.ts
npm.cmd run build:customer
npm.cmd run build:manager
npm.cmd run build:developer
```

Expected: entry test and all builds PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/desktop/manager.html apps/desktop/src/renderer/manager-main.tsx apps/desktop/src/renderer/ManagerApp.tsx apps/desktop/vite.config.ts apps/desktop/package.json apps/desktop/src/renderer/test/BuildEntries.test.ts
git commit -m "feat: add independent manager frontend build"
```

---

### Task 6: Create Portal Auth Clients and Login Experiences

**Files:**
- Create: `apps/desktop/src/renderer/auth/portalSession.ts`
- Create: `apps/desktop/src/renderer/api/httpClient.ts`
- Create: `apps/desktop/src/renderer/components/PortalLoginPage.tsx`
- Modify: `apps/desktop/src/renderer/api/client.ts`
- Modify: `apps/desktop/src/renderer/api/developerClient.ts`
- Create: `apps/desktop/src/renderer/api/managerClient.ts`
- Modify: `apps/desktop/src/renderer/types.ts`
- Modify: `apps/desktop/src/renderer/styles.css`
- Test: `apps/desktop/src/renderer/test/PortalLoginPage.test.tsx`
- Test: `apps/desktop/src/renderer/test/apiClients.test.ts`

**Interfaces:**
- Produces: `Portal = "customer" | "manager" | "developer"`
- Produces: `tokenKey(portal)`
- Produces: `createPortalRequest(portal)`
- Produces: `PortalLoginPage`
- Produces: `customerApi.login`, `managerApi.login`, `developerApi.login`

- [ ] **Step 1: Write failing portal-auth tests**

Create `PortalLoginPage.test.tsx`:

```tsx
it("renders manager-specific copy without customer registration", () => {
  render(
    <PortalLoginPage
      portal="manager"
      error=""
      isSubmitting={false}
      onSubmit={vi.fn()}
    />
  );
  expect(screen.getByRole("heading", { name: "管理端登录" })).toBeInTheDocument();
  expect(screen.getByText("禾一斯运营管理中心")).toBeInTheDocument();
  expect(screen.queryByText(/注册/)).not.toBeInTheDocument();
});
```

Create `apiClients.test.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from "vitest";

import { customerApi } from "../api/client";
import { developerApi } from "../api/developerClient";
import { managerApi } from "../api/managerClient";

const clients = {
  customer: customerApi,
  manager: managerApi,
  developer: developerApi
} as const;

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

beforeEach(() => {
  fetchMock.mockReset();
  localStorage.clear();
});

it.each([
  ["customer", "/api/auth/customer/login", "karries_customer_access_token"],
  ["manager", "/api/auth/manager/login", "karries_manager_access_token"],
  ["developer", "/api/auth/developer/login", "karries_developer_access_token"]
  ] as const
)("uses the %s portal login contract", async (portal, path, storageKey) => {
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({
      success: true,
      data: {
        access_token: "portal-token",
        token_type: "bearer",
        expires_in: 3600,
        user: {
          id: 1,
          tenant_id: 101,
          login_name: "operator",
          nickname: "Operator",
          user_role:
            portal === "customer"
              ? "customer"
              : portal === "manager"
                ? "client_owner"
                : "developer_admin",
          wallet_balance: 0
        }
      },
      error: null
    })
  });

  await clients[portal].login({
    login_name: "operator",
    password: "test-password"
  });

  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining(path),
    expect.objectContaining({ method: "POST" })
  );
  expect(localStorage.getItem(storageKey)).toBe("portal-token");
});
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
npm.cmd test -- src/renderer/test/PortalLoginPage.test.tsx src/renderer/test/apiClients.test.ts
```

Expected: FAIL because portal auth modules do not exist.

- [ ] **Step 3: Add portal session storage**

Create `auth/portalSession.ts`:

```typescript
export type Portal = "customer" | "manager" | "developer";

const tokenKeys: Record<Portal, string> = {
  customer: "karries_customer_access_token",
  manager: "karries_manager_access_token",
  developer: "karries_developer_access_token"
};

export function tokenKey(portal: Portal) {
  return tokenKeys[portal];
}

export function clearPortalToken(portal: Portal) {
  window.localStorage.removeItem(tokenKey(portal));
}

export function setPortalToken(portal: Portal, token: string) {
  window.localStorage.setItem(tokenKey(portal), token);
}
```

This is a temporary local-development session mechanism. The later production-hardening plan replaces it with secure cookies without changing page contracts.

- [ ] **Step 4: Extract a portal-aware request factory**

Create `api/httpClient.ts`:

```typescript
export function createPortalRequest(portal: Portal) {
  return async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const token = window.localStorage.getItem(tokenKey(portal));
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {})
      }
    });
    const body = (await response.json()) as ApiResponse<T>;
    if (!response.ok || !body.success) {
      throw new ApiRequestError(
        body.error?.message || "请求未完成",
        body.error?.code || "REQUEST_FAILED",
        response.status
      );
    }
    return body.data;
  };
}
```

Create one request instance per portal:

```typescript
const customerRequest = createPortalRequest("customer");
const managerRequest = createPortalRequest("manager");
const developerRequest = createPortalRequest("developer");
```

Implement each login method with the corresponding endpoint and token key:

```typescript
async function loginForPortal(
  portal: Portal,
  request: ReturnType<typeof createPortalRequest>,
  payload: LoginRequest,
) {
  const result = await request<AuthResponse>(`/api/auth/${portal}/login`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
  setPortalToken(portal, result.access_token);
  return result;
}
```

Export `customerApi` from `client.ts`, `managerApi` from `managerClient.ts`, and `developerApi` from `developerClient.ts`. Each API object must use only its matching request instance for login, `/api/auth/me`, and business methods.

- [ ] **Step 5: Build a configurable login page**

Create `PortalLoginPage.tsx` with portal-specific content:

```typescript
const portalCopy = {
  customer: {
    title: "账号登录",
    product: "小红书智能运营工作台",
    description: "禾一斯员工工作入口"
  },
  manager: {
    title: "管理端登录",
    product: "禾一斯运营管理中心",
    description: "老板与管理层专属入口"
  },
  developer: {
    title: "内部系统登录",
    product: "点绘环球技术运营中心",
    description: "内部管理员专用入口"
  }
} satisfies Record<Portal, PortalCopy>;
```

The component must expose only account, password, submit, error, and loading state. It must not include registration.

- [ ] **Step 6: Run portal-auth tests and verify GREEN**

```powershell
npm.cmd test -- src/renderer/test/PortalLoginPage.test.tsx src/renderer/test/apiClients.test.ts
npm.cmd run typecheck
```

Expected: tests and typecheck PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/desktop/src/renderer/auth/portalSession.ts apps/desktop/src/renderer/api/httpClient.ts apps/desktop/src/renderer/components/PortalLoginPage.tsx apps/desktop/src/renderer/api/client.ts apps/desktop/src/renderer/api/developerClient.ts apps/desktop/src/renderer/api/managerClient.ts apps/desktop/src/renderer/types.ts apps/desktop/src/renderer/styles.css apps/desktop/src/renderer/test/PortalLoginPage.test.tsx apps/desktop/src/renderer/test/apiClients.test.ts
git commit -m "feat: add isolated portal login clients"
```

---

### Task 7: Separate the Customer Application and Add Logout

**Files:**
- Modify: `apps/desktop/src/renderer/App.tsx`
- Modify: `apps/desktop/src/renderer/components/AppShell.tsx`
- Modify: `apps/desktop/src/renderer/components/PortalLoginPage.tsx`
- Modify: `apps/desktop/src/renderer/test/App.test.tsx`

**Interfaces:**
- Consumes: `customerApi.login`, `customerApi.getCurrentUser`
- Produces: customer-only navigation
- Produces: `onLogout()`

- [ ] **Step 1: Write failing customer isolation tests**

Add to `App.test.tsx`:

```tsx
it("does not render a manager portal switch or manager pages", async () => {
  render(<App />);
  await screen.findByRole("button", { name: "智能创作" });
  expect(screen.queryByText("管理端")).not.toBeInTheDocument();
  expect(screen.queryByText("运营总览")).not.toBeInTheDocument();
});


it("logs out and returns to the customer login page", async () => {
  localStorage.setItem("karries_customer_access_token", "customer-token");
  render(<App />);
  await screen.findByRole("button", { name: "账号菜单" });
  fireEvent.click(screen.getByRole("button", { name: "账号菜单" }));
  fireEvent.click(screen.getByRole("button", { name: "退出登录" }));
  expect(await screen.findByRole("heading", { name: "账号登录" })).toBeInTheDocument();
  expect(localStorage.getItem("karries_customer_access_token")).toBeNull();
});
```

- [ ] **Step 2: Run App tests and verify RED**

```powershell
npm.cmd test -- src/renderer/test/App.test.tsx
```

Expected: FAIL because App still contains portal switching and AppShell has no logout menu.

- [ ] **Step 3: Remove manager state from customer App**

Delete from `App.tsx`:

- `activePortal`
- `allowedPortals`
- `handlePortalChange`
- manager page imports and manager page branches

Keep only customer pages and customer role validation:

```typescript
function isCustomerRole(user: AuthUser | null) {
  return user?.user_role === "customer";
}
```

Use `PortalLoginPage portal="customer"` and `customerApi`.

- [ ] **Step 4: Simplify AppShell and add logout**

Make `AppShell` customer-only and replace the portal switcher with the product identity. Use this navigation order for the current available pages:

```typescript
const navigation = [
  { key: "create", label: "智能创作", icon: Sparkles },
  { key: "viralAnalysis", label: "爆款解析", icon: ScanSearch },
  { key: "inspiration", label: "小禾助手", icon: Lightbulb },
  { key: "schedule", label: "定时发布", icon: Clock3 },
  { key: "settings", label: "账号管理", icon: Settings }
] as const;
```

The product-knowledge entry is added in the content workspace plan when its production page is connected.

Add an account menu containing:

```tsx
<button type="button" onClick={onLogout}>
  <LogOut size={16} aria-hidden="true" />
  退出登录
</button>
```

- [ ] **Step 5: Run customer tests and verify GREEN**

```powershell
npm.cmd test -- src/renderer/test/App.test.tsx
npm.cmd run typecheck
```

Expected: customer tests and typecheck PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/desktop/src/renderer/App.tsx apps/desktop/src/renderer/components/AppShell.tsx apps/desktop/src/renderer/components/PortalLoginPage.tsx apps/desktop/src/renderer/test/App.test.tsx
git commit -m "feat: isolate customer application navigation"
```

---

### Task 8: Build the Independent Manager Application

**Files:**
- Create: `apps/desktop/src/renderer/components/ManagerShell.tsx`
- Create: `apps/desktop/src/renderer/pages/ManagerUsersPage.tsx`
- Modify: `apps/desktop/src/renderer/ManagerApp.tsx`
- Modify: `apps/desktop/src/renderer/pages/ManagerOverviewPage.tsx`
- Modify: `apps/desktop/src/renderer/pages/ManagerInspirationPage.tsx`
- Modify: `apps/desktop/src/renderer/pages/ManagerViralAnalysisPage.tsx`
- Modify: `apps/desktop/src/renderer/styles.css`
- Create: `apps/desktop/src/renderer/test/ManagerApp.test.tsx`

**Interfaces:**
- Consumes: `managerApi.login`, `managerApi.getCurrentUser`, employee APIs
- Produces: manager-only navigation and login
- Produces: employee list, create, status, and password reset UI

- [ ] **Step 1: Write failing ManagerApp tests**

Create `ManagerApp.test.tsx`:

```tsx
it("shows the independent manager login when no manager token exists", async () => {
  mockedManagerApi.getCurrentUser.mockRejectedValue(
    new ApiRequestError("missing bearer token", "UNAUTHORIZED", 401)
  );
  render(<ManagerApp />);
  expect(await screen.findByRole("heading", { name: "管理端登录" })).toBeInTheDocument();
  expect(screen.queryByText("智能创作")).not.toBeInTheDocument();
});


it("creates an employee from member management", async () => {
  render(<ManagerApp />);
  fireEvent.click(await screen.findByRole("button", { name: "成员与权限" }));
  fireEvent.click(screen.getByRole("button", { name: "新增员工" }));
  fireEvent.change(screen.getByLabelText("登录账号"), {
    target: { value: "new_employee" }
  });
  fireEvent.change(screen.getByLabelText("员工姓名"), {
    target: { value: "新员工" }
  });
  fireEvent.change(screen.getByLabelText("长期密码"), {
    target: { value: "employee-password" }
  });
  fireEvent.click(screen.getByRole("button", { name: "确认新增" }));
  await waitFor(() => {
    expect(mockedManagerApi.createEmployee).toHaveBeenCalledWith({
      login_name: "new_employee",
      nickname: "新员工",
      password: "employee-password",
      status: 1
    });
  });
});
```

Add these UI tests to the same file:

| Test name | Interaction | Required assertion |
|---|---|---|
| `rejects_a_customer_role_from_manager_app` | Resolve `getCurrentUser` with `user_role: "customer"` | Manager token is cleared and `当前账号没有管理端访问权限` is shown |
| `logs_out_to_manager_login` | Open `管理账号菜单`, click `退出登录` | Only the manager token is cleared and `管理端登录` is shown |
| `disables_an_employee_after_confirmation` | Click the enabled row's `停用`, then `确认停用` | `managerApi.updateEmployeeStatus(id, 2)` is called once and the list reloads |
| `resets_an_employee_password_without_echoing_it` | Open `重置密码`, enter a valid value, and confirm | `managerApi.resetEmployeePassword(id, { password })` is called; the dialog closes and the password does not appear in the page |
| `does_not_render_customer_or_developer_navigation` | Render an authenticated manager | `智能创作`, `开发者工作台`, and `租户管理` are absent |

Mock the authenticated manager in all success-path tests as:

```typescript
mockedManagerApi.getCurrentUser.mockResolvedValue({
  id: 11,
  tenant_id: 101,
  login_name: "owner",
  nickname: "禾一斯负责人",
  user_role: "client_owner",
  wallet_balance: 0
});
```

- [ ] **Step 2: Run manager tests and verify RED**

```powershell
npm.cmd test -- src/renderer/test/ManagerApp.test.tsx
```

Expected: FAIL because the manager shell and user page do not exist.

- [ ] **Step 3: Build ManagerShell**

Manager navigation for this foundation:

```typescript
export type ManagerPageKey =
  | "overview"
  | "users"
  | "inspiration"
  | "viralAnalysis";

const navigation = [
  { key: "overview", label: "运营总览", icon: LayoutDashboard },
  { key: "users", label: "成员与权限", icon: UsersRound },
  { key: "inspiration", label: "小禾记录", icon: MessageSquareText },
  { key: "viralAnalysis", label: "爆款解析记录", icon: ScanSearch }
] as const;
```

Use a manager-specific header and account menu. Do not reuse the customer sidebar.

- [ ] **Step 4: Implement ManagerUsersPage**

The page has:

- employee table
- keyword and status filters
- new employee dialog
- reset password dialog
- enable/disable confirmation
- loading, empty, success, and error states

Submit exactly this create payload:

```typescript
type AdminEmployeeCreate = {
  login_name: string;
  nickname: string;
  password: string;
  status: 1 | 2;
};
```

Never display an existing password or password hash. Clear password fields after success or dialog close.

- [ ] **Step 5: Wire ManagerApp auth and pages**

`ManagerApp` must:

1. Check only the manager token.
2. Render `PortalLoginPage portal="manager"` on `401`.
3. Reject any role other than `client_owner` or `client_admin`.
4. Load pages through `managerApi`.
5. Clear manager token and return to manager login on logout.

- [ ] **Step 6: Run manager tests, full frontend tests, and builds**

```powershell
npm.cmd test -- src/renderer/test/ManagerApp.test.tsx
npm.cmd test
npm.cmd run typecheck
npm.cmd run build:customer
npm.cmd run build:manager
npm.cmd run build:developer
```

Expected: all tests, typecheck, and all builds PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/desktop/src/renderer/components/ManagerShell.tsx apps/desktop/src/renderer/pages/ManagerUsersPage.tsx apps/desktop/src/renderer/ManagerApp.tsx apps/desktop/src/renderer/pages/ManagerOverviewPage.tsx apps/desktop/src/renderer/pages/ManagerInspirationPage.tsx apps/desktop/src/renderer/pages/ManagerViralAnalysisPage.tsx apps/desktop/src/renderer/styles.css apps/desktop/src/renderer/test/ManagerApp.test.tsx
git commit -m "feat: add independent manager application"
```

---

### Task 9: Add Developer Login and Final Cross-Portal Verification

**Files:**
- Modify: `apps/desktop/src/renderer/DeveloperApp.tsx`
- Modify: `apps/desktop/src/renderer/components/DeveloperShell.tsx`
- Modify: `apps/desktop/src/renderer/test/DeveloperApp.test.tsx`
- Modify: `backend/app/core/dependencies.py`
- Modify: `backend/app/api/ai.py`
- Modify: `backend/app/api/content_drafts.py`
- Modify: `backend/app/api/inspiration.py`
- Modify: `backend/app/api/matrix_plans.py`
- Modify: `backend/app/api/products.py`
- Modify: `backend/app/api/video_edit.py`
- Modify: `backend/app/api/viral_analysis.py`
- Modify: `backend/app/api/wallet.py`
- Modify: `backend/app/api/xhs_accounts.py`
- Create: `backend/tests/test_portal_isolation_api.py`
- Modify: `docs/superpowers/specs/2026-07-24-three-portal-content-ai-redesign-design.md`

**Interfaces:**
- Consumes: `developerApi.login`, developer token storage
- Produces: a login page and logout for the internal developer app
- Verifies all three portal role and route boundaries

- [ ] **Step 1: Write failing developer login and isolation tests**

Add to `DeveloperApp.test.tsx`:

```tsx
it("shows the internal login page for an unauthenticated developer", async () => {
  mockedDeveloperApi.getCurrentUser.mockRejectedValue(
    new ApiRequestError("missing bearer token", "UNAUTHORIZED", 401)
  );
  render(<DeveloperApp />);
  expect(await screen.findByRole("heading", { name: "内部系统登录" })).toBeInTheDocument();
});


it("logs out without exposing a customer or manager page", async () => {
  render(<DeveloperApp />);
  fireEvent.click(await screen.findByRole("button", { name: "开发者账号菜单" }));
  fireEvent.click(screen.getByRole("button", { name: "退出登录" }));
  expect(await screen.findByRole("heading", { name: "内部系统登录" })).toBeInTheDocument();
  expect(screen.queryByText("智能创作")).not.toBeInTheDocument();
  expect(screen.queryByText("成员与权限")).not.toBeInTheDocument();
});
```

Create `backend/tests/test_portal_isolation_api.py`:

```python
def test_customer_token_cannot_call_manager_api(
    mysql_app_client,
    customer_headers,
):
    response = mysql_app_client.get("/api/admin/users", headers=customer_headers)
    assert response.status_code == 403


def test_manager_token_cannot_call_developer_api(
    mysql_app_client,
    manager_headers,
):
    response = mysql_app_client.get(
        "/api/developer/viral-analysis/jobs",
        headers=manager_headers,
    )
    assert response.status_code == 403


def test_developer_token_cannot_call_customer_api(
    mysql_app_client,
    developer_headers,
):
    response = mysql_app_client.get(
        "/api/inspiration/sessions",
        headers=developer_headers,
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Run the new tests and verify RED**

```powershell
python -m pytest tests/test_portal_isolation_api.py -q
npm.cmd test -- src/renderer/test/DeveloperApp.test.tsx
```

Expected: tests expose missing developer login/logout and any remaining route-role gaps.

- [ ] **Step 3: Add developer login and logout**

Use `PortalLoginPage portal="developer"`, `developerApi.login`, and the developer token key. Add a real account menu to `DeveloperShell` with `退出登录`.

On wrong portal role:

```typescript
clearPortalToken("developer");
setAuthError("当前账号没有开发者端访问权限");
setAuthState("error");
```

- [ ] **Step 4: Close backend route-role gaps**

Every customer route rejects internal roles through a new `require_customer_user` dependency. Every manager route uses `require_management_user`. Every developer route uses `require_developer_user`.

Define:

```python
def require_customer_user(user: dict = Depends(current_user)) -> dict:
    if user["user_role"] != "customer":
        raise HTTPException(status_code=403, detail="customer role required")
    return user
```

Replace `Depends(current_user)` with `Depends(require_customer_user)` and update imports in these customer API files:

```text
backend/app/api/ai.py
backend/app/api/content_drafts.py
backend/app/api/inspiration.py
backend/app/api/matrix_plans.py
backend/app/api/products.py
backend/app/api/video_edit.py
backend/app/api/viral_analysis.py
backend/app/api/wallet.py
backend/app/api/xhs_accounts.py
```

In `video_edit.py`, change only the customer-facing dependencies; keep existing `require_developer_user` dependencies unchanged. Verify no generic dependency remains:

```powershell
rg -n "Depends\\(current_user\\)" app/api
```

Expected: no matches.

- [ ] **Step 5: Run complete verification**

Backend:

```powershell
python -m pytest tests -q
```

Frontend:

```powershell
npm.cmd test
npm.cmd run typecheck
npm.cmd run build:customer
npm.cmd run build:manager
npm.cmd run build:developer
```

Expected:

- backend suite PASS
- frontend suite PASS
- typecheck PASS
- all three builds PASS

- [ ] **Step 6: Run three local frontends**

Use available ports, preferring:

```text
customer: 127.0.0.1:5175
manager: 127.0.0.1:5176
developer: 127.0.0.1:5177
backend: 127.0.0.1:8765
```

Verify manually:

1. Manager creates an employee.
2. Employee logs into customer.
3. Employee cannot log into manager.
4. Manager cannot log into customer.
5. Developer cannot log into either customer portal.
6. Each logout returns to its own login page.

- [ ] **Step 7: Update the design status**

In `2026-07-24-three-portal-content-ai-redesign-design.md`, append an implementation status section:

```markdown
## Implementation Status

- Three independent applications and login pages: completed
- Manager employee provisioning: completed
- Customer registration UI and public registration surface: removed
- Production secure-cookie migration: scheduled in the production-hardening batch
```

- [ ] **Step 8: Commit**

```powershell
git add apps/desktop/src/renderer/DeveloperApp.tsx apps/desktop/src/renderer/components/DeveloperShell.tsx apps/desktop/src/renderer/test/DeveloperApp.test.tsx backend/tests/test_portal_isolation_api.py backend/app/core/dependencies.py backend/app/api/ai.py backend/app/api/content_drafts.py backend/app/api/inspiration.py backend/app/api/matrix_plans.py backend/app/api/products.py backend/app/api/video_edit.py backend/app/api/viral_analysis.py backend/app/api/wallet.py backend/app/api/xhs_accounts.py docs/superpowers/specs/2026-07-24-three-portal-content-ai-redesign-design.md
git commit -m "feat: complete three-portal authentication foundation"
```
