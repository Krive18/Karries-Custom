import json

from app.repositories.user_repository import UserRepository


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


def test_create_matrix_plan_from_drafts_rejects_duplicate_xhs_account_ids(monkeypatch):
    from app.api import matrix_plans as matrix_plans_api
    from app.schemas.matrix_plan import MatrixPlanFromDraftsCreate

    class FakeRepository:
        def __init__(self, _conn):
            raise AssertionError("repository should not be constructed for duplicate accounts")

    monkeypatch.setattr(matrix_plans_api, "MatrixPlanRepository", FakeRepository)

    response = matrix_plans_api.create_matrix_plan_from_drafts(
        payload=MatrixPlanFromDraftsCreate(
            plan_name="Duplicate accounts",
            draft_ids=[31],
            xhs_account_ids=[11, 11],
            schedule_start_time=1_700_000_000,
            schedule_end_time=1_700_086_400,
        ),
        user={"id": 5},
        conn=object(),
    )

    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_create_matrix_plan_from_drafts_rejects_missing_or_cross_user_draft(monkeypatch):
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
            raise AssertionError("plan should not be created when a draft is missing")

    class FakeDraftRepository:
        def __init__(self, _conn):
            pass

        def list_for_user_by_ids(self, user_id, draft_ids):
            assert user_id == 5
            assert draft_ids == [31]
            return []

    monkeypatch.setattr(matrix_plans_api, "MatrixPlanRepository", FakeMatrixRepository)
    monkeypatch.setattr(matrix_plans_api, "ContentDraftRepository", FakeDraftRepository)

    response = matrix_plans_api.create_matrix_plan_from_drafts(
        payload=MatrixPlanFromDraftsCreate(
            plan_name="Missing draft",
            draft_ids=[31],
            xhs_account_ids=[11],
            schedule_start_time=1_700_000_000,
            schedule_end_time=1_700_086_400,
        ),
        user={"id": 5},
        conn=object(),
    )

    assert response.status_code == 404
    body = json.loads(response.body)
    assert body["error"]["code"] == "NOT_FOUND"


def test_create_matrix_plan_from_drafts_rejects_missing_or_cross_user_account(monkeypatch):
    from app.api import matrix_plans as matrix_plans_api
    from app.schemas.matrix_plan import MatrixPlanFromDraftsCreate

    class FakeMatrixRepository:
        def __init__(self, _conn):
            pass

        def validate_accounts_for_user(self, user_id, account_ids):
            assert user_id == 5
            assert account_ids == [11]
            return False

    class FakeDraftRepository:
        def __init__(self, _conn):
            raise AssertionError("draft lookup should not run when account validation fails")

    monkeypatch.setattr(matrix_plans_api, "MatrixPlanRepository", FakeMatrixRepository)
    monkeypatch.setattr(matrix_plans_api, "ContentDraftRepository", FakeDraftRepository)

    response = matrix_plans_api.create_matrix_plan_from_drafts(
        payload=MatrixPlanFromDraftsCreate(
            plan_name="Missing account",
            draft_ids=[31],
            xhs_account_ids=[11],
            schedule_start_time=1_700_000_000,
            schedule_end_time=1_700_086_400,
        ),
        user={"id": 5},
        conn=object(),
    )

    assert response.status_code == 404
    body = json.loads(response.body)
    assert body["error"]["code"] == "NOT_FOUND"


def test_create_matrix_plan_from_drafts_rejects_invalid_schedule_range(monkeypatch):
    from app.api import matrix_plans as matrix_plans_api
    from app.schemas.matrix_plan import MatrixPlanFromDraftsCreate

    class FakeMatrixRepository:
        def __init__(self, _conn):
            raise AssertionError("repository should not be constructed for invalid schedule range")

    monkeypatch.setattr(matrix_plans_api, "MatrixPlanRepository", FakeMatrixRepository)

    response = matrix_plans_api.create_matrix_plan_from_drafts(
        payload=MatrixPlanFromDraftsCreate(
            plan_name="Invalid schedule range",
            draft_ids=[31],
            xhs_account_ids=[11],
            schedule_start_time=1_700_086_400,
            schedule_end_time=1_700_000_000,
        ),
        user={"id": 5},
        conn=object(),
    )

    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_create_matrix_plan_from_drafts_pairs_multiple_accounts_and_drafts_in_account_outer_order(monkeypatch):
    from app.api import matrix_plans as matrix_plans_api
    from app.schemas.matrix_plan import MatrixPlanFromDraftsCreate

    captured = {}

    class FakeMatrixRepository:
        def __init__(self, _conn):
            pass

        def validate_accounts_for_user(self, user_id, account_ids):
            captured["validated_accounts"] = (user_id, list(account_ids))
            return True

        def create_plan_from_drafts(self, user_id, payload, drafts, draft_schedule):
            captured["create_plan_from_drafts"] = {
                "user_id": user_id,
                "payload": payload,
                "drafts": drafts,
                "draft_schedule": draft_schedule,
            }
            return 901, len(draft_schedule)

    class FakeDraftRepository:
        def __init__(self, _conn):
            pass

        def list_for_user_by_ids(self, user_id, draft_ids):
            captured["loaded_drafts"] = (user_id, list(draft_ids))
            return [
                {
                    "id": 31,
                    "product_id": 7,
                    "content_type": "image_text",
                    "title": "Draft 31",
                    "body": "Body 31",
                    "tags": ["#31"],
                    "material": {"existing": "draft-31"},
                    "status": "confirmed",
                },
                {
                    "id": 32,
                    "product_id": 8,
                    "content_type": "image_text",
                    "title": "Draft 32",
                    "body": "Body 32",
                    "tags": ["#32"],
                    "material": {"existing": "draft-32"},
                    "status": "confirmed",
                },
            ]

    def fake_generate_schedule_times(*args, **kwargs):
        captured["generate_schedule_times"] = {"args": args, "kwargs": kwargs}
        return [
            (11, 1_700_000_001),
            (11, 1_700_000_002),
            (12, 1_700_000_003),
            (12, 1_700_000_004),
        ]

    monkeypatch.setattr(matrix_plans_api, "MatrixPlanRepository", FakeMatrixRepository)
    monkeypatch.setattr(matrix_plans_api, "ContentDraftRepository", FakeDraftRepository)
    monkeypatch.setattr(matrix_plans_api, "generate_schedule_times", fake_generate_schedule_times)

    response = matrix_plans_api.create_matrix_plan_from_drafts(
        payload=MatrixPlanFromDraftsCreate(
            plan_name="Draft/account pairing",
            draft_ids=[31, 32],
            xhs_account_ids=[11, 12],
            schedule_start_time=1_700_000_000,
            schedule_end_time=1_700_086_400,
            min_interval_minutes=360,
        ),
        user={"id": 5},
        conn=object(),
    )

    body = response if isinstance(response, dict) else json.loads(response.body)
    assert body["data"]["id"] == 901
    assert body["data"]["item_count"] == 4
    assert body["data"]["draft_count"] == 2
    assert body["data"]["account_count"] == 2

    assert captured["validated_accounts"] == (5, [11, 12])
    assert captured["loaded_drafts"] == (5, [31, 32])
    assert captured["generate_schedule_times"]["kwargs"] == {
        "account_ids": [11, 12],
        "schedule_start_time": 1_700_000_000,
        "schedule_end_time": 1_700_086_400,
        "items_per_account": 2,
        "min_interval_minutes": 360,
    }
    assert captured["create_plan_from_drafts"]["user_id"] == 5
    assert captured["create_plan_from_drafts"]["payload"].plan_name == "Draft/account pairing"
    assert captured["create_plan_from_drafts"]["payload"].draft_ids == [31, 32]
    assert captured["create_plan_from_drafts"]["payload"].xhs_account_ids == [11, 12]
    assert captured["create_plan_from_drafts"]["drafts"][0]["id"] == 31
    assert captured["create_plan_from_drafts"]["drafts"][1]["id"] == 32
    assert captured["create_plan_from_drafts"]["draft_schedule"] == [
        (11, 31, 1_700_000_001),
        (11, 32, 1_700_000_002),
        (12, 31, 1_700_000_003),
        (12, 32, 1_700_000_004),
    ]


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


def create_confirmed_draft(
    mysql_app_client, headers: dict[str, str], product_id: int, account_id: int
) -> int:
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


def test_create_matrix_plan_from_confirmed_drafts_copies_content(
    mysql_conn, mysql_app_client
):
    headers = auth_headers(mysql_conn, mysql_app_client, "copy")
    account_id = create_xhs_account(mysql_app_client, headers, "copy")
    product_id = create_product(mysql_app_client, headers, "copy")
    draft_id = create_confirmed_draft(mysql_app_client, headers, product_id, account_id)

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select status, update_time, title, body, tag_json
            from content_draft
            where id = %s
            """,
            (draft_id,),
        )
        draft_before = cursor.fetchone()

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

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select status, update_time, title, body, tag_json
            from content_draft
            where id = %s
            """,
            (draft_id,),
        )
        draft_after = cursor.fetchone()

    assert draft_after["status"] == draft_before["status"]
    assert draft_after["update_time"] == draft_before["update_time"]
    assert draft_after["title"] == draft_before["title"]
    assert draft_after["body"] == draft_before["body"]
    assert draft_after["tag_json"] == draft_before["tag_json"]
