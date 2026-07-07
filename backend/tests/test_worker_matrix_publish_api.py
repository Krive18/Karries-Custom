from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.core.responses import fail, ok
from test_matrix_plan_execution_queue_api import (
    auth_headers,
    create_confirmed_draft,
    create_plan_from_drafts,
    create_product,
    create_xhs_account,
)


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


def test_worker_claim_requires_valid_token(app_client_without_db):
    app_client_without_db.app.state.config.worker_api_token = "secret"

    response = app_client_without_db.post(
        "/api/worker/matrix-publish-items/claim",
        json={"limit": 1, "now_time": 1_700_000_000},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def create_claimed_worker_item(
    mysql_conn,
    mysql_app_client,
    suffix: str,
    *,
    draft_count: int = 1,
    claim_limit: int = 5,
) -> tuple[int, int]:
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"
    headers = auth_headers(mysql_conn, mysql_app_client, f"worker-result-{suffix}")
    account_id = create_xhs_account(mysql_app_client, headers, f"worker-result-{suffix}")
    product_id = create_product(mysql_app_client, headers, f"worker-result-{suffix}")
    draft_ids = [
        create_confirmed_draft(
            mysql_app_client,
            headers,
            product_id,
            account_id,
            f"worker-result-{suffix}-{index}",
        )
        for index in range(draft_count)
    ]
    plan_id = create_plan_from_drafts(
        mysql_app_client,
        headers,
        draft_ids,
        account_id,
        f"worker-result-{suffix}",
    )
    confirm = mysql_app_client.post(f"/api/matrix-plans/{plan_id}/confirm", headers=headers)
    assert confirm.status_code == 200

    claim_response = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": claim_limit, "now_time": 1_700_000_000},
    )
    assert claim_response.status_code == 200
    items = claim_response.json()["data"]["items"]
    expected_item_count = min(draft_count, claim_limit)
    assert len(items) == expected_item_count
    return items[0]["id"], plan_id


def test_worker_claim_due_items_marks_items_submitting(mysql_conn, mysql_app_client):
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"
    headers = auth_headers(mysql_conn, mysql_app_client, "worker-claim")
    account_id = create_xhs_account(mysql_app_client, headers, "worker-claim")
    product_id = create_product(mysql_app_client, headers, "worker-claim")
    draft_id = create_confirmed_draft(
        mysql_app_client,
        headers,
        product_id,
        account_id,
        "worker-claim",
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client,
        headers,
        [draft_id],
        account_id,
        "worker-claim",
    )
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


def test_worker_success_marks_item_submitted_and_plan_complete(mysql_conn, mysql_app_client):
    item_id, plan_id = create_claimed_worker_item(mysql_conn, mysql_app_client, "success")

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/success",
        headers={"X-Worker-Token": "worker-secret"},
        json={"message": "submitted"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == 4
    assert response.json()["data"]["plan_status"] == 5
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status, last_error from matrix_publish_item where id = %s", (item_id,))
        item = cursor.fetchone()
        assert item["status"] == 4
        assert item["last_error"] == "submitted"
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 5


def test_full_matrix_queue_lifecycle(mysql_conn, mysql_app_client):
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"
    headers = auth_headers(mysql_conn, mysql_app_client, "full-life")
    account_id = create_xhs_account(mysql_app_client, headers, "full-life")
    product_id = create_product(mysql_app_client, headers, "full-life")
    draft_id = create_confirmed_draft(
        mysql_app_client,
        headers,
        product_id,
        account_id,
        "full-life",
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client,
        headers,
        [draft_id],
        account_id,
        "full-life",
    )

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


def test_worker_success_keeps_plan_running_when_other_items_not_done(mysql_conn, mysql_app_client):
    item_id, plan_id = create_claimed_worker_item(
        mysql_conn,
        mysql_app_client,
        "success-partial",
        draft_count=2,
        claim_limit=1,
    )

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/success",
        headers={"X-Worker-Token": "worker-secret"},
        json={"message": "submitted"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["plan_status"] == 4
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 4
        cursor.execute(
            "select status from matrix_publish_item where plan_id = %s order by id asc",
            (plan_id,),
        )
        assert [row["status"] for row in cursor.fetchall()] == [4, 2]


def test_worker_fail_marks_item_failed_and_plan_failed(mysql_conn, mysql_app_client):
    item_id, plan_id = create_claimed_worker_item(mysql_conn, mysql_app_client, "fail")

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/fail",
        headers={"X-Worker-Token": "worker-secret"},
        json={"error_message": "upload failed"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == 5
    assert response.json()["data"]["plan_status"] == 6
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status, last_error from matrix_publish_item where id = %s", (item_id,))
        item = cursor.fetchone()
        assert item["status"] == 5
        assert item["last_error"] == "upload failed"
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 6


def test_worker_manual_takeover_marks_item_and_plan_failed(mysql_conn, mysql_app_client):
    item_id, plan_id = create_claimed_worker_item(mysql_conn, mysql_app_client, "manual")

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/manual-takeover",
        headers={"X-Worker-Token": "worker-secret"},
        json={"reason": "login expired"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == 6
    assert response.json()["data"]["plan_status"] == 6
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status, last_error from matrix_publish_item where id = %s", (item_id,))
        item = cursor.fetchone()
        assert item["status"] == 6
        assert item["last_error"] == "login expired"
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 6


def test_worker_result_returns_not_found_for_missing_item(mysql_conn, mysql_app_client):
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"

    response = mysql_app_client.post(
        "/api/worker/matrix-publish-items/999999/success",
        headers={"X-Worker-Token": "worker-secret"},
        json={"message": "submitted"},
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["error"]["message"] == "matrix publish item not found"


def test_worker_result_returns_validation_error_for_wrong_item_status(
    mysql_conn, mysql_app_client
):
    item_id, plan_id = create_claimed_worker_item(mysql_conn, mysql_app_client, "wrong-status")

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "update matrix_publish_item set status = %s where id = %s",
            (2, item_id),
        )
    mysql_conn.commit()

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/fail",
        headers={"X-Worker-Token": "worker-secret"},
        json={"error_message": "upload failed"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"] == "publish item is not submitting"

    with mysql_conn.cursor() as cursor:
        cursor.execute("select status, last_error from matrix_publish_item where id = %s", (item_id,))
        item = cursor.fetchone()
        assert item["status"] == 2
        assert item["last_error"] == ""
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 4
