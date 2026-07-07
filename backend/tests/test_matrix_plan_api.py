import json

import pytest

from app.repositories.user_repository import UserRepository


def auth_headers(mysql_conn, mysql_app_client, suffix: str) -> dict[str, str]:
    invite_code = f"INV-MATRIX-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=0,
        max_uses=1,
        expires_time=0,
        remark="matrix-plan-api",
    )

    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": f"matrix_user_{suffix}",
            "nickname": f"Matrix User {suffix}",
            "password": "matrix-secret",
            "invite_code": invite_code,
        },
    )

    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_xhs_account(mysql_app_client, headers: dict[str, str], suffix: str) -> int:
    response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=headers,
        json={
            "display_name": f"Matrix account {suffix}",
            "account_group": "matrix",
            "daily_limit": 3,
            "min_interval_minutes": 120,
        },
    )

    assert response.status_code == 200
    return response.json()["data"]["id"]


def create_product(mysql_app_client, headers: dict[str, str], suffix: str) -> int:
    response = mysql_app_client.post(
        "/api/products",
        headers=headers,
        json={
            "product_name": f"Matrix product {suffix}",
            "brand_name": "KARRIES",
            "category": "skincare",
        },
    )

    assert response.status_code == 200
    return response.json()["data"]["id"]


def test_generate_schedule_times_offsets_accounts_and_clamps_to_end():
    from app.services.scheduling_service import generate_schedule_times

    schedule = generate_schedule_times(
        account_ids=[11, 12],
        schedule_start_time=1_700_000_000,
        schedule_end_time=1_700_000_900,
        items_per_account=2,
        min_interval_minutes=10,
    )

    assert schedule == [
        (11, 1_700_000_000),
        (11, 1_700_000_600),
        (12, 1_700_000_300),
        (12, 1_700_000_900),
    ]


def test_generate_schedule_times_rejects_invalid_range():
    from app.services.scheduling_service import generate_schedule_times

    with pytest.raises(ValueError, match="schedule start must be before end"):
        generate_schedule_times(
            account_ids=[11],
            schedule_start_time=200,
            schedule_end_time=100,
            items_per_account=1,
            min_interval_minutes=360,
        )


class FakeMatrixPlanCursor:
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
            self.lastrowid = 77
        elif normalized.startswith("insert into matrix_publish_item"):
            raise RuntimeError("item insert failed")

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class FakeMatrixPlanConnection:
    def __init__(self):
        self.statements = []
        self.commit_count = 0
        self.rollback_count = 0

    def cursor(self):
        return FakeMatrixPlanCursor(self)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def test_create_plan_rolls_back_when_item_insert_fails():
    from app.repositories.matrix_plan_repository import MatrixPlanRepository
    from app.schemas.matrix_plan import MatrixPlanCreate

    conn = FakeMatrixPlanConnection()
    payload = MatrixPlanCreate(
        plan_name="Rollback plan",
        product_id=9,
        xhs_account_ids=[11],
        schedule_start_time=1_700_000_000,
        schedule_end_time=1_700_086_400,
    )

    with pytest.raises(RuntimeError, match="item insert failed"):
        MatrixPlanRepository(conn).create_plan(
            user_id=5,
            payload=payload,
            schedule=[(11, 1_700_000_000)],
        )

    assert conn.commit_count == 0
    assert conn.rollback_count == 1
    assert any("insert into matrix_publish_plan" in statement for statement in conn.statements)
    assert any("insert into matrix_publish_item" in statement for statement in conn.statements)


def test_matrix_plan_create_accepts_public_schedule_aliases():
    from app.schemas.matrix_plan import MatrixPlanCreate

    payload = MatrixPlanCreate(
        plan_name="Alias plan",
        product_id=9,
        xhs_account_ids=[11],
        schedule_start=1_700_000_000,
        schedule_end=1_700_086_400,
    )

    assert payload.schedule_start_time == 1_700_000_000
    assert payload.schedule_end_time == 1_700_086_400


def test_temporary_material_plan_validates_nonzero_product_owner(monkeypatch):
    from app.api import matrix_plans as matrix_plans_api
    from app.schemas.matrix_plan import MatrixPlanCreate

    class FakeRepository:
        def __init__(self, _conn):
            self.product_checked = False

        def validate_product_for_user(self, user_id, product_id):
            assert user_id == 5
            assert product_id == 99
            self.product_checked = True
            return False

        def validate_accounts_for_user(self, _user_id, _account_ids):
            return True

        def create_plan(self, *_args, **_kwargs):
            raise AssertionError("create_plan should not run for cross-user product")

    monkeypatch.setattr(matrix_plans_api, "MatrixPlanRepository", FakeRepository)
    payload = MatrixPlanCreate(
        plan_name="Temporary material plan",
        source_type="temporary_material",
        product_id=99,
        xhs_account_ids=[11],
        schedule_start_time=1_700_000_000,
        schedule_end_time=1_700_086_400,
    )

    response = matrix_plans_api.create_matrix_plan(
        payload=payload,
        user={"id": 5},
        conn=object(),
    )

    assert response.status_code == 404
    body = json.loads(response.body)
    assert body["error"]["code"] == "NOT_FOUND"


def test_create_matrix_publish_plan_generates_items(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "create")
    account_id = create_xhs_account(mysql_app_client, headers, "create")
    product_id = create_product(mysql_app_client, headers, "create")

    response = mysql_app_client.post(
        "/api/matrix-plans",
        headers=headers,
        json={
            "plan_name": "Launch week matrix",
            "source_type": "product",
            "content_type": "image_text",
            "product_id": product_id,
            "xhs_account_ids": [account_id],
            "schedule_start_time": 1_700_000_000,
            "schedule_end_time": 1_700_086_400,
            "items_per_account": 2,
            "min_interval_minutes": 360,
        },
    )

    assert response.status_code == 200
    created = response.json()["data"]
    assert created["id"] > 0
    assert created["item_count"] == 2

    list_response = mysql_app_client.get("/api/matrix-plans", headers=headers)

    assert list_response.status_code == 200
    plans = list_response.json()["data"]
    assert len(plans) == 1
    assert plans[0]["id"] == created["id"]
    assert plans[0]["plan_name"] == "Launch week matrix"
    assert plans[0]["item_count"] == 2
    assert plans[0]["scheduling_rule"]["xhs_account_ids"] == [account_id]


def test_matrix_plans_are_user_isolated(mysql_conn, mysql_app_client):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "other")
    account_id = create_xhs_account(mysql_app_client, owner_headers, "owner")
    product_id = create_product(mysql_app_client, owner_headers, "owner")

    create_response = mysql_app_client.post(
        "/api/matrix-plans",
        headers=owner_headers,
        json={
            "plan_name": "Owner plan",
            "product_id": product_id,
            "xhs_account_ids": [account_id],
            "schedule_start_time": 1_700_000_000,
            "schedule_end_time": 1_700_086_400,
        },
    )
    assert create_response.status_code == 200

    list_response = mysql_app_client.get("/api/matrix-plans", headers=other_headers)

    assert list_response.status_code == 200
    assert list_response.json()["data"] == []


def test_matrix_plan_rejects_cross_user_account_or_product(mysql_conn, mysql_app_client):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "cross-owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "cross-other")
    owner_account_id = create_xhs_account(mysql_app_client, owner_headers, "cross-owner")
    owner_product_id = create_product(mysql_app_client, owner_headers, "cross-owner")
    other_account_id = create_xhs_account(mysql_app_client, other_headers, "cross-other")
    other_product_id = create_product(mysql_app_client, other_headers, "cross-other")

    product_response = mysql_app_client.post(
        "/api/matrix-plans",
        headers=other_headers,
        json={
            "plan_name": "Cross product plan",
            "product_id": owner_product_id,
            "xhs_account_ids": [other_account_id],
            "schedule_start_time": 1_700_000_000,
            "schedule_end_time": 1_700_086_400,
        },
    )

    assert product_response.status_code == 404
    assert product_response.json()["error"]["code"] == "NOT_FOUND"

    account_response = mysql_app_client.post(
        "/api/matrix-plans",
        headers=other_headers,
        json={
            "plan_name": "Cross account plan",
            "product_id": other_product_id,
            "xhs_account_ids": [owner_account_id],
            "schedule_start_time": 1_700_000_000,
            "schedule_end_time": 1_700_086_400,
        },
    )

    assert account_response.status_code == 404
    assert account_response.json()["error"]["code"] == "NOT_FOUND"


def test_matrix_plan_rejects_invalid_schedule_range(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "invalid-range")
    account_id = create_xhs_account(mysql_app_client, headers, "invalid-range")
    product_id = create_product(mysql_app_client, headers, "invalid-range")

    response = mysql_app_client.post(
        "/api/matrix-plans",
        headers=headers,
        json={
            "plan_name": "Invalid range plan",
            "product_id": product_id,
            "xhs_account_ids": [account_id],
            "schedule_start_time": 1_700_086_400,
            "schedule_end_time": 1_700_000_000,
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"


def test_matrix_plan_requires_auth(app_client_without_db):
    response = app_client_without_db.get("/api/matrix-plans")

    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNAUTHORIZED"
