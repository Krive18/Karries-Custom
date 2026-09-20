import time

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


def mark_account_login_ready(mysql_conn, account_id: int) -> None:
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            update xhs_account
            set status = 1, login_state_path = %s
            where id = %s
            """,
            (f"data/test-xhs-account-{account_id}.json", account_id),
        )
    mysql_conn.commit()


def worker_result_json(mysql_conn, item_id: int, **values) -> dict:
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select lease_token from matrix_publish_item where id = %s",
            (item_id,),
        )
        row = cursor.fetchone()
    return {"lease_token": str(row["lease_token"]), **values}


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
    mark_account_login_ready(mysql_conn, account_id)
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


def create_claimed_worker_items(
    mysql_conn,
    mysql_app_client,
    suffix: str,
    *,
    draft_count: int,
    claim_limit: int,
    now_time: int = 1_700_000_000,
) -> tuple[list[dict], int]:
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"
    headers = auth_headers(mysql_conn, mysql_app_client, f"worker-result-{suffix}")
    account_id = create_xhs_account(mysql_app_client, headers, f"worker-result-{suffix}")
    mark_account_login_ready(mysql_conn, account_id)
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
    if draft_count > 1:
        additional_account_ids = [
            create_xhs_account(
                mysql_app_client,
                headers,
                f"worker-result-{suffix}-account-{index}",
            )
            for index in range(1, draft_count)
        ]
        for additional_account_id in additional_account_ids:
            mark_account_login_ready(mysql_conn, additional_account_id)
        with mysql_conn.cursor() as cursor:
            cursor.execute(
                """
                select id
                from matrix_publish_item
                where plan_id = %s
                order by id asc
                """,
                (plan_id,),
            )
            item_ids = [int(row["id"]) for row in cursor.fetchall()]
            for item_id, additional_account_id in zip(
                item_ids[1:],
                additional_account_ids,
                strict=True,
            ):
                cursor.execute(
                    """
                    update matrix_publish_item
                    set xhs_account_id = %s
                    where id = %s
                    """,
                    (additional_account_id, item_id),
                )
        mysql_conn.commit()
    confirm = mysql_app_client.post(f"/api/matrix-plans/{plan_id}/confirm", headers=headers)
    assert confirm.status_code == 200

    expected_item_count = min(draft_count, claim_limit)
    items: list[dict] = []
    while len(items) < expected_item_count:
        claim_response = mysql_app_client.post(
            "/api/worker/matrix-publish-items/claim",
            headers={"X-Worker-Token": "worker-secret"},
            json={"limit": expected_item_count - len(items), "now_time": now_time},
        )
        assert claim_response.status_code == 200
        claimed_items = claim_response.json()["data"]["items"]
        assert claimed_items
        items.extend(claimed_items)

    return items, plan_id


def test_worker_claim_due_items_marks_items_submitting(mysql_conn, mysql_app_client):
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"
    headers = auth_headers(mysql_conn, mysql_app_client, "worker-claim")
    account_id = create_xhs_account(mysql_app_client, headers, "worker-claim")
    mark_account_login_ready(mysql_conn, account_id)
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
    assert len(items[0]["lease_token"]) == 32
    assert items[0]["attempt_count"] == 1
    assert items[0]["max_attempts"] == 3
    assert items[0]["lease_expires_time"] == 1_700_000_300

    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 4
        cursor.execute(
            """
            select status, attempt_count, lease_token, lease_expires_time
            from matrix_publish_item
            where id = %s
            """,
            (items[0]["id"],),
        )
        claimed = cursor.fetchone()
        assert claimed["status"] == 3
        assert claimed["attempt_count"] == 1
        assert claimed["lease_token"] == items[0]["lease_token"]
        assert claimed["lease_expires_time"] == 1_700_000_300


def test_worker_success_marks_item_submitted_and_plan_complete(mysql_conn, mysql_app_client):
    item_id, plan_id = create_claimed_worker_item(mysql_conn, mysql_app_client, "success")

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/success",
        headers={"X-Worker-Token": "worker-secret"},
        json=worker_result_json(
            mysql_conn,
            item_id,
            message="submitted",
            result_data={"platform": "xiaohongshu"},
        ),
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == 4
    assert response.json()["data"]["plan_status"] == 5
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select status, last_error, submitted_time, publish_result_json,
                   lease_token, lease_expires_time
            from matrix_publish_item
            where id = %s
            """,
            (item_id,),
        )
        item = cursor.fetchone()
        assert item["status"] == 4
        assert item["last_error"] == ""
        assert item["submitted_time"] > 0
        assert '"platform": "xiaohongshu"' in item["publish_result_json"]
        assert item["lease_token"] == ""
        assert item["lease_expires_time"] == 0
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 5


def test_full_matrix_queue_lifecycle(mysql_conn, mysql_app_client):
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"
    headers = auth_headers(mysql_conn, mysql_app_client, "full-life")
    account_id = create_xhs_account(mysql_app_client, headers, "full-life")
    mark_account_login_ready(mysql_conn, account_id)
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
    balance_before = mysql_app_client.get(
        "/api/wallet",
        headers=headers,
    ).json()["data"]["balance"]

    confirm = mysql_app_client.post(f"/api/matrix-plans/{plan_id}/confirm", headers=headers)
    assert confirm.status_code == 200
    balance_after_confirm = mysql_app_client.get(
        "/api/wallet",
        headers=headers,
    ).json()["data"]["balance"]
    assert balance_after_confirm == balance_before

    claim = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": 1, "now_time": 1_700_000_000},
    )
    assert claim.status_code == 200
    claimed_item = claim.json()["data"]["items"][0]
    item_id = claimed_item["id"]

    success = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/success",
        headers={"X-Worker-Token": "worker-secret"},
        json={
            "lease_token": claimed_item["lease_token"],
            "message": "submitted",
        },
    )
    assert success.status_code == 200
    balance_after_success = mysql_app_client.get(
        "/api/wallet",
        headers=headers,
    ).json()["data"]["balance"]
    assert balance_after_success == balance_before - 20

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
        json=worker_result_json(mysql_conn, item_id, message="submitted"),
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
        json=worker_result_json(mysql_conn, item_id, error_message="upload failed"),
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
        cursor.execute(
            """
            select count(*) as charge_count
            from credit_ledger
            where business_type = 'scheduled_publish'
              and business_id in (%s, %s)
            """,
            (item_id, plan_id),
        )
        assert cursor.fetchone()["charge_count"] == 0


def test_customer_retries_failed_matrix_plan_items(mysql_conn, mysql_app_client):
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"
    headers = auth_headers(mysql_conn, mysql_app_client, "retry-failed")
    account_id = create_xhs_account(mysql_app_client, headers, "retry-failed")
    mark_account_login_ready(mysql_conn, account_id)
    product_id = create_product(mysql_app_client, headers, "retry-failed")
    draft_id = create_confirmed_draft(
        mysql_app_client,
        headers,
        product_id,
        account_id,
        "retry-failed",
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client,
        headers,
        [draft_id],
        account_id,
        "retry-failed",
    )
    confirm = mysql_app_client.post(f"/api/matrix-plans/{plan_id}/confirm", headers=headers)
    assert confirm.status_code == 200

    claim = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": 1, "now_time": 4_000_000_000},
    )
    item_id = claim.json()["data"]["items"][0]["id"]
    failed = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/fail",
        headers={"X-Worker-Token": "worker-secret"},
        json=worker_result_json(
            mysql_conn,
            item_id,
            error_message="temporary upload error",
        ),
    )
    assert failed.status_code == 200

    retry = mysql_app_client.post(
        f"/api/matrix-plans/{plan_id}/retry-failed",
        headers=headers,
    )

    assert retry.status_code == 200
    assert retry.json()["data"]["status"] == 3
    assert retry.json()["data"]["retried_item_count"] == 1
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select status, last_error from matrix_publish_item where id = %s",
            (item_id,),
        )
        item = cursor.fetchone()
        assert item["status"] == 2
        assert item["last_error"] == ""
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 3

    reclaimed = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": 1, "now_time": 4_000_000_000},
    )
    assert reclaimed.status_code == 200
    assert reclaimed.json()["data"]["items"][0]["id"] == item_id


def test_worker_manual_takeover_marks_item_and_plan_failed(mysql_conn, mysql_app_client):
    item_id, plan_id = create_claimed_worker_item(mysql_conn, mysql_app_client, "manual")

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/manual-takeover",
        headers={"X-Worker-Token": "worker-secret"},
        json=worker_result_json(mysql_conn, item_id, reason="login expired"),
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


def test_worker_login_expiry_marks_account_for_reauthentication(
    mysql_conn,
    mysql_app_client,
):
    item_id, plan_id = create_claimed_worker_item(
        mysql_conn,
        mysql_app_client,
        "login-expired",
    )
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select xhs_account_id from matrix_publish_item where id = %s",
            (item_id,),
        )
        account_id = int(cursor.fetchone()["xhs_account_id"])

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/manual-takeover",
        headers={"X-Worker-Token": "worker-secret"},
        json=worker_result_json(
            mysql_conn,
            item_id,
            reason="小红书账号登录已失效，请到账号管理重新扫码登录",
            invalidate_account_login=True,
        ),
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == 6
    assert response.json()["data"]["plan_status"] == 6
    assert response.json()["data"]["account_login_invalidated"] is True
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from xhs_account where id = %s", (account_id,))
        assert cursor.fetchone()["status"] == 2
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 6


def test_worker_security_challenge_marks_account_as_risk(
    mysql_conn,
    mysql_app_client,
):
    item_id, plan_id = create_claimed_worker_item(
        mysql_conn,
        mysql_app_client,
        "security-challenge",
    )
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select xhs_account_id from matrix_publish_item where id = %s",
            (item_id,),
        )
        account_id = int(cursor.fetchone()["xhs_account_id"])

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/manual-takeover",
        headers={"X-Worker-Token": "worker-secret"},
        json=worker_result_json(
            mysql_conn,
            item_id,
            reason="小红书触发安全验证，已暂停该账号自动发布，请人工检查后恢复",
            mark_account_risk=True,
        ),
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == 6
    assert response.json()["data"]["account_marked_risk"] is True
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from xhs_account where id = %s", (account_id,))
        assert cursor.fetchone()["status"] == 4
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 6
        cursor.execute(
            """
            select title, content, priority, business_type, business_id
            from user_notification
            where business_type = 'matrix_publish_item_issue'
              and business_id = %s
            order by id desc
            limit 1
            """,
            (item_id,),
        )
        notification = cursor.fetchone()
        assert notification["title"] == "小红书账号需要人工检查"
        assert "安全验证" in notification["content"]
        assert notification["priority"] == 3


def test_worker_success_updates_account_publish_statistics_and_audit_log(
    mysql_conn,
    mysql_app_client,
):
    item_id, _plan_id = create_claimed_worker_item(
        mysql_conn,
        mysql_app_client,
        "account-statistics",
    )
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select xhs_account_id from matrix_publish_item where id = %s",
            (item_id,),
        )
        account_id = int(cursor.fetchone()["xhs_account_id"])

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/success",
        headers={"X-Worker-Token": "worker-secret"},
        json=worker_result_json(mysql_conn, item_id, message="submitted"),
    )

    assert response.status_code == 200
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select last_publish_time, today_publish_count, publish_count_date
            from xhs_account
            where id = %s
            """,
            (account_id,),
        )
        account = cursor.fetchone()
        assert account["last_publish_time"] > 0
        assert account["today_publish_count"] == 1
        assert len(account["publish_count_date"]) == 10
        cursor.execute(
            """
            select event_type, message
            from matrix_publish_event_log
            where item_id = %s
            order by id desc
            limit 1
            """,
            (item_id,),
        )
        event = cursor.fetchone()
        assert event["event_type"] == "publish_succeeded"
        assert event["message"] == "submitted"


def test_worker_claim_serializes_tasks_for_the_same_account(
    mysql_conn,
    mysql_app_client,
):
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"
    headers = auth_headers(mysql_conn, mysql_app_client, "account-serialization")
    account_id = create_xhs_account(
        mysql_app_client,
        headers,
        "account-serialization",
    )
    mark_account_login_ready(mysql_conn, account_id)
    product_id = create_product(
        mysql_app_client,
        headers,
        "account-serialization",
    )
    draft_ids = [
        create_confirmed_draft(
            mysql_app_client,
            headers,
            product_id,
            account_id,
            f"account-serialization-{index}",
        )
        for index in range(2)
    ]
    plan_id = create_plan_from_drafts(
        mysql_app_client,
        headers,
        draft_ids,
        account_id,
        "account-serialization",
    )
    assert (
        mysql_app_client.post(
            f"/api/matrix-plans/{plan_id}/confirm",
            headers=headers,
        ).status_code
        == 200
    )

    first_claim = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": 2, "now_time": 1_700_086_400},
    )
    second_claim = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": 2, "now_time": 1_700_086_400},
    )

    assert first_claim.status_code == 200
    assert len(first_claim.json()["data"]["items"]) == 1
    assert second_claim.status_code == 200
    assert second_claim.json()["data"]["items"] == []


def test_worker_claim_defers_account_after_daily_limit(
    mysql_conn,
    mysql_app_client,
):
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"
    headers = auth_headers(mysql_conn, mysql_app_client, "daily-limit")
    account_id = create_xhs_account(mysql_app_client, headers, "daily-limit")
    mark_account_login_ready(mysql_conn, account_id)
    now_time = int(time.time())
    from app.services.publish_safety_service import business_date

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            update xhs_account
            set daily_limit = 1,
                today_publish_count = 1,
                publish_count_date = %s
            where id = %s
            """,
            (business_date(now_time), account_id),
        )
    mysql_conn.commit()
    product_id = create_product(mysql_app_client, headers, "daily-limit")
    draft_id = create_confirmed_draft(
        mysql_app_client,
        headers,
        product_id,
        account_id,
        "daily-limit",
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client,
        headers,
        [draft_id],
        account_id,
        "daily-limit",
    )
    assert (
        mysql_app_client.post(
            f"/api/matrix-plans/{plan_id}/confirm",
            headers=headers,
        ).status_code
        == 200
    )

    response = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": 1, "now_time": now_time},
    )

    assert response.status_code == 200
    assert response.json()["data"]["items"] == []
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select status, next_retry_time, last_error
            from matrix_publish_item
            where plan_id = %s
            """,
            (plan_id,),
        )
        item = cursor.fetchone()
        assert item["status"] == 2
        assert item["next_retry_time"] > now_time
        assert "今日发布上限" in item["last_error"]
        cursor.execute(
            """
            select event_type
            from matrix_publish_event_log
            where item_id = (
                select id from matrix_publish_item where plan_id = %s limit 1
            )
            order by id desc
            limit 1
            """,
            (plan_id,),
        )
        assert cursor.fetchone()["event_type"] == "daily_limit_deferred"


def test_worker_claim_defers_account_during_minimum_publish_interval(
    mysql_conn,
    mysql_app_client,
):
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"
    headers = auth_headers(mysql_conn, mysql_app_client, "minimum-interval")
    account_id = create_xhs_account(mysql_app_client, headers, "minimum-interval")
    mark_account_login_ready(mysql_conn, account_id)
    now_time = int(time.time())
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            update xhs_account
            set min_interval_minutes = 60,
                last_publish_time = %s
            where id = %s
            """,
            (now_time - 60, account_id),
        )
    mysql_conn.commit()
    product_id = create_product(mysql_app_client, headers, "minimum-interval")
    draft_id = create_confirmed_draft(
        mysql_app_client,
        headers,
        product_id,
        account_id,
        "minimum-interval",
    )
    plan_id = create_plan_from_drafts(
        mysql_app_client,
        headers,
        [draft_id],
        account_id,
        "minimum-interval",
    )
    assert (
        mysql_app_client.post(
            f"/api/matrix-plans/{plan_id}/confirm",
            headers=headers,
        ).status_code
        == 200
    )

    response = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": 1, "now_time": now_time},
    )

    assert response.status_code == 200
    assert response.json()["data"]["items"] == []
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select status, next_retry_time, last_error
            from matrix_publish_item
            where plan_id = %s
            """,
            (plan_id,),
        )
        item = cursor.fetchone()
        assert item["status"] == 2
        assert item["next_retry_time"] == now_time - 60 + (60 * 60)
        assert "最小发布间隔" in item["last_error"]
        cursor.execute(
            """
            select event_type
            from matrix_publish_event_log
            where item_id = (
                select id from matrix_publish_item where plan_id = %s limit 1
            )
            order by id desc
            limit 1
            """,
            (plan_id,),
        )
        assert cursor.fetchone()["event_type"] == "publish_interval_deferred"


def test_worker_claim_blocks_recent_duplicate_content(
    mysql_conn,
    mysql_app_client,
):
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"
    headers = auth_headers(mysql_conn, mysql_app_client, "duplicate-content")
    account_id = create_xhs_account(mysql_app_client, headers, "duplicate-content")
    mark_account_login_ready(mysql_conn, account_id)
    product_id = create_product(mysql_app_client, headers, "duplicate-content")
    first_draft_id = create_confirmed_draft(
        mysql_app_client,
        headers,
        product_id,
        account_id,
        "duplicate-content-first",
    )
    second_draft_id = create_confirmed_draft(
        mysql_app_client,
        headers,
        product_id,
        account_id,
        "duplicate-content-second",
    )
    first_plan_id = create_plan_from_drafts(
        mysql_app_client,
        headers,
        [first_draft_id],
        account_id,
        "duplicate-content-first",
    )
    second_plan_id = create_plan_from_drafts(
        mysql_app_client,
        headers,
        [second_draft_id],
        account_id,
        "duplicate-content-second",
    )
    now_time = int(time.time())
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select content_fingerprint
            from matrix_publish_item
            where plan_id = %s
            """,
            (first_plan_id,),
        )
        fingerprint = str(cursor.fetchone()["content_fingerprint"])
        cursor.execute(
            """
            update matrix_publish_item
            set status = 4, submitted_time = %s
            where plan_id = %s
            """,
            (now_time - 60, first_plan_id),
        )
        cursor.execute(
            """
            update matrix_publish_plan
            set status = 5
            where id = %s
            """,
            (first_plan_id,),
        )
        cursor.execute(
            """
            update matrix_publish_item
            set content_fingerprint = %s
            where plan_id = %s
            """,
            (fingerprint, second_plan_id),
        )
    mysql_conn.commit()
    assert (
        mysql_app_client.post(
            f"/api/matrix-plans/{second_plan_id}/confirm",
            headers=headers,
        ).status_code
        == 200
    )

    response = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": 1, "now_time": now_time},
    )

    assert response.status_code == 200
    assert response.json()["data"]["items"] == []
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select status, last_error
            from matrix_publish_item
            where plan_id = %s
            """,
            (second_plan_id,),
        )
        item = cursor.fetchone()
        assert item["status"] == 6
        assert "近 7 天" in item["last_error"]
        cursor.execute(
            "select status from matrix_publish_plan where id = %s",
            (second_plan_id,),
        )
        assert cursor.fetchone()["status"] == 6
        cursor.execute(
            """
            select event_type
            from matrix_publish_event_log
            where item_id = (
                select id from matrix_publish_item where plan_id = %s limit 1
            )
            order by id desc
            limit 1
            """,
            (second_plan_id,),
        )
        assert cursor.fetchone()["event_type"] == "duplicate_content_blocked"


def test_worker_success_after_fail_keeps_plan_failed(mysql_conn, mysql_app_client):
    items, plan_id = create_claimed_worker_items(
        mysql_conn,
        mysql_app_client,
        "fail-then-success",
        draft_count=2,
        claim_limit=2,
        now_time=1_700_086_400,
    )

    fail_response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{items[0]['id']}/fail",
        headers={"X-Worker-Token": "worker-secret"},
        json={
            "lease_token": items[0]["lease_token"],
            "error_message": "upload failed",
        },
    )
    assert fail_response.status_code == 200
    assert fail_response.json()["data"]["plan_status"] == 6

    success_response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{items[1]['id']}/success",
        headers={"X-Worker-Token": "worker-secret"},
        json={
            "lease_token": items[1]["lease_token"],
            "message": "submitted",
        },
    )

    assert success_response.status_code == 200
    assert success_response.json()["data"]["status"] == 4
    assert success_response.json()["data"]["plan_status"] == 6
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 6
        cursor.execute(
            "select status from matrix_publish_item where plan_id = %s order by id asc",
            (plan_id,),
        )
        assert [row["status"] for row in cursor.fetchall()] == [5, 4]


def test_worker_success_after_manual_takeover_keeps_plan_failed(mysql_conn, mysql_app_client):
    items, plan_id = create_claimed_worker_items(
        mysql_conn,
        mysql_app_client,
        "manual-then-success",
        draft_count=2,
        claim_limit=2,
        now_time=1_700_086_400,
    )

    manual_response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{items[0]['id']}/manual-takeover",
        headers={"X-Worker-Token": "worker-secret"},
        json={
            "lease_token": items[0]["lease_token"],
            "reason": "login expired",
        },
    )
    assert manual_response.status_code == 200
    assert manual_response.json()["data"]["plan_status"] == 6

    success_response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{items[1]['id']}/success",
        headers={"X-Worker-Token": "worker-secret"},
        json={
            "lease_token": items[1]["lease_token"],
            "message": "submitted",
        },
    )

    assert success_response.status_code == 200
    assert success_response.json()["data"]["status"] == 4
    assert success_response.json()["data"]["plan_status"] == 6
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 6
        cursor.execute(
            "select status from matrix_publish_item where plan_id = %s order by id asc",
            (plan_id,),
        )
        assert [row["status"] for row in cursor.fetchall()] == [6, 4]


def test_worker_result_returns_not_found_for_missing_item(mysql_conn, mysql_app_client):
    mysql_app_client.app.state.config.worker_api_token = "worker-secret"

    response = mysql_app_client.post(
        "/api/worker/matrix-publish-items/999999/success",
        headers={"X-Worker-Token": "worker-secret"},
        json={"lease_token": "missing-item-lease", "message": "submitted"},
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
        json=worker_result_json(mysql_conn, item_id, error_message="upload failed"),
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


def test_retryable_worker_failure_is_requeued_with_backoff(
    mysql_conn,
    mysql_app_client,
):
    item_id, plan_id = create_claimed_worker_item(
        mysql_conn,
        mysql_app_client,
        "automatic-retry",
    )
    first_lease = worker_result_json(mysql_conn, item_id)["lease_token"]

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/fail",
        headers={"X-Worker-Token": "worker-secret"},
        json={
            "lease_token": first_lease,
            "error_message": "creator page temporarily unavailable",
            "retryable": True,
            "retry_delay_seconds": 120,
        },
    )

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == 2
    assert result["plan_status"] == 4
    assert result["retry_scheduled"] is True
    assert result["next_retry_time"] > 0

    before_retry = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": 1, "now_time": result["next_retry_time"] - 1},
    )
    assert before_retry.status_code == 200
    assert before_retry.json()["data"]["items"] == []

    after_retry = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": 1, "now_time": result["next_retry_time"]},
    )
    assert after_retry.status_code == 200
    retried_item = after_retry.json()["data"]["items"][0]
    assert retried_item["id"] == item_id
    assert retried_item["attempt_count"] == 2
    assert retried_item["lease_token"] != first_lease

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select status, attempt_count, next_retry_time
            from matrix_publish_item
            where id = %s
            """,
            (item_id,),
        )
        item = cursor.fetchone()
        assert item["status"] == 3
        assert item["attempt_count"] == 2
        assert item["next_retry_time"] == 0
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 4


def test_retryable_worker_failure_stops_after_max_attempts(
    mysql_conn,
    mysql_app_client,
):
    item_id, plan_id = create_claimed_worker_item(
        mysql_conn,
        mysql_app_client,
        "retry-limit",
    )
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "update matrix_publish_item set max_attempts = 1 where id = %s",
            (item_id,),
        )
    mysql_conn.commit()

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/fail",
        headers={"X-Worker-Token": "worker-secret"},
        json=worker_result_json(
            mysql_conn,
            item_id,
            error_message="network timeout",
            retryable=True,
            retry_delay_seconds=60,
        ),
    )

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == 5
    assert result["plan_status"] == 6
    assert result["retry_scheduled"] is False
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 6


def test_worker_result_rejects_stale_lease_token(mysql_conn, mysql_app_client):
    item_id, _plan_id = create_claimed_worker_item(
        mysql_conn,
        mysql_app_client,
        "stale-lease",
    )

    response = mysql_app_client.post(
        f"/api/worker/matrix-publish-items/{item_id}/success",
        headers={"X-Worker-Token": "worker-secret"},
        json={"lease_token": "wrong-lease-token", "message": "submitted"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "publish item lease has expired"
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select status from matrix_publish_item where id = %s",
            (item_id,),
        )
        assert cursor.fetchone()["status"] == 3


def test_expired_worker_lease_moves_item_to_manual_takeover(
    mysql_conn,
    mysql_app_client,
):
    item_id, plan_id = create_claimed_worker_item(
        mysql_conn,
        mysql_app_client,
        "expired-lease",
    )
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            update matrix_publish_item
            set lease_expires_time = 1, update_time = 1
            where id = %s
            """,
            (item_id,),
        )
    mysql_conn.commit()

    response = mysql_app_client.post(
        "/api/worker/matrix-publish-items/claim",
        headers={"X-Worker-Token": "worker-secret"},
        json={"limit": 1, "now_time": 1_700_000_000},
    )

    assert response.status_code == 200
    assert response.json()["data"]["items"] == []
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select status, last_error, lease_token from matrix_publish_item where id = %s",
            (item_id,),
        )
        item = cursor.fetchone()
        assert item["status"] == 6
        assert "执行中断" in item["last_error"]
        assert item["lease_token"] == ""
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert cursor.fetchone()["status"] == 6
