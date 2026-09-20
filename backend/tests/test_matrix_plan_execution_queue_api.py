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


def test_confirm_plan_rolls_back_when_validation_fails_after_locking():
    from app.repositories.matrix_plan_repository import MatrixPlanRepository

    class FakeCursor:
        def __init__(self):
            self._fetchone_calls = 0
            self._fetchall_calls = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, _sql, _params):
            return None

        def fetchone(self):
            self._fetchone_calls += 1
            if self._fetchone_calls == 1:
                return {"id": 12, "status": 2}
            return None

        def fetchall(self):
            self._fetchall_calls += 1
            if self._fetchall_calls == 1:
                return [{"id": 101, "title": "", "body": "body", "status": 1}]
            return []

    class FakeConn:
        def __init__(self):
            self.rollback_calls = 0
            self.commit_calls = 0

        def cursor(self):
            return FakeCursor()

        def rollback(self):
            self.rollback_calls += 1

        def commit(self):
            self.commit_calls += 1

    conn = FakeConn()

    result = MatrixPlanRepository(conn).confirm_plan(user_id=5, plan_id=12)

    assert result == {"error": "publish item title and body are required"}
    assert conn.rollback_calls == 1
    assert conn.commit_calls == 0


def test_cancel_plan_rolls_back_when_validation_fails_after_locking():
    from app.repositories.matrix_plan_repository import MatrixPlanRepository

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, _sql, _params):
            return None

        def fetchone(self):
            return {"id": 12, "status": 3}

        def fetchall(self):
            return [{"id": 201, "status": 3}]

    class FakeConn:
        def __init__(self):
            self.rollback_calls = 0
            self.commit_calls = 0

        def cursor(self):
            return FakeCursor()

        def rollback(self):
            self.rollback_calls += 1

        def commit(self):
            self.commit_calls += 1

    conn = FakeConn()

    result = MatrixPlanRepository(conn).cancel_plan(user_id=5, plan_id=12)

    assert result == {"error": "plan has items already submitting"}
    assert conn.rollback_calls == 1
    assert conn.commit_calls == 0


def auth_headers(mysql_conn, mysql_app_client, suffix: str) -> dict[str, str]:
    from app.repositories.user_repository import UserRepository

    invite_code = f"INV-QUEUE-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=1000,
        max_uses=1,
        expires_time=0,
        remark="matrix-plan-execution-queue-api",
    )

    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": f"queue_user_{suffix}",
            "nickname": f"Queue User {suffix}",
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
            "display_name": f"Queue account {suffix}",
            "account_group": "queue",
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
            "product_name": f"Queue product {suffix}",
            "brand_name": "KARRIES",
            "category": "skincare",
        },
    )

    assert response.status_code == 200
    return response.json()["data"]["id"]


def create_confirmed_draft(
    mysql_app_client, headers: dict[str, str], product_id: int, account_id: int, suffix: str
) -> int:
    generate_response = mysql_app_client.post(
        "/api/content-drafts/product-copy",
        headers=headers,
        json={
            "product_id": product_id,
            "xhs_account_id": account_id,
            "extra_requirement": f"keep the copy friendly {suffix}",
        },
    )
    assert generate_response.status_code == 200
    draft_id = generate_response.json()["data"]["id"]

    update_response = mysql_app_client.patch(
        f"/api/content-drafts/{draft_id}",
        headers=headers,
        json={
            "title": f"Friendly routine note {suffix}",
            "body": f"Final reviewed copy {suffix}",
            "tags": ["#reviewed", "#skincare"],
            "status": "confirmed",
        },
    )
    assert update_response.status_code == 200
    return draft_id


def create_plan_from_drafts(
    mysql_app_client,
    headers: dict[str, str],
    draft_ids: list[int],
    account_id: int,
    suffix: str,
) -> int:
    response = mysql_app_client.post(
        "/api/matrix-plans/from-drafts",
        headers=headers,
        json={
            "plan_name": f"Queue plan {suffix}",
            "draft_ids": draft_ids,
            "xhs_account_ids": [account_id],
            "schedule_start_time": 1_700_000_000,
            "schedule_end_time": 1_700_086_400,
            "min_interval_minutes": 360,
        },
    )

    assert response.status_code == 200
    return response.json()["data"]["id"]


def test_get_matrix_plan_returns_plan_detail(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "detail")
    account_id = create_xhs_account(mysql_app_client, headers, "detail")
    product_id = create_product(mysql_app_client, headers, "detail")
    draft_id = create_confirmed_draft(
        mysql_app_client, headers, product_id, account_id, "detail"
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client, headers, [draft_id], account_id, "detail"
    )

    response = mysql_app_client.get(f"/api/matrix-plans/{plan_id}", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == plan_id
    assert data["status"] == 2
    assert data["item_count"] == 1
    assert data["scheduling_rule"]["draft_ids"] == [draft_id]


def test_get_matrix_plan_returns_404_for_other_user(mysql_conn, mysql_app_client):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "detail-owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "detail-other")
    account_id = create_xhs_account(mysql_app_client, owner_headers, "detail-owner")
    product_id = create_product(mysql_app_client, owner_headers, "detail-owner")
    draft_id = create_confirmed_draft(
        mysql_app_client, owner_headers, product_id, account_id, "detail-owner"
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client, owner_headers, [draft_id], account_id, "detail-owner"
    )

    response = mysql_app_client.get(f"/api/matrix-plans/{plan_id}", headers=other_headers)

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["error"]["message"] == "matrix plan not found"


def test_get_plan_items_are_sorted_by_schedule_time(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "sorted")
    account_id = create_xhs_account(mysql_app_client, headers, "sorted")
    product_id = create_product(mysql_app_client, headers, "sorted")
    draft_one_id = create_confirmed_draft(
        mysql_app_client, headers, product_id, account_id, "sorted-1"
    )
    draft_two_id = create_confirmed_draft(
        mysql_app_client, headers, product_id, account_id, "sorted-2"
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client, headers, [draft_one_id, draft_two_id], account_id, "sorted"
    )

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select id from matrix_publish_item where plan_id = %s order by id asc",
            (plan_id,),
        )
        item_ids = [row["id"] for row in cursor.fetchall()]
        cursor.execute(
            "update matrix_publish_item set scheduled_time = %s where id = %s",
            (1_700_000_900, item_ids[0]),
        )
        cursor.execute(
            "update matrix_publish_item set scheduled_time = %s where id = %s",
            (1_700_000_100, item_ids[1]),
        )
    mysql_conn.commit()

    response = mysql_app_client.get(f"/api/matrix-plans/{plan_id}/items", headers=headers)

    assert response.status_code == 200
    items = response.json()["data"]
    assert [item["id"] for item in items] == [item_ids[1], item_ids[0]]
    assert [item["scheduled_time"] for item in items] == [1_700_000_100, 1_700_000_900]


def test_confirm_plan_moves_items_to_pending_auto_submit(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "confirm")
    account_id = create_xhs_account(mysql_app_client, headers, "confirm")
    product_id = create_product(mysql_app_client, headers, "confirm")
    draft_id = create_confirmed_draft(
        mysql_app_client, headers, product_id, account_id, "confirm"
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client, headers, [draft_id], account_id, "confirm"
    )

    response = mysql_app_client.post(
        f"/api/matrix-plans/{plan_id}/confirm", headers=headers
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == plan_id
    assert data["status"] == 3
    assert data["item_count"] == 1

    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 3
        cursor.execute(
            "select status from matrix_publish_item where plan_id = %s",
            (plan_id,),
        )
        assert cursor.fetchone()["status"] == 2


def test_confirm_plan_rejects_blank_title_or_body(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "blank")
    account_id = create_xhs_account(mysql_app_client, headers, "blank")
    product_id = create_product(mysql_app_client, headers, "blank")
    draft_id = create_confirmed_draft(
        mysql_app_client, headers, product_id, account_id, "blank"
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client, headers, [draft_id], account_id, "blank"
    )

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "update matrix_publish_item set title = %s where plan_id = %s",
            ("   ", plan_id),
        )
    mysql_conn.commit()

    response = mysql_app_client.post(
        f"/api/matrix-plans/{plan_id}/confirm", headers=headers
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"] == "publish item title and body are required"

    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 2
        cursor.execute(
            "select status from matrix_publish_item where plan_id = %s",
            (plan_id,),
        )
        assert cursor.fetchone()["status"] == 1


def test_confirm_plan_rejects_blank_body(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "blank-body")
    account_id = create_xhs_account(mysql_app_client, headers, "blank-body")
    product_id = create_product(mysql_app_client, headers, "blank-body")
    draft_id = create_confirmed_draft(
        mysql_app_client, headers, product_id, account_id, "blank-body"
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client, headers, [draft_id], account_id, "blank-body"
    )

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "update matrix_publish_item set body = %s where plan_id = %s",
            ("   ", plan_id),
        )
    mysql_conn.commit()

    response = mysql_app_client.post(
        f"/api/matrix-plans/{plan_id}/confirm", headers=headers
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"] == "publish item title and body are required"

    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 2
        cursor.execute(
            "select status from matrix_publish_item where plan_id = %s",
            (plan_id,),
        )
        assert cursor.fetchone()["status"] == 1


def test_confirm_plan_rejects_item_not_pending_confirmation(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "bad-item-status")
    account_id = create_xhs_account(mysql_app_client, headers, "bad-item-status")
    product_id = create_product(mysql_app_client, headers, "bad-item-status")
    draft_id = create_confirmed_draft(
        mysql_app_client, headers, product_id, account_id, "bad-item-status"
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client, headers, [draft_id], account_id, "bad-item-status"
    )

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "update matrix_publish_item set status = %s where plan_id = %s",
            (2, plan_id),
        )
    mysql_conn.commit()

    response = mysql_app_client.post(
        f"/api/matrix-plans/{plan_id}/confirm", headers=headers
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"] == "publish items are not all pending confirmation"

    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 2


def test_cancel_plan_marks_pending_items_cancelled(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "cancel")
    account_id = create_xhs_account(mysql_app_client, headers, "cancel")
    product_id = create_product(mysql_app_client, headers, "cancel")
    draft_one_id = create_confirmed_draft(
        mysql_app_client, headers, product_id, account_id, "cancel-1"
    )
    draft_two_id = create_confirmed_draft(
        mysql_app_client, headers, product_id, account_id, "cancel-2"
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client, headers, [draft_one_id, draft_two_id], account_id, "cancel"
    )

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select id from matrix_publish_item where plan_id = %s order by id asc",
            (plan_id,),
        )
        item_ids = [row["id"] for row in cursor.fetchall()]
        cursor.execute(
            "update matrix_publish_plan set status = 3 where id = %s",
            (plan_id,),
        )
        cursor.execute(
            "update matrix_publish_item set status = 1 where id = %s",
            (item_ids[0],),
        )
        cursor.execute(
            "update matrix_publish_item set status = 2 where id = %s",
            (item_ids[1],),
        )
    mysql_conn.commit()

    response = mysql_app_client.post(
        f"/api/matrix-plans/{plan_id}/cancel", headers=headers
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == plan_id
    assert data["status"] == 7
    assert data["cancelled_item_count"] == 2

    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 7
        cursor.execute(
            "select status from matrix_publish_item where plan_id = %s order by id asc",
            (plan_id,),
        )
        assert [row["status"] for row in cursor.fetchall()] == [7, 7]


def test_cancel_plan_rejects_submitting_items(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "submitting")
    account_id = create_xhs_account(mysql_app_client, headers, "submitting")
    product_id = create_product(mysql_app_client, headers, "submitting")
    draft_id = create_confirmed_draft(
        mysql_app_client, headers, product_id, account_id, "submitting"
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client, headers, [draft_id], account_id, "submitting"
    )

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "update matrix_publish_plan set status = %s where id = %s",
            (3, plan_id),
        )
        cursor.execute(
            "update matrix_publish_item set status = %s where plan_id = %s",
            (3, plan_id),
        )
    mysql_conn.commit()

    response = mysql_app_client.post(
        f"/api/matrix-plans/{plan_id}/cancel", headers=headers
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"] == "plan has items already submitting"

    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 3
        cursor.execute(
            "select status from matrix_publish_item where plan_id = %s",
            (plan_id,),
        )
        assert cursor.fetchone()["status"] == 3


def test_matrix_plan_execution_routes_are_user_isolated(mysql_conn, mysql_app_client):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "isolation-owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "isolation-other")
    account_id = create_xhs_account(mysql_app_client, owner_headers, "isolation-owner")
    product_id = create_product(mysql_app_client, owner_headers, "isolation-owner")
    draft_id = create_confirmed_draft(
        mysql_app_client, owner_headers, product_id, account_id, "isolation-owner"
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client, owner_headers, [draft_id], account_id, "isolation-owner"
    )

    items_response = mysql_app_client.get(
        f"/api/matrix-plans/{plan_id}/items",
        headers=other_headers,
    )
    confirm_response = mysql_app_client.post(
        f"/api/matrix-plans/{plan_id}/confirm",
        headers=other_headers,
    )
    cancel_response = mysql_app_client.post(
        f"/api/matrix-plans/{plan_id}/cancel",
        headers=other_headers,
    )

    for response in (items_response, confirm_response, cancel_response):
        assert response.status_code == 404
        payload = response.json()
        assert payload["error"]["code"] == "NOT_FOUND"
        assert payload["error"]["message"] == "matrix plan not found"
