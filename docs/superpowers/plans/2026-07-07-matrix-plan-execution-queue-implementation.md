# Matrix Plan Execution Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend execution queue that moves confirmed matrix plans into worker-claimable publish items and records worker execution results.

**Architecture:** Extend the existing FastAPI + repository pattern. User routes stay in `backend/app/api/matrix_plans.py`; worker-only routes live in a new `backend/app/api/worker_matrix_publish.py` router protected by `X-Worker-Token`. `MatrixPlanRepository` owns all MySQL reads, transactions, status transitions, JSON parsing, and worker item claiming with row locks.

**Tech Stack:** Python 3.10+, FastAPI 0.115.6, Pydantic 2.10.4, PyMySQL 1.1.1, MySQL 8.0, pytest 8.3.4.

## Global Constraints

- User detail endpoint: `GET /api/matrix-plans/{plan_id}`.
- User item list endpoint: `GET /api/matrix-plans/{plan_id}/items`.
- User confirm endpoint: `POST /api/matrix-plans/{plan_id}/confirm`.
- User cancel endpoint: `POST /api/matrix-plans/{plan_id}/cancel`.
- Worker claim endpoint: `POST /api/worker/matrix-publish-items/claim`.
- Worker success endpoint: `POST /api/worker/matrix-publish-items/{item_id}/success`.
- Worker fail endpoint: `POST /api/worker/matrix-publish-items/{item_id}/fail`.
- Worker manual takeover endpoint: `POST /api/worker/matrix-publish-items/{item_id}/manual-takeover`.
- Worker auth uses header `X-Worker-Token`.
- Worker token config key is `worker_api_token`, read from environment variable `WORKER_API_TOKEN`.
- If `WORKER_API_TOKEN` is empty, worker endpoints return HTTP 503 with error code `SERVICE_UNAVAILABLE`.
- If worker token is missing or wrong, worker endpoints return HTTP 401 with error code `UNAUTHORIZED`.
- `matrix_publish_plan.status`: `1` draft, `2` pending confirm, `3` pending auto submit, `4` submitting, `5` complete, `6` failed, `7` cancelled.
- `matrix_publish_item.status`: `1` pending confirm, `2` pending auto submit, `3` submitting, `4` submitted, `5` failed, `6` manual takeover, `7` cancelled.
- Confirm plan only allows plan `status = 2`, requires at least one item, requires every item `status = 1`, and requires every item title/body to be non-empty.
- Confirm plan sets plan `2 -> 3` and items `1 -> 2` in one transaction.
- Cancel plan only allows plan `status in (1, 2, 3)`.
- Cancel plan fails if any item already has `status = 3`.
- Cancel plan sets plan `status = 7` and items with `status in (1, 2)` to `7`.
- Worker claim only returns item `status = 2`, item `scheduled_time <= now_time`, parent plan `status in (3, 4)`, and `xhs_account.status = 1`.
- Worker claim sets claimed items to `status = 3` and parent plans to `status = 4`.
- Worker success only accepts item `status = 3`, sets item to `4`, and sets parent plan to `5` when all non-cancelled items are complete.
- Worker fail only accepts item `status = 3`, sets item to `5`, writes `last_error`, and sets parent plan to `6`.
- Worker manual takeover only accepts item `status = 3`, sets item to `6`, writes `last_error`, and sets parent plan to `6`.
- Do not use or mutate old `publish_task` / `account` tables for this SaaS execution queue.
- Do not implement real Xiaohongshu browser automation in this phase.
- Do not implement credit deduction in this phase.
- Keep existing unrelated frontend, emergency demo, and older dirty files untouched.

---

## File Structure

- Modify `backend/app/core/config.py`: add `worker_api_token` to `AppConfig` and `default_config()`.
- Modify `backend/app/core/dependencies.py`: add `verify_worker_token()` dependency.
- Modify `backend/app/schemas/matrix_plan.py`: add response and worker request schemas.
- Modify `backend/app/repositories/matrix_plan_repository.py`: add user plan actions, item listing, worker claim, worker result methods, and status refresh helpers.
- Modify `backend/app/api/matrix_plans.py`: add user detail, item list, confirm, and cancel routes.
- Create `backend/app/api/worker_matrix_publish.py`: worker claim and worker result routes.
- Modify `backend/app/main.py`: include the worker router.
- Modify `backend/app/db/schema.py`: update matrix plan/item status comments to include status `7`.
- Create `backend/tests/test_matrix_plan_execution_queue_api.py`: user-side route and repository coverage.
- Create `backend/tests/test_worker_matrix_publish_api.py`: worker token, claim, and result coverage.
- Modify `backend/tests/test_mysql_config.py`: assert `WORKER_API_TOKEN` config behavior.

---

### Task 1: Config And Schemas

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/dependencies.py`
- Modify: `backend/app/schemas/matrix_plan.py`
- Modify: `backend/tests/test_mysql_config.py`
- Create: `backend/tests/test_worker_matrix_publish_api.py`

**Interfaces:**
- Produces: `AppConfig.worker_api_token: str`.
- Produces: `verify_worker_token(request: Request, x_worker_token: str = Header(default="")) -> None`.
- Produces schema classes:
  - `MatrixPlanActionResult`
  - `MatrixPlanItemDetail`
  - `WorkerClaimRequest`
  - `WorkerClaimResponse`
  - `WorkerClaimedItem`
  - `WorkerItemSuccessRequest`
  - `WorkerItemFailRequest`
  - `WorkerItemManualTakeoverRequest`

- [ ] **Step 1: Write failing config and worker-auth tests**

Append to `backend/tests/test_mysql_config.py`:

```python
def test_default_config_reads_worker_api_token(monkeypatch):
    monkeypatch.setenv("WORKER_API_TOKEN", "worker-secret")

    from app.core.config import default_config

    config = default_config()

    assert config.worker_api_token == "worker-secret"
```

Create `backend/tests/test_worker_matrix_publish_api.py`:

```python
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from app.core.responses import fail, ok


def test_worker_token_dependency_returns_503_when_not_configured():
    from app.core.dependencies import verify_worker_token

    app = FastAPI()
    app.state.config = type("Config", (), {"worker_api_token": ""})()

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request, exc):
        code = "SERVICE_UNAVAILABLE" if exc.status_code == 503 else "UNAUTHORIZED"
        return JSONResponse(status_code=exc.status_code, content=fail(code, str(exc.detail)))

    @app.get("/probe")
    def probe(_auth=Depends(verify_worker_token)):
        return ok({"ready": True})

    response = TestClient(app).get("/probe", headers={"X-Worker-Token": "abc"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend/tests/test_mysql_config.py::test_default_config_reads_worker_api_token backend/tests/test_worker_matrix_publish_api.py::test_worker_token_dependency_returns_503_when_not_configured -q
```

Expected: FAIL because `worker_api_token` and `verify_worker_token` do not exist.

- [ ] **Step 3: Add worker config**

Edit `backend/app/core/config.py`:

```python
class AppConfig(BaseModel):
    environment: str
    app_root: Path
    data_dir: Path
    log_dir: Path
    runtime_dir: Path
    mysql: MysqlConfig
    auth: AuthConfig
    worker_api_token: str
```

Add to the `AppConfig(...)` construction:

```python
worker_api_token=os.environ.get("WORKER_API_TOKEN", ""),
```

- [ ] **Step 4: Add worker token dependency**

Add this dependency before `current_user = get_current_user`:

```python
def verify_worker_token(
    request: Request,
    x_worker_token: str = Header(default="", alias="X-Worker-Token"),
) -> None:
    configured_token = request.app.state.config.worker_api_token
    if not configured_token:
        raise HTTPException(status_code=503, detail="worker api token is not configured")
    if not x_worker_token or x_worker_token != configured_token:
        raise HTTPException(status_code=401, detail="invalid worker token")
```

Task 3 updates the app-wide HTTP exception handler so production worker routes map 503 to `SERVICE_UNAVAILABLE`.

- [ ] **Step 5: Add matrix plan and worker schemas**

Edit `backend/app/schemas/matrix_plan.py` and add:

```python
class MatrixPlanActionResult(BaseModel):
    id: int
    status: int
    item_count: int = 0
    cancelled_item_count: int = 0


class MatrixPlanDetail(BaseModel):
    id: int
    user_id: int
    plan_name: str
    source_type: str
    content_type: str
    product_id: int
    status: int
    schedule_start_time: int
    schedule_end_time: int
    scheduling_rule: dict
    item_count: int
    create_time: int
    update_time: int


class MatrixPlanItemDetail(BaseModel):
    id: int
    plan_id: int
    xhs_account_id: int
    content_type: str
    title: str
    body: str
    tags: list[str]
    material: dict
    scheduled_time: int
    status: int
    last_error: str
    create_time: int
    update_time: int


class WorkerClaimRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)
    now_time: int | None = Field(default=None, ge=0)


class WorkerClaimedItem(BaseModel):
    id: int
    plan_id: int
    user_id: int
    xhs_account_id: int
    login_state_path: str
    content_type: str
    title: str
    body: str
    tags: list[str]
    material: dict
    scheduled_time: int


class WorkerClaimResponse(BaseModel):
    items: list[WorkerClaimedItem]


class WorkerItemSuccessRequest(BaseModel):
    message: str = Field(default="", max_length=1000)


class WorkerItemFailRequest(BaseModel):
    error_message: str = Field(min_length=1, max_length=1000)


class WorkerItemManualTakeoverRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
```

- [ ] **Step 6: Run Task 1 tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend/tests/test_mysql_config.py backend/tests/test_worker_matrix_publish_api.py -q
```

Expected: PASS for the new config/auth tests.

- [ ] **Step 7: Commit Task 1**

Run:

```powershell
git add backend/app/core/config.py backend/app/core/dependencies.py backend/app/schemas/matrix_plan.py backend/tests/test_mysql_config.py backend/tests/test_worker_matrix_publish_api.py
git commit -m "feat: add worker queue config and schemas"
```

---

### Task 2: User Plan Detail, Items, Confirm, And Cancel

**Files:**
- Modify: `backend/app/repositories/matrix_plan_repository.py`
- Modify: `backend/app/api/matrix_plans.py`
- Create: `backend/tests/test_matrix_plan_execution_queue_api.py`

**Interfaces:**
- Produces: `MatrixPlanRepository.list_items_for_plan(user_id: int, plan_id: int) -> list[dict] | None`.
- Produces: `MatrixPlanRepository.confirm_plan(user_id: int, plan_id: int) -> dict | None`.
- Produces: `MatrixPlanRepository.cancel_plan(user_id: int, plan_id: int) -> dict | None`.
- Produces routes:
  - `GET /api/matrix-plans/{plan_id}`
  - `GET /api/matrix-plans/{plan_id}/items`
  - `POST /api/matrix-plans/{plan_id}/confirm`
  - `POST /api/matrix-plans/{plan_id}/cancel`

- [ ] **Step 1: Write failing user route tests**

Create `backend/tests/test_matrix_plan_execution_queue_api.py` with helper registration and this focused fake-repository test:

```python
import json


def test_confirm_matrix_plan_returns_validation_error_when_status_is_invalid(monkeypatch):
    from app.api import matrix_plans as matrix_plans_api

    class FakeRepository:
        def __init__(self, _conn):
            pass

        def confirm_plan(self, user_id, plan_id):
            assert user_id == 5
            assert plan_id == 12
            return {"error": "plan status does not allow confirmation"}

    monkeypatch.setattr(matrix_plans_api, "MatrixPlanRepository", FakeRepository)

    response = matrix_plans_api.confirm_matrix_plan(
        plan_id=12,
        user={"id": 5},
        conn=object(),
    )

    assert response.status_code == 400
    assert json.loads(response.body)["error"]["code"] == "VALIDATION_ERROR"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend/tests/test_matrix_plan_execution_queue_api.py::test_confirm_matrix_plan_returns_validation_error_when_status_is_invalid -q
```

Expected: FAIL because `confirm_matrix_plan` does not exist.

- [ ] **Step 3: Add repository item row mapping**

Edit `backend/app/repositories/matrix_plan_repository.py` and add helper methods near `_row_to_plan()`:

```python
    def _row_to_item(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "plan_id": row["plan_id"],
            "user_id": row["user_id"],
            "xhs_account_id": row["xhs_account_id"],
            "content_type": row["content_type"],
            "title": row["title"],
            "body": row["body"],
            "tags": self._load_json_list(row["tag_json"]),
            "material": self._load_json_dict(row["material_json"]),
            "scheduled_time": row["scheduled_time"],
            "status": row["status"],
            "last_error": row["last_error"],
            "create_time": row["create_time"],
            "update_time": row["update_time"],
        }

    def _load_json_list(self, raw_value: str) -> list:
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return []
        return parsed if isinstance(parsed, list) else []
```

- [ ] **Step 4: Add repository user methods**

Add to `MatrixPlanRepository`:

```python
    def list_items_for_plan(self, user_id: int, plan_id: int) -> list[dict] | None:
        if self.get_plan_for_user(user_id, plan_id) is None:
            return None
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, plan_id, user_id, xhs_account_id, content_type,
                       title, body, tag_json, material_json, scheduled_time,
                       status, last_error, create_time, update_time
                from matrix_publish_item
                where user_id = %s and plan_id = %s
                order by scheduled_time asc, id asc
                """,
                (user_id, plan_id),
            )
            return [self._row_to_item(row) for row in cursor.fetchall()]
```

Add `confirm_plan()`:

```python
    def confirm_plan(self, user_id: int, plan_id: int) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "select id, status from matrix_publish_plan where user_id = %s and id = %s for update",
                    (user_id, plan_id),
                )
                plan = cursor.fetchone()
                if plan is None:
                    return None
                if int(plan["status"]) != 2:
                    return {"error": "plan status does not allow confirmation"}

                cursor.execute(
                    """
                    select id, title, body, status
                    from matrix_publish_item
                    where user_id = %s and plan_id = %s
                    for update
                    """,
                    (user_id, plan_id),
                )
                rows = cursor.fetchall()
                if not rows:
                    return {"error": "plan has no publish items"}
                if any(int(row["status"]) != 1 for row in rows):
                    return {"error": "publish items are not all pending confirmation"}
                if any(not str(row["title"]).strip() or not str(row["body"]).strip() for row in rows):
                    return {"error": "publish item title and body are required"}

                cursor.execute(
                    "update matrix_publish_plan set status = 3, update_time = %s where id = %s",
                    (now, plan_id),
                )
                cursor.execute(
                    """
                    update matrix_publish_item
                    set status = 2, update_time = %s
                    where user_id = %s and plan_id = %s and status = 1
                    """,
                    (now, user_id, plan_id),
                )
                item_count = cursor.rowcount
            self.conn.commit()
            return {"id": plan_id, "status": 3, "item_count": item_count}
        except Exception:
            self.conn.rollback()
            raise
```

Add `cancel_plan()`:

```python
    def cancel_plan(self, user_id: int, plan_id: int) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "select id, status from matrix_publish_plan where user_id = %s and id = %s for update",
                    (user_id, plan_id),
                )
                plan = cursor.fetchone()
                if plan is None:
                    return None
                if int(plan["status"]) not in {1, 2, 3}:
                    return {"error": "plan status does not allow cancellation"}

                cursor.execute(
                    """
                    select id, status
                    from matrix_publish_item
                    where user_id = %s and plan_id = %s
                    for update
                    """,
                    (user_id, plan_id),
                )
                item_rows = cursor.fetchall()
                if any(int(row["status"]) == 3 for row in item_rows):
                    return {"error": "plan has items already submitting"}

                cursor.execute(
                    "update matrix_publish_plan set status = 7, update_time = %s where id = %s",
                    (now, plan_id),
                )
                cursor.execute(
                    """
                    update matrix_publish_item
                    set status = 7, update_time = %s
                    where user_id = %s and plan_id = %s and status in (1, 2)
                    """,
                    (now, user_id, plan_id),
                )
                cancelled_item_count = cursor.rowcount
            self.conn.commit()
            return {"id": plan_id, "status": 7, "cancelled_item_count": cancelled_item_count}
        except Exception:
            self.conn.rollback()
            raise
```

- [ ] **Step 5: Add user API routes**

Edit `backend/app/api/matrix_plans.py`. Add after `list_matrix_plans()` or before it while keeping `/from-drafts` above `/{plan_id}`:

```python
@router.get("/{plan_id}")
def get_matrix_plan(
    plan_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = MatrixPlanRepository(conn)
    plan = repo.get_plan_for_user(user["id"], plan_id)
    if plan is None:
        return _not_found("matrix plan not found")
    return ok(plan)


@router.get("/{plan_id}/items")
def list_matrix_plan_items(
    plan_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = MatrixPlanRepository(conn)
    items = repo.list_items_for_plan(user["id"], plan_id)
    if items is None:
        return _not_found("matrix plan not found")
    return ok(items)


@router.post("/{plan_id}/confirm")
def confirm_matrix_plan(
    plan_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    result = MatrixPlanRepository(conn).confirm_plan(user["id"], plan_id)
    if result is None:
        return _not_found("matrix plan not found")
    if "error" in result:
        return _validation_error(result["error"])
    return ok(result)


@router.post("/{plan_id}/cancel")
def cancel_matrix_plan(
    plan_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    result = MatrixPlanRepository(conn).cancel_plan(user["id"], plan_id)
    if result is None:
        return _not_found("matrix plan not found")
    if "error" in result:
        return _validation_error(result["error"])
    return ok(result)
```

- [ ] **Step 6: Add MySQL user flow tests**

In `backend/tests/test_matrix_plan_execution_queue_api.py`, add helpers copied from `test_matrix_plan_from_drafts_api.py` only as needed, then add:

```python
def test_confirm_plan_moves_items_to_pending_auto_submit(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "confirm-flow")
    account_id = create_xhs_account(mysql_app_client, headers, "confirm-flow")
    product_id = create_product(mysql_app_client, headers, "confirm-flow")
    draft_id = create_confirmed_draft(mysql_app_client, headers, product_id, account_id)
    plan_id = create_plan_from_drafts(mysql_app_client, headers, draft_id, account_id)

    response = mysql_app_client.post(f"/api/matrix-plans/{plan_id}/confirm", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["status"] == 3
    assert response.json()["data"]["item_count"] == 1
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 3
        cursor.execute("select status from matrix_publish_item where plan_id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 2
```

Also add tests for:

```python
def test_get_plan_items_are_sorted_by_schedule_time(mysql_conn, mysql_app_client):
    ...
```

and:

```python
def test_cancel_plan_marks_pending_items_cancelled(mysql_conn, mysql_app_client):
    ...
```

Use direct SQL updates inside tests to create the needed status and schedule ordering after API setup.

- [ ] **Step 7: Run Task 2 tests**

Run:

```powershell
$env:MYSQL_TEST_HOST='127.0.0.1'; $env:MYSQL_TEST_PORT='3306'; $env:MYSQL_TEST_DATABASE='xhs_publisher_test'; $env:MYSQL_TEST_USER='root'; $env:MYSQL_TEST_PASSWORD='123456'; .\.venv\Scripts\python -m pytest backend/tests/test_matrix_plan_execution_queue_api.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

Run:

```powershell
git add backend/app/repositories/matrix_plan_repository.py backend/app/api/matrix_plans.py backend/tests/test_matrix_plan_execution_queue_api.py
git commit -m "feat: add matrix plan user execution actions"
```

---

### Task 3: Worker Claim API

**Files:**
- Modify: `backend/app/repositories/matrix_plan_repository.py`
- Create: `backend/app/api/worker_matrix_publish.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_worker_matrix_publish_api.py`

**Interfaces:**
- Produces: `MatrixPlanRepository.claim_due_items(limit: int, now_time: int) -> list[dict]`.
- Produces: `POST /api/worker/matrix-publish-items/claim`.

- [ ] **Step 1: Write failing worker claim route test**

Append to `backend/tests/test_worker_matrix_publish_api.py`:

```python
def test_worker_claim_requires_valid_token(app_client_without_db):
    app_client_without_db.app.state.config.worker_api_token = "secret"

    response = app_client_without_db.post(
        "/api/worker/matrix-publish-items/claim",
        json={"limit": 1, "now_time": 1_700_000_000},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
```

- [ ] **Step 2: Run the worker claim auth test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend/tests/test_worker_matrix_publish_api.py::test_worker_claim_requires_valid_token -q
```

Expected: FAIL because the route is not registered.

- [ ] **Step 3: Add repository claim method**

Add to `MatrixPlanRepository`:

```python
    def claim_due_items(self, limit: int, now_time: int) -> list[dict]:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select
                        i.id, i.plan_id, i.user_id, i.xhs_account_id,
                        a.login_state_path,
                        i.content_type, i.title, i.body, i.tag_json,
                        i.material_json, i.scheduled_time
                    from matrix_publish_item i
                    join matrix_publish_plan p on p.id = i.plan_id
                    join xhs_account a on a.id = i.xhs_account_id and a.user_id = i.user_id
                    where i.status = 2
                      and i.scheduled_time <= %s
                      and p.status in (3, 4)
                      and a.status = 1
                    order by i.scheduled_time asc, i.id asc
                    limit %s
                    for update skip locked
                    """,
                    (now_time, limit),
                )
                rows = cursor.fetchall()
                if not rows:
                    self.conn.commit()
                    return []
                item_ids = [row["id"] for row in rows]
                plan_ids = sorted({row["plan_id"] for row in rows})
                item_placeholders = ", ".join(["%s"] * len(item_ids))
                plan_placeholders = ", ".join(["%s"] * len(plan_ids))
                cursor.execute(
                    f"update matrix_publish_item set status = 3, update_time = %s where id in ({item_placeholders})",
                    (now, *item_ids),
                )
                cursor.execute(
                    f"update matrix_publish_plan set status = 4, update_time = %s where id in ({plan_placeholders})",
                    (now, *plan_ids),
                )
            self.conn.commit()
            return [self._row_to_claimed_item(row) for row in rows]
        except Exception:
            self.conn.rollback()
            raise
```

Add helper:

```python
    def _row_to_claimed_item(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "plan_id": row["plan_id"],
            "user_id": row["user_id"],
            "xhs_account_id": row["xhs_account_id"],
            "login_state_path": row["login_state_path"],
            "content_type": row["content_type"],
            "title": row["title"],
            "body": row["body"],
            "tags": self._load_json_list(row["tag_json"]),
            "material": self._load_json_dict(row["material_json"]),
            "scheduled_time": row["scheduled_time"],
        }
```

- [ ] **Step 4: Add worker router and register it**

Create `backend/app/api/worker_matrix_publish.py`:

```python
import time

from fastapi import APIRouter, Depends

from app.core.dependencies import get_db_connection, verify_worker_token
from app.core.responses import ok
from app.repositories.matrix_plan_repository import MatrixPlanRepository
from app.schemas.matrix_plan import WorkerClaimRequest


router = APIRouter(
    prefix="/api/worker/matrix-publish-items",
    tags=["worker-matrix-publish"],
    dependencies=[Depends(verify_worker_token)],
)


@router.post("/claim")
def claim_matrix_publish_items(
    payload: WorkerClaimRequest,
    conn=Depends(get_db_connection),
) -> dict:
    now_time = payload.now_time if payload.now_time is not None else int(time.time())
    items = MatrixPlanRepository(conn).claim_due_items(payload.limit, now_time)
    return ok({"items": items})
```

Edit `backend/app/main.py`:

```python
from app.api.worker_matrix_publish import router as worker_matrix_publish_router
```

and include:

```python
app.include_router(worker_matrix_publish_router)
```

Update HTTP exception handler so status 503 maps to `SERVICE_UNAVAILABLE`:

```python
elif exc.status_code == 503:
    code = "SERVICE_UNAVAILABLE"
```

- [ ] **Step 5: Add MySQL claim test**

Append to `backend/tests/test_worker_matrix_publish_api.py`:

```python
def test_worker_claim_due_items_marks_items_submitting(mysql_conn, mysql_app_client):
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"
    headers = auth_headers(mysql_conn, mysql_app_client, "worker-claim")
    account_id = create_xhs_account(mysql_app_client, headers, "worker-claim")
    product_id = create_product(mysql_app_client, headers, "worker-claim")
    draft_id = create_confirmed_draft(mysql_app_client, headers, product_id, account_id)
    plan_id = create_plan_from_drafts(mysql_app_client, headers, draft_id, account_id)
    confirm = mysql_app_client.post(f"/api/matrix-plans/{plan_id}/confirm", headers=headers)
    assert confirm.status_code == 200

    response = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": 5, "now_time": 1_700_000_000},
    )

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["plan_id"] == plan_id
    assert items[0]["xhs_account_id"] == account_id
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 4
        cursor.execute("select status from matrix_publish_item where id = %s", (items[0]["id"],))
        assert cursor.fetchone()["status"] == 3
```

Use helper functions by importing them from `backend/tests/test_matrix_plan_from_drafts_api.py` if duplicated helpers become noisy:

```python
from test_matrix_plan_from_drafts_api import (
    auth_headers,
    create_confirmed_draft,
    create_product,
    create_xhs_account,
)
```

- [ ] **Step 6: Run Task 3 tests**

Run:

```powershell
$env:MYSQL_TEST_HOST='127.0.0.1'; $env:MYSQL_TEST_PORT='3306'; $env:MYSQL_TEST_DATABASE='xhs_publisher_test'; $env:MYSQL_TEST_USER='root'; $env:MYSQL_TEST_PASSWORD='123456'; .\.venv\Scripts\python -m pytest backend/tests/test_worker_matrix_publish_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

Run:

```powershell
git add backend/app/repositories/matrix_plan_repository.py backend/app/api/worker_matrix_publish.py backend/app/main.py backend/tests/test_worker_matrix_publish_api.py
git commit -m "feat: add worker matrix item claim api"
```

---

### Task 4: Worker Result APIs And Plan Status Refresh

**Files:**
- Modify: `backend/app/repositories/matrix_plan_repository.py`
- Modify: `backend/app/api/worker_matrix_publish.py`
- Modify: `backend/tests/test_worker_matrix_publish_api.py`

**Interfaces:**
- Produces: `mark_item_success(item_id: int, message: str) -> dict | None`.
- Produces: `mark_item_failed(item_id: int, error_message: str) -> dict | None`.
- Produces: `mark_item_manual_takeover(item_id: int, reason: str) -> dict | None`.
- Produces worker result routes.

- [ ] **Step 1: Write failing worker success test**

Append:

```python
def test_worker_success_marks_item_submitted_and_plan_complete(mysql_conn, mysql_app_client):
    item_id, plan_id = create_claimed_worker_item(mysql_conn, mysql_app_client, "success")

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/success",
        headers={"X-Worker-Token": "worker-secret"},
        json={"message": "submitted"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == 4
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_item where id = %s", (item_id,))
        assert cursor.fetchone()["status"] == 4
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 5
```

Create helper `create_claimed_worker_item()` in the same test file by reusing the claim flow from Task 3 and returning `(item_id, plan_id)`.

- [ ] **Step 2: Run the worker success test and verify it fails**

Run:

```powershell
$env:MYSQL_TEST_HOST='127.0.0.1'; $env:MYSQL_TEST_PORT='3306'; $env:MYSQL_TEST_DATABASE='xhs_publisher_test'; $env:MYSQL_TEST_USER='root'; $env:MYSQL_TEST_PASSWORD='123456'; .\.venv\Scripts\python -m pytest backend/tests/test_worker_matrix_publish_api.py::test_worker_success_marks_item_submitted_and_plan_complete -q
```

Expected: FAIL because success route does not exist.

- [ ] **Step 3: Add repository worker result helpers**

Add to `MatrixPlanRepository`:

```python
    def mark_item_success(self, item_id: int, message: str) -> dict | None:
        return self._mark_worker_item(item_id, target_status=4, last_error=message, plan_failure=False)

    def mark_item_failed(self, item_id: int, error_message: str) -> dict | None:
        return self._mark_worker_item(item_id, target_status=5, last_error=error_message, plan_failure=True)

    def mark_item_manual_takeover(self, item_id: int, reason: str) -> dict | None:
        return self._mark_worker_item(item_id, target_status=6, last_error=reason, plan_failure=True)
```

Add internal helper:

```python
    def _mark_worker_item(
        self,
        item_id: int,
        target_status: int,
        last_error: str,
        plan_failure: bool,
    ) -> dict | None:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, plan_id, status
                    from matrix_publish_item
                    where id = %s
                    for update
                    """,
                    (item_id,),
                )
                item = cursor.fetchone()
                if item is None:
                    return None
                if int(item["status"]) != 3:
                    return {"error": "publish item is not submitting"}

                plan_id = int(item["plan_id"])
                cursor.execute(
                    """
                    update matrix_publish_item
                    set status = %s, last_error = %s, update_time = %s
                    where id = %s
                    """,
                    (target_status, last_error, now, item_id),
                )
                if plan_failure:
                    cursor.execute(
                        "update matrix_publish_plan set status = 6, update_time = %s where id = %s",
                        (now, plan_id),
                    )
                    plan_status = 6
                else:
                    plan_status = self._refresh_plan_status_locked(cursor, plan_id, now)
            self.conn.commit()
            return {"id": item_id, "plan_id": plan_id, "status": target_status, "plan_status": plan_status}
        except Exception:
            self.conn.rollback()
            raise
```

Add status refresh helper:

```python
    def _refresh_plan_status_locked(self, cursor, plan_id: int, now: int) -> int:
        cursor.execute(
            """
            select id, status
            from matrix_publish_item
            where plan_id = %s and status <> 7
            for update
            """,
            (plan_id,),
        )
        item_rows = cursor.fetchall()
        statuses = [int(row["status"]) for row in item_rows]
        if any(status in {5, 6} for status in statuses):
            status = 6
        elif statuses and all(status == 4 for status in statuses):
            status = 5
        else:
            status = 4
        cursor.execute(
            "update matrix_publish_plan set status = %s, update_time = %s where id = %s",
            (status, now, plan_id),
        )
        return status
```

- [ ] **Step 4: Add worker result routes**

Edit `backend/app/api/worker_matrix_publish.py` imports:

```python
from fastapi.responses import JSONResponse
from app.core.responses import fail, ok
from app.schemas.matrix_plan import (
    WorkerClaimRequest,
    WorkerItemFailRequest,
    WorkerItemManualTakeoverRequest,
    WorkerItemSuccessRequest,
)
```

Add helpers:

```python
def _not_found(message: str) -> JSONResponse:
    return JSONResponse(status_code=404, content=fail("NOT_FOUND", message))


def _validation_error(message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content=fail("VALIDATION_ERROR", message))


def _worker_result_response(result: dict | None) -> dict | JSONResponse:
    if result is None:
        return _not_found("matrix publish item not found")
    if "error" in result:
        return _validation_error(result["error"])
    return ok(result)
```

Add routes:

```python
@router.post("/{item_id}/success")
def mark_matrix_publish_item_success(
    item_id: int,
    payload: WorkerItemSuccessRequest,
    conn=Depends(get_db_connection),
) -> dict | JSONResponse:
    result = MatrixPlanRepository(conn).mark_item_success(item_id, payload.message)
    return _worker_result_response(result)


@router.post("/{item_id}/fail")
def mark_matrix_publish_item_failed(
    item_id: int,
    payload: WorkerItemFailRequest,
    conn=Depends(get_db_connection),
) -> dict | JSONResponse:
    result = MatrixPlanRepository(conn).mark_item_failed(item_id, payload.error_message)
    return _worker_result_response(result)


@router.post("/{item_id}/manual-takeover")
def mark_matrix_publish_item_manual_takeover(
    item_id: int,
    payload: WorkerItemManualTakeoverRequest,
    conn=Depends(get_db_connection),
) -> dict | JSONResponse:
    result = MatrixPlanRepository(conn).mark_item_manual_takeover(item_id, payload.reason)
    return _worker_result_response(result)
```

- [ ] **Step 5: Add fail and manual takeover tests**

Append:

```python
def test_worker_fail_marks_item_failed_and_plan_failed(mysql_conn, mysql_app_client):
    item_id, plan_id = create_claimed_worker_item(mysql_conn, mysql_app_client, "fail")

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/fail",
        headers={"X-Worker-Token": "worker-secret"},
        json={"error_message": "upload failed"},
    )

    assert response.status_code == 200
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status, last_error from matrix_publish_item where id = %s", (item_id,))
        item = cursor.fetchone()
        assert item["status"] == 5
        assert item["last_error"] == "upload failed"
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 6
```

Append:

```python
def test_worker_manual_takeover_marks_item_and_plan_failed(mysql_conn, mysql_app_client):
    item_id, plan_id = create_claimed_worker_item(mysql_conn, mysql_app_client, "manual")

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/manual-takeover",
        headers={"X-Worker-Token": "worker-secret"},
        json={"reason": "login expired"},
    )

    assert response.status_code == 200
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status, last_error from matrix_publish_item where id = %s", (item_id,))
        item = cursor.fetchone()
        assert item["status"] == 6
        assert item["last_error"] == "login expired"
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 6
```

- [ ] **Step 6: Run Task 4 tests**

Run:

```powershell
$env:MYSQL_TEST_HOST='127.0.0.1'; $env:MYSQL_TEST_PORT='3306'; $env:MYSQL_TEST_DATABASE='xhs_publisher_test'; $env:MYSQL_TEST_USER='root'; $env:MYSQL_TEST_PASSWORD='123456'; .\.venv\Scripts\python -m pytest backend/tests/test_worker_matrix_publish_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

Run:

```powershell
git add backend/app/repositories/matrix_plan_repository.py backend/app/api/worker_matrix_publish.py backend/tests/test_worker_matrix_publish_api.py
git commit -m "feat: add worker matrix item result api"
```

---

### Task 5: Schema Comments And End-To-End Verification

**Files:**
- Modify: `backend/app/db/schema.py`
- Modify: `backend/tests/test_database_schema.py`
- Modify: `backend/tests/test_matrix_plan_execution_queue_api.py`
- Modify: `backend/tests/test_worker_matrix_publish_api.py`

**Interfaces:**
- Produces updated table comments that include cancelled status `7`.
- Produces one full MySQL test for `draft -> plan -> confirm -> claim -> success`.

- [ ] **Step 1: Update schema comments**

Edit `backend/app/db/schema.py` status comments:

```sql
status tinyint unsigned not null default 1 comment '状态，1-草稿，2-待确认，3-待自动提交，4-自动提交中，5-完成，6-失败，7-取消',
```

and:

```sql
status tinyint unsigned not null default 1 comment '状态，1-待确认，2-待自动提交，3-提交中，4-已提交，5-失败，6-人工接管，7-取消',
```

- [ ] **Step 2: Add schema comment test**

Append to `backend/tests/test_database_schema.py`:

```python
def test_matrix_publish_status_comments_include_cancelled_status(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select table_name, column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name in ('matrix_publish_plan', 'matrix_publish_item')
          and column_name = 'status'
        """,
    )

    comments = {row["table_name"]: row["column_comment"] for row in rows}
    assert "7-取消" in comments["matrix_publish_plan"]
    assert "7-取消" in comments["matrix_publish_item"]
```

- [ ] **Step 3: Add full queue lifecycle test**

Append to `backend/tests/test_worker_matrix_publish_api.py`:

```python
def test_full_matrix_queue_lifecycle(mysql_conn, mysql_app_client):
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"
    headers = auth_headers(mysql_conn, mysql_app_client, "full-life")
    account_id = create_xhs_account(mysql_app_client, headers, "full-life")
    product_id = create_product(mysql_app_client, headers, "full-life")
    draft_id = create_confirmed_draft(mysql_app_client, headers, product_id, account_id)
    plan_id = create_plan_from_drafts(mysql_app_client, headers, draft_id, account_id)

    detail = mysql_app_client.get(f"/api/matrix-plans/{plan_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == 2

    confirm = mysql_app_client.post(f"/api/matrix-plans/{plan_id}/confirm", headers=headers)
    assert confirm.status_code == 200

    claim = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": 1, "now_time": 1_700_000_000},
    )
    assert claim.status_code == 200
    item_id = claim.json()["data"]["items"][0]["id"]

    success = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/success",
        headers={"X-Worker-Token": "worker-secret"},
        json={"message": "submitted"},
    )
    assert success.status_code == 200

    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 5
        cursor.execute("select status from matrix_publish_item where id = %s", (item_id,))
        assert cursor.fetchone()["status"] == 4
```

- [ ] **Step 4: Run focused MySQL tests**

Run:

```powershell
$env:MYSQL_TEST_HOST='127.0.0.1'; $env:MYSQL_TEST_PORT='3306'; $env:MYSQL_TEST_DATABASE='xhs_publisher_test'; $env:MYSQL_TEST_USER='root'; $env:MYSQL_TEST_PASSWORD='123456'; .\.venv\Scripts\python -m pytest backend/tests/test_matrix_plan_execution_queue_api.py backend/tests/test_worker_matrix_publish_api.py backend/tests/test_database_schema.py -q
```

Expected: PASS.

- [ ] **Step 5: Run full backend tests**

Run:

```powershell
$env:MYSQL_TEST_HOST='127.0.0.1'; $env:MYSQL_TEST_PORT='3306'; $env:MYSQL_TEST_DATABASE='xhs_publisher_test'; $env:MYSQL_TEST_USER='root'; $env:MYSQL_TEST_PASSWORD='123456'; .\.venv\Scripts\python -m pytest backend/tests -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

Run:

```powershell
git add backend/app/db/schema.py backend/tests/test_database_schema.py backend/tests/test_matrix_plan_execution_queue_api.py backend/tests/test_worker_matrix_publish_api.py
git commit -m "test: verify matrix execution queue lifecycle"
```

---

## Self-Review

- Spec coverage: tasks cover user detail/items/confirm/cancel, worker token auth, worker claim, worker success/fail/manual takeover, state transitions, schema comments, and MySQL verification.
- Placeholder scan: this plan contains concrete file paths, command lines, method names, route paths, status values, and response shapes; it does not rely on deferred work markers.
- Type consistency: request and response class names match across schema, API, repository, and tests.
- Scope check: this plan intentionally excludes real Xiaohongshu browser automation, credit deduction, and old `publish_task` integration.
