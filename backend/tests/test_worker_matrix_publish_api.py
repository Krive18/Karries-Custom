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
