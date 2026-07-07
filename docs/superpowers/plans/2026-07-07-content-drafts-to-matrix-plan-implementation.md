# Content Drafts To Matrix Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an authenticated backend workflow that converts confirmed AI content drafts into Xiaohongshu matrix publish plans and pending publish items.

**Architecture:** Add a focused request schema for the new workflow, reuse the existing scheduling service for cross-account timing, and keep all plan/item database writes inside one repository transaction. The API validates ownership, confirmed draft status, account ownership, and schedule range before creating the plan, and it copies draft title, body, tags, and material context into each matrix publish item.

**Tech Stack:** Python 3.10+, FastAPI 0.115.6, Pydantic 2.10.4, PyMySQL 1.1.1, MySQL 8.0, pytest 8.3.4.

## Global Constraints

- Endpoint path: `POST /api/matrix-plans/from-drafts`.
- Request fields: `plan_name`, `draft_ids`, `xhs_account_ids`, `schedule_start_time`, `schedule_end_time`, `min_interval_minutes`.
- Also accept aliases `schedule_start` and `schedule_end`.
- Only current-user owned drafts and accounts can be used.
- Every draft must have status `confirmed`.
- Duplicate `draft_ids` or `xhs_account_ids` return HTTP 400 with `VALIDATION_ERROR`.
- Invalid schedule range returns HTTP 400 with `VALIDATION_ERROR`.
- Missing or cross-user draft/account returns HTTP 404 with `NOT_FOUND`.
- New matrix plan uses status `2` pending confirmation.
- New matrix items use status `1` pending confirmation.
- Copy draft `title`, `body`, `tags`, and `material` into each matrix item.
- `material_json` must include both `draft_id` and `source_content_draft_id`.
- Success response returns `id`, `item_count`, `draft_count`, and `account_count`.
- The operation must be one database transaction and roll back both plan and items if any insert fails.
- Do not mutate rows in `content_draft`.
- Follow the existing MySQL schema style: explicit columns, comments already present, bigint timestamps, JSON stored as text/varchar JSON strings.
- Do not touch existing unrelated frontend, emergency demo, or deleted documentation files.

---

## File Structure

- Modify `backend/app/schemas/matrix_plan.py`: add `MatrixPlanFromDraftsCreate` request model next to `MatrixPlanCreate`.
- Modify `backend/app/repositories/content_draft_repository.py`: add a bulk read method that returns current-user drafts in request order.
- Modify `backend/app/repositories/matrix_plan_repository.py`: add `create_plan_from_drafts()` and small JSON helpers for item material merging.
- Modify `backend/app/api/matrix_plans.py`: add the `/from-drafts` route and validation helpers.
- Create `backend/tests/test_matrix_plan_from_drafts_api.py`: schema, API unit, repository rollback, and MySQL integration coverage.

---

### Task 1: Request Schema

**Files:**
- Modify: `backend/app/schemas/matrix_plan.py`
- Create: `backend/tests/test_matrix_plan_from_drafts_api.py`

**Interfaces:**
- Consumes: existing `MatrixPlanCreate`.
- Produces: `MatrixPlanFromDraftsCreate` with attributes `plan_name: str`, `draft_ids: list[int]`, `xhs_account_ids: list[int]`, `schedule_start_time: int`, `schedule_end_time: int`, `min_interval_minutes: int`.

- [ ] **Step 1: Write the failing schema tests**

Add this content to the new file `backend/tests/test_matrix_plan_from_drafts_api.py`:

```python
def test_matrix_plan_from_drafts_schema_accepts_schedule_aliases():
    from app.schemas.matrix_plan import MatrixPlanFromDraftsCreate

    payload = MatrixPlanFromDraftsCreate(
        plan_name="Reviewed launch plan",
        draft_ids=[21, 22],
        xhs_account_ids=[11],
        schedule_start=1_700_000_000,
        schedule_end=1_700_086_400,
    )

    assert payload.plan_name == "Reviewed launch plan"
    assert payload.draft_ids == [21, 22]
    assert payload.xhs_account_ids == [11]
    assert payload.schedule_start_time == 1_700_000_000
    assert payload.schedule_end_time == 1_700_086_400
    assert payload.min_interval_minutes == 360
```

- [ ] **Step 2: Run the schema test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend/tests/test_matrix_plan_from_drafts_api.py::test_matrix_plan_from_drafts_schema_accepts_schedule_aliases -q
```

Expected: FAIL with an import error for `MatrixPlanFromDraftsCreate`.

- [ ] **Step 3: Add the request model**

Edit `backend/app/schemas/matrix_plan.py` so the imports stay Pydantic v2 compatible and the file contains this new class after `MatrixPlanCreate`:

```python
class MatrixPlanFromDraftsCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    plan_name: str = Field(min_length=1, max_length=200)
    draft_ids: list[int] = Field(min_length=1, max_length=50)
    xhs_account_ids: list[int] = Field(min_length=1, max_length=100)
    schedule_start_time: int = Field(
        validation_alias=AliasChoices("schedule_start_time", "schedule_start"),
        ge=0,
    )
    schedule_end_time: int = Field(
        validation_alias=AliasChoices("schedule_end_time", "schedule_end"),
        ge=0,
    )
    min_interval_minutes: int = Field(default=360, ge=1, le=1440)
```

- [ ] **Step 4: Run the schema test and verify it passes**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend/tests/test_matrix_plan_from_drafts_api.py::test_matrix_plan_from_drafts_schema_accepts_schedule_aliases -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add backend/app/schemas/matrix_plan.py backend/tests/test_matrix_plan_from_drafts_api.py
git commit -m "feat: add draft matrix plan schema"
```

---

### Task 2: Repository Support

**Files:**
- Modify: `backend/app/repositories/content_draft_repository.py`
- Modify: `backend/app/repositories/matrix_plan_repository.py`
- Modify: `backend/tests/test_matrix_plan_from_drafts_api.py`

**Interfaces:**
- Consumes: `MatrixPlanFromDraftsCreate` from Task 1.
- Produces: `ContentDraftRepository.list_for_user_by_ids(user_id: int, draft_ids: list[int]) -> list[dict]`.
- Produces: `MatrixPlanRepository.create_plan_from_drafts(user_id: int, payload: MatrixPlanFromDraftsCreate, drafts: list[dict], draft_schedule: list[tuple[int, int, int]]) -> tuple[int, int]`.
- `draft_schedule` tuple order is `(xhs_account_id, draft_id, scheduled_time)`.

- [ ] **Step 1: Add repository rollback test**

Append this test and fake classes to `backend/tests/test_matrix_plan_from_drafts_api.py`:

```python
class FakeDraftMatrixCursor:
    def __init__(self, conn):
        self.conn = conn
        self.lastrowid = 0

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def execute(self, sql, _params=()):
        normalized = " ".join(sql.lower().split())
        self.conn.statements.append(normalized)
        if normalized.startswith("insert into matrix_publish_plan"):
            self.lastrowid = 88
        elif normalized.startswith("insert into matrix_publish_item"):
            raise RuntimeError("draft item insert failed")

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class FakeDraftMatrixConnection:
    def __init__(self):
        self.statements = []
        self.commit_count = 0
        self.rollback_count = 0

    def cursor(self):
        return FakeDraftMatrixCursor(self)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def test_create_plan_from_drafts_rolls_back_when_item_insert_fails():
    import pytest

    from app.repositories.matrix_plan_repository import MatrixPlanRepository
    from app.schemas.matrix_plan import MatrixPlanFromDraftsCreate

    conn = FakeDraftMatrixConnection()
    payload = MatrixPlanFromDraftsCreate(
        plan_name="Rollback from drafts",
        draft_ids=[31],
        xhs_account_ids=[11],
        schedule_start_time=1_700_000_000,
        schedule_end_time=1_700_086_400,
    )
    drafts = [
        {
            "id": 31,
            "product_id": 7,
            "content_type": "image_text",
            "title": "Reviewed title",
            "body": "Reviewed body",
            "tags": ["#reviewed"],
            "material": {"product_id": 7},
        }
    ]

    with pytest.raises(RuntimeError, match="draft item insert failed"):
        MatrixPlanRepository(conn).create_plan_from_drafts(
            user_id=5,
            payload=payload,
            drafts=drafts,
            draft_schedule=[(11, 31, 1_700_000_000)],
        )

    assert conn.commit_count == 0
    assert conn.rollback_count == 1
    assert any("insert into matrix_publish_plan" in statement for statement in conn.statements)
    assert any("insert into matrix_publish_item" in statement for statement in conn.statements)
```

- [ ] **Step 2: Run the repository test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend/tests/test_matrix_plan_from_drafts_api.py::test_create_plan_from_drafts_rolls_back_when_item_insert_fails -q
```

Expected: FAIL with an attribute error for `create_plan_from_drafts`.

- [ ] **Step 3: Add content draft bulk read**

Add this method to `ContentDraftRepository` before `update_for_user()` in `backend/app/repositories/content_draft_repository.py`:

```python
    def list_for_user_by_ids(self, user_id: int, draft_ids: list[int]) -> list[dict]:
        if not draft_ids:
            return []

        placeholders = ", ".join(["%s"] * len(draft_ids))
        with self.conn.cursor() as cursor:
            cursor.execute(
                self._select_sql()
                + f"""
                where user_id = %s and id in ({placeholders})
                """,
                (user_id, *draft_ids),
            )
            rows = cursor.fetchall()

        drafts_by_id = {int(row["id"]): self._row_to_draft(row) for row in rows}
        return [drafts_by_id[draft_id] for draft_id in draft_ids if draft_id in drafts_by_id]
```

- [ ] **Step 4: Add matrix plan creation from drafts**

Edit `backend/app/repositories/matrix_plan_repository.py`:

1. Change the import to:

```python
from app.schemas.matrix_plan import MatrixPlanCreate, MatrixPlanFromDraftsCreate
```

2. Add this method after `create_plan()`:

```python
    def create_plan_from_drafts(
        self,
        user_id: int,
        payload: MatrixPlanFromDraftsCreate,
        drafts: list[dict],
        draft_schedule: list[tuple[int, int, int]],
    ) -> tuple[int, int]:
        now = int(time.time())
        drafts_by_id = {int(draft["id"]): draft for draft in drafts}
        scheduling_rule = {
            "source": "content_draft",
            "draft_ids": payload.draft_ids,
            "xhs_account_ids": payload.xhs_account_ids,
            "items_per_account": len(payload.draft_ids),
            "min_interval_minutes": payload.min_interval_minutes,
        }

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into matrix_publish_plan (
                        user_id, plan_name, source_type, content_type, product_id,
                        status, schedule_start_time, schedule_end_time,
                        scheduling_rule_json, create_time, update_time
                    )
                    values (%s, %s, 'content_draft', 'image_text', 0, 2, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        payload.plan_name,
                        payload.schedule_start_time,
                        payload.schedule_end_time,
                        self._dump_json(scheduling_rule),
                        now,
                        now,
                    ),
                )
                plan_id = int(cursor.lastrowid)
                for account_id, draft_id, scheduled_time in draft_schedule:
                    draft = drafts_by_id[draft_id]
                    material = self._draft_item_material(draft, account_id)
                    cursor.execute(
                        """
                        insert into matrix_publish_item (
                            plan_id, user_id, xhs_account_id, content_type,
                            title, body, tag_json, material_json, scheduled_time,
                            status, last_error, create_time, update_time
                        )
                        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, '', %s, %s)
                        """,
                        (
                            plan_id,
                            user_id,
                            account_id,
                            draft["content_type"],
                            draft["title"],
                            draft["body"],
                            self._dump_json(draft["tags"]),
                            self._dump_json(material),
                            scheduled_time,
                            now,
                            now,
                        ),
                    )
            self.conn.commit()
            return plan_id, len(draft_schedule)
        except Exception:
            self.conn.rollback()
            raise
```

3. Add this helper near `_dump_json()`:

```python
    def _draft_item_material(self, draft: dict, account_id: int) -> dict:
        material = dict(draft.get("material") or {})
        material["draft_id"] = draft["id"]
        material["source_content_draft_id"] = draft["id"]
        material["source_product_id"] = draft["product_id"]
        material["target_xhs_account_id"] = account_id
        return material
```

- [ ] **Step 5: Run the repository test and verify it passes**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend/tests/test_matrix_plan_from_drafts_api.py::test_create_plan_from_drafts_rolls_back_when_item_insert_fails -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add backend/app/repositories/content_draft_repository.py backend/app/repositories/matrix_plan_repository.py backend/tests/test_matrix_plan_from_drafts_api.py
git commit -m "feat: add draft matrix plan repositories"
```

---

### Task 3: API Route And Validation

**Files:**
- Modify: `backend/app/api/matrix_plans.py`
- Modify: `backend/tests/test_matrix_plan_from_drafts_api.py`

**Interfaces:**
- Consumes: `MatrixPlanFromDraftsCreate`, `ContentDraftRepository.list_for_user_by_ids()`, `MatrixPlanRepository.create_plan_from_drafts()`, `generate_schedule_times()`.
- Produces: `POST /api/matrix-plans/from-drafts` returning `ok({"id": plan_id, "item_count": item_count, "draft_count": len(payload.draft_ids), "account_count": len(payload.xhs_account_ids)})`.

- [ ] **Step 1: Add API validation tests**

Append these tests to `backend/tests/test_matrix_plan_from_drafts_api.py`:

```python
import json


def test_create_matrix_plan_from_drafts_rejects_duplicate_draft_ids(monkeypatch):
    from app.api import matrix_plans as matrix_plans_api
    from app.schemas.matrix_plan import MatrixPlanFromDraftsCreate

    class FakeRepository:
        def __init__(self, _conn):
            pass

        def validate_accounts_for_user(self, *_args):
            raise AssertionError("account validation should not run")

    monkeypatch.setattr(matrix_plans_api, "MatrixPlanRepository", FakeRepository)

    response = matrix_plans_api.create_matrix_plan_from_drafts(
        payload=MatrixPlanFromDraftsCreate(
            plan_name="Duplicate drafts",
            draft_ids=[31, 31],
            xhs_account_ids=[11],
            schedule_start_time=1_700_000_000,
            schedule_end_time=1_700_086_400,
        ),
        user={"id": 5},
        conn=object(),
    )

    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_create_matrix_plan_from_drafts_rejects_unconfirmed_drafts(monkeypatch):
    from app.api import matrix_plans as matrix_plans_api
    from app.schemas.matrix_plan import MatrixPlanFromDraftsCreate

    class FakeMatrixRepository:
        def __init__(self, _conn):
            pass

        def validate_accounts_for_user(self, user_id, account_ids):
            assert user_id == 5
            assert account_ids == [11]
            return True

        def create_plan_from_drafts(self, *_args, **_kwargs):
            raise AssertionError("plan should not be created from draft status")

    class FakeDraftRepository:
        def __init__(self, _conn):
            pass

        def list_for_user_by_ids(self, user_id, draft_ids):
            assert user_id == 5
            assert draft_ids == [31]
            return [
                {
                    "id": 31,
                    "status": "draft",
                    "product_id": 7,
                    "content_type": "image_text",
                    "title": "Draft title",
                    "body": "Draft body",
                    "tags": [],
                    "material": {},
                }
            ]

    monkeypatch.setattr(matrix_plans_api, "MatrixPlanRepository", FakeMatrixRepository)
    monkeypatch.setattr(matrix_plans_api, "ContentDraftRepository", FakeDraftRepository)

    response = matrix_plans_api.create_matrix_plan_from_drafts(
        payload=MatrixPlanFromDraftsCreate(
            plan_name="Unconfirmed drafts",
            draft_ids=[31],
            xhs_account_ids=[11],
            schedule_start_time=1_700_000_000,
            schedule_end_time=1_700_086_400,
        ),
        user={"id": 5},
        conn=object(),
    )

    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["error"]["code"] == "VALIDATION_ERROR"
```

- [ ] **Step 2: Run the API validation tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend/tests/test_matrix_plan_from_drafts_api.py::test_create_matrix_plan_from_drafts_rejects_duplicate_draft_ids backend/tests/test_matrix_plan_from_drafts_api.py::test_create_matrix_plan_from_drafts_rejects_unconfirmed_drafts -q
```

Expected: FAIL with an attribute error for `create_matrix_plan_from_drafts`.

- [ ] **Step 3: Add route imports and helper**

Edit `backend/app/api/matrix_plans.py` imports:

```python
from app.repositories.content_draft_repository import ContentDraftRepository
from app.repositories.matrix_plan_repository import MatrixPlanRepository
from app.schemas.matrix_plan import MatrixPlanCreate, MatrixPlanFromDraftsCreate
```

Add this helper above `_not_found()`:

```python
def _has_duplicates(values: list[int]) -> bool:
    return len(values) != len(set(values))
```

- [ ] **Step 4: Add the API route**

Add this route before `@router.get("")` in `backend/app/api/matrix_plans.py`:

```python
@router.post("/from-drafts")
def create_matrix_plan_from_drafts(
    payload: MatrixPlanFromDraftsCreate,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    if _has_duplicates(payload.draft_ids):
        return _validation_error("draft_ids must not contain duplicate IDs")
    if _has_duplicates(payload.xhs_account_ids):
        return _validation_error("xhs_account_ids must not contain duplicate IDs")
    if payload.schedule_start_time > payload.schedule_end_time:
        return _validation_error("schedule start must be before end")

    plan_repo = MatrixPlanRepository(conn)
    if not plan_repo.validate_accounts_for_user(user["id"], payload.xhs_account_ids):
        return _not_found("xhs account not found")

    draft_repo = ContentDraftRepository(conn)
    drafts = draft_repo.list_for_user_by_ids(user["id"], payload.draft_ids)
    if len(drafts) != len(payload.draft_ids):
        return _not_found("content draft not found")
    if any(draft["status"] != "confirmed" for draft in drafts):
        return _validation_error("content draft must be confirmed")

    try:
        schedule = generate_schedule_times(
            account_ids=payload.xhs_account_ids,
            schedule_start_time=payload.schedule_start_time,
            schedule_end_time=payload.schedule_end_time,
            items_per_account=len(payload.draft_ids),
            min_interval_minutes=payload.min_interval_minutes,
        )
    except ValueError as exc:
        return _validation_error(str(exc))

    draft_schedule = _pair_drafts_with_schedule(payload.draft_ids, schedule)
    plan_id, item_count = plan_repo.create_plan_from_drafts(
        user["id"],
        payload,
        drafts,
        draft_schedule,
    )
    return ok(
        {
            "id": plan_id,
            "item_count": item_count,
            "draft_count": len(payload.draft_ids),
            "account_count": len(payload.xhs_account_ids),
        }
    )
```

Add this helper above `_has_duplicates()`:

```python
def _pair_drafts_with_schedule(
    draft_ids: list[int],
    schedule: list[tuple[int, int]],
) -> list[tuple[int, int, int]]:
    paired: list[tuple[int, int, int]] = []
    for index, (account_id, scheduled_time) in enumerate(schedule):
        draft_id = draft_ids[index % len(draft_ids)]
        paired.append((account_id, draft_id, scheduled_time))
    return paired
```

- [ ] **Step 5: Run the API validation tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend/tests/test_matrix_plan_from_drafts_api.py::test_create_matrix_plan_from_drafts_rejects_duplicate_draft_ids backend/tests/test_matrix_plan_from_drafts_api.py::test_create_matrix_plan_from_drafts_rejects_unconfirmed_drafts -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add backend/app/api/matrix_plans.py backend/tests/test_matrix_plan_from_drafts_api.py
git commit -m "feat: add draft matrix plan api"
```

---

### Task 4: End-To-End MySQL Coverage

**Files:**
- Modify: `backend/tests/test_matrix_plan_from_drafts_api.py`

**Interfaces:**
- Consumes: the API route from Task 3.
- Produces: a MySQL-backed test proving confirmed drafts become matrix publish items with copied copy and material context.

- [ ] **Step 1: Add MySQL integration helpers and test**

Append this code to `backend/tests/test_matrix_plan_from_drafts_api.py`:

```python
from app.repositories.user_repository import UserRepository


def auth_headers(mysql_conn, mysql_app_client, suffix: str) -> dict[str, str]:
    invite_code = f"INV-DRAFT-MATRIX-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=0,
        max_uses=1,
        expires_time=0,
        remark="draft-matrix-plan-api",
    )

    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": f"draft_matrix_user_{suffix}",
            "nickname": f"Draft Matrix User {suffix}",
            "password": "matrix-secret",
            "invite_code": invite_code,
        },
    )

    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_product(mysql_app_client, headers: dict[str, str], suffix: str) -> int:
    response = mysql_app_client.post(
        "/api/products",
        headers=headers,
        json={
            "product_name": f"Karries serum {suffix}",
            "brand_name": "KARRIES",
            "category": "skincare",
            "selling_point": {"points": ["gentle", "daily routine"]},
            "ai_material": {"scene": "morning commute", "audience": "office worker"},
        },
    )

    assert response.status_code == 200
    return response.json()["data"]["id"]


def create_xhs_account(mysql_app_client, headers: dict[str, str], suffix: str) -> int:
    response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=headers,
        json={
            "display_name": f"Draft Matrix account {suffix}",
            "profile": {
                "persona": "gentle skincare advisor",
                "target_audience": "office workers",
                "tone": "natural",
                "tag_preferences": "[\"#skincare\", \"#routine\"]",
            },
        },
    )

    assert response.status_code == 200
    return response.json()["data"]["id"]


def create_confirmed_draft(mysql_app_client, headers: dict[str, str], product_id: int, account_id: int) -> int:
    generate_response = mysql_app_client.post(
        "/api/content-drafts/product-copy",
        headers=headers,
        json={
            "product_id": product_id,
            "xhs_account_id": account_id,
            "extra_requirement": "keep the copy friendly",
        },
    )
    assert generate_response.status_code == 200
    draft_id = generate_response.json()["data"]["id"]

    update_response = mysql_app_client.patch(
        f"/api/content-drafts/{draft_id}",
        headers=headers,
        json={
            "title": "Friendly routine note",
            "body": "Final reviewed copy",
            "tags": ["#reviewed", "#skincare"],
            "status": "confirmed",
        },
    )
    assert update_response.status_code == 200
    return draft_id


def test_create_matrix_plan_from_confirmed_drafts_copies_content(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "copy")
    account_id = create_xhs_account(mysql_app_client, headers, "copy")
    product_id = create_product(mysql_app_client, headers, "copy")
    draft_id = create_confirmed_draft(mysql_app_client, headers, product_id, account_id)

    response = mysql_app_client.post(
        "/api/matrix-plans/from-drafts",
        headers=headers,
        json={
            "plan_name": "Reviewed content matrix",
            "draft_ids": [draft_id],
            "xhs_account_ids": [account_id],
            "schedule_start_time": 1_700_000_000,
            "schedule_end_time": 1_700_086_400,
            "min_interval_minutes": 360,
        },
    )

    assert response.status_code == 200
    created = response.json()["data"]
    assert created["id"] > 0
    assert created["item_count"] == 1
    assert created["draft_count"] == 1
    assert created["account_count"] == 1

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select source_type, content_type, product_id, status, scheduling_rule_json
            from matrix_publish_plan
            where id = %s
            """,
            (created["id"],),
        )
        plan = cursor.fetchone()
        cursor.execute(
            """
            select xhs_account_id, title, body, tag_json, material_json, status, scheduled_time
            from matrix_publish_item
            where plan_id = %s
            """,
            (created["id"],),
        )
        item = cursor.fetchone()

    assert plan["source_type"] == "content_draft"
    assert plan["content_type"] == "image_text"
    assert plan["product_id"] == 0
    assert plan["status"] == 2
    rule = json.loads(plan["scheduling_rule_json"])
    assert rule["draft_ids"] == [draft_id]
    assert rule["xhs_account_ids"] == [account_id]

    assert item["xhs_account_id"] == account_id
    assert item["title"] == "Friendly routine note"
    assert item["body"] == "Final reviewed copy"
    assert json.loads(item["tag_json"]) == ["#reviewed", "#skincare"]
    material = json.loads(item["material_json"])
    assert material["draft_id"] == draft_id
    assert material["source_content_draft_id"] == draft_id
    assert material["source_product_id"] == product_id
    assert material["target_xhs_account_id"] == account_id
    assert item["status"] == 1
    assert item["scheduled_time"] == 1_700_000_000
```

- [ ] **Step 2: Run the focused test file**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend/tests/test_matrix_plan_from_drafts_api.py -q
```

Expected: unit tests PASS; MySQL integration test SKIPPED unless `MYSQL_TEST_HOST`, `MYSQL_TEST_DATABASE`, and `MYSQL_TEST_USER` are configured.

- [ ] **Step 3: Run the backend test suite**

Run:

```powershell
.\.venv\Scripts\python -m pytest backend/tests -q
```

Expected: PASS with existing MySQL integration skips when test MySQL env vars are absent.

- [ ] **Step 4: Commit Task 4**

Run:

```powershell
git add backend/tests/test_matrix_plan_from_drafts_api.py
git commit -m "test: cover draft matrix plan flow"
```

---

## Self-Review

- Spec coverage: the plan maps the approved design to schema, draft ownership read, account ownership validation, confirmed status validation, schedule generation, transaction-safe plan/item inserts, item content copying, response counts, and MySQL-backed verification.
- Placeholder scan: the plan contains no deferred markers, no undefined future work markers, and no vague testing instruction without concrete commands.
- Type consistency: `MatrixPlanFromDraftsCreate`, `list_for_user_by_ids()`, `create_plan_from_drafts()`, and `_pair_drafts_with_schedule()` use the same field names and tuple order across tasks.
