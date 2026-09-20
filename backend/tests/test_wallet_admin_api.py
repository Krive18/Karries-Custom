import pytest
from fastapi import HTTPException

import time
from datetime import datetime

from app.core.security import create_access_token
from app.repositories.user_repository import UserRepository
from app.repositories.wallet_repository import BUSINESS_TIMEZONE


def auth_headers(mysql_conn, mysql_app_client, suffix="wallet", initial_credits=0) -> dict[str, str]:
    invite_code = f"INV-WALLET-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=initial_credits,
        max_uses=1,
        expires_time=0,
        remark="wallet-admin-api",
    )

    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": f"wallet_user_{suffix}",
            "nickname": f"Wallet User {suffix}",
            "password": "matrix-secret",
            "invite_code": invite_code,
        },
    )

    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def admin_headers(mysql_conn, mysql_app_client, suffix="admin") -> dict[str, str]:
    admin_id = UserRepository(mysql_conn).create_user(
        login_name=f"client_owner_{suffix}",
        nickname="Client Owner",
        password_hash="not-used-by-token-auth",
        user_role="client_owner",
        invite_code="",
    )
    token = create_access_token(
        {"user_id": admin_id, "tenant_id": 1, "role": "client_owner"},
        mysql_app_client.app.state.config.auth.token_secret,
        mysql_app_client.app.state.config.auth.access_token_seconds,
    )
    return {"Authorization": f"Bearer {token}"}


def test_wallet_api_returns_balance_and_ledger(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, suffix="balance", initial_credits=33)

    response = mysql_app_client.get("/api/wallet", headers=headers)
    ledger = mysql_app_client.get("/api/wallet/ledger", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["balance"] == 1533
    assert response.json()["data"]["total_recharged"] == 1533
    assert ledger.status_code == 200
    rows = ledger.json()["data"]
    assert len(rows) == 2
    assert rows[0]["business_type"] == "membership_monthly"
    assert rows[0]["change_amount"] == 1500
    assert rows[1]["business_type"] == "invite_bonus"
    assert rows[1]["change_amount"] == 33


def test_billing_catalog_and_default_pro_membership(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, suffix="membership", initial_credits=18)

    plans = mysql_app_client.get("/api/wallet/membership-plans", headers=headers)
    membership = mysql_app_client.get("/api/wallet/membership", headers=headers)
    packages = mysql_app_client.get("/api/wallet/recharge-packages", headers=headers)

    assert plans.status_code == 200
    assert [
        (item["plan_code"], item["price_cent"])
        for item in plans.json()["data"]
    ] == [
        ("free", 0),
        ("pro", 19900),
        ("max", 29900),
        ("storage", 59900),
    ]
    plan_rows = {
        item["plan_code"]: item
        for item in plans.json()["data"]
    }
    assert "全部核心功能均可使用" in plan_rows["pro"]["summary"]
    assert "平台全部核心功能" in plan_rows["pro"]["features"]
    assert "包含 Pro 会员全部功能" in plan_rows["max"]["features"]
    assert plan_rows["max"]["storage_gb"] == 180
    assert "包含 Pro 会员全部功能" in plan_rows["storage"]["features"]
    assert plan_rows["storage"]["storage_gb"] == 1000
    assert membership.status_code == 200
    assert membership.json()["data"]["plan"]["plan_code"] == "pro"
    assert membership.json()["data"]["plan"]["monthly_credits"] == 1500
    assert membership.json()["data"]["plan"]["daily_checkin_credits"] == 20
    assert membership.json()["data"]["plan"]["storage_gb"] == 100
    assert membership.json()["data"]["expire_time"] == 0
    assert packages.status_code == 200
    package_rows = packages.json()["data"]
    assert len(package_rows) == 4
    assert [
        (item["price_cent"], item["base_credits"], item["credits"])
        for item in package_rows
    ] == [
        (100000, 20000, 20000),
        (200000, 40000, 40000),
        (500000, 100000, 110000),
        (1000000, 200000, 220000),
    ]

    wallet = mysql_app_client.get("/api/wallet", headers=headers).json()["data"]
    assert wallet["balance"] == 1518

    membership_again = mysql_app_client.get("/api/wallet/membership", headers=headers)
    wallet_again = mysql_app_client.get("/api/wallet", headers=headers).json()["data"]
    assert membership_again.status_code == 200
    assert wallet_again["balance"] == 1518


def test_unused_monthly_membership_credits_expire_without_touching_other_credits(
    mysql_conn,
    mysql_app_client,
):
    headers = auth_headers(
        mysql_conn,
        mysql_app_client,
        suffix="monthly-expiry",
        initial_credits=500,
    )
    user = UserRepository(mysql_conn).get_by_login_name(
        "wallet_user_monthly-expiry"
    )
    user_id = int(user["id"])
    first_wallet = mysql_app_client.get("/api/wallet", headers=headers).json()["data"]
    assert first_wallet["balance"] == 2000

    from app.repositories.wallet_repository import WalletRepository

    WalletRepository(mysql_conn).adjust_credits(
        user_id,
        -200,
        "test_consumption",
        1,
        "测试消耗",
    )
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            update membership_monthly_credit_grant
            set grant_month = '2000-01'
            where user_id = %s
            """,
            (user_id,),
        )
    mysql_conn.commit()

    rolled_over = mysql_app_client.get("/api/wallet", headers=headers)

    assert rolled_over.status_code == 200
    assert rolled_over.json()["data"]["balance"] == 2000
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select change_amount
            from credit_ledger
            where user_id = %s and business_type = 'membership_expiry'
            order by id desc limit 1
            """,
            (user_id,),
        )
        expiry = cursor.fetchone()
        cursor.execute(
            """
            select remaining_credits, expired_credits
            from membership_monthly_credit_grant
            where user_id = %s and grant_month = '2000-01'
            """,
            (user_id,),
        )
        previous_grant = cursor.fetchone()
    assert int(expiry["change_amount"]) == -1300
    assert int(previous_grant["remaining_credits"]) == 0
    assert int(previous_grant["expired_credits"]) == 1300


def test_recharge_application_does_not_credit_wallet_before_payment(
    mysql_conn,
    mysql_app_client,
):
    headers = auth_headers(mysql_conn, mysql_app_client, suffix="recharge", initial_credits=18)

    before = mysql_app_client.get("/api/wallet", headers=headers).json()["data"]
    response = mysql_app_client.post(
        "/api/wallet/recharge-orders",
        headers=headers,
        json={
            "recharge_type": "online",
            "amount_cent": 5000,
            "payment_channel": "alipay",
        },
    )
    after = mysql_app_client.get("/api/wallet", headers=headers).json()["data"]
    orders = mysql_app_client.get("/api/wallet/recharge-orders", headers=headers)

    assert response.status_code == 200
    order = response.json()["data"]
    assert order["amount_cent"] == 5000
    assert order["requested_credits"] == 1000
    assert order["status"] == 1
    assert before["balance"] == after["balance"] == 1518
    assert orders.status_code == 200
    assert orders.json()["data"][0]["order_no"] == order["order_no"]


def test_package_recharge_application_uses_catalog_amount_and_credits(
    mysql_conn,
    mysql_app_client,
):
    headers = auth_headers(mysql_conn, mysql_app_client, suffix="package")
    package = mysql_app_client.get(
        "/api/wallet/recharge-packages",
        headers=headers,
    ).json()["data"][2]

    response = mysql_app_client.post(
        "/api/wallet/recharge-orders",
        headers=headers,
        json={
            "recharge_type": "package",
            "package_id": package["id"],
            "amount_cent": 0,
            "payment_channel": "wechat",
        },
    )

    assert response.status_code == 200
    order = response.json()["data"]
    assert order["package_name"] == package["package_name"]
    assert order["amount_cent"] == package["price_cent"]
    assert order["requested_credits"] == package["credits"]
    assert order["status"] == 1


def test_qr_recharge_requires_proof_and_manager_verification(
    mysql_conn,
    mysql_app_client,
):
    customer_headers = auth_headers(
        mysql_conn,
        mysql_app_client,
        suffix="proof-confirm",
        initial_credits=18,
    )
    manager_headers = admin_headers(
        mysql_conn,
        mysql_app_client,
        suffix="proof-confirm",
    )
    wallet_before = mysql_app_client.get(
        "/api/wallet",
        headers=customer_headers,
    ).json()["data"]
    created = mysql_app_client.post(
        "/api/wallet/recharge-orders",
        headers=customer_headers,
        json={
            "recharge_type": "online",
            "amount_cent": 5000,
            "payment_channel": "alipay",
        },
    )
    assert created.status_code == 200
    order = created.json()["data"]

    confirm_without_proof = mysql_app_client.post(
        f"/api/admin/billing/recharge-orders/{order['id']}/confirm",
        headers=manager_headers,
    )
    assert confirm_without_proof.status_code == 409

    proof_bytes = b"\x89PNG\r\n\x1a\n" + b"verified-payment-proof"
    submitted = mysql_app_client.post(
        f"/api/wallet/recharge-orders/{order['id']}/payment-proof",
        headers=customer_headers,
        data={"payer_note": "张三 支付宝尾号 1234"},
        files={"proof": ("proof.png", proof_bytes, "image/png")},
    )
    assert submitted.status_code == 200
    submitted_order = submitted.json()["data"]
    assert submitted_order["status"] == 2
    assert submitted_order["payer_note"] == "张三 支付宝尾号 1234"
    assert submitted_order["has_payment_proof"] is True
    assert submitted_order["proof_file_name"] == "proof.png"
    assert "proof_file_path" not in submitted_order

    customer_proof = mysql_app_client.get(
        f"/api/wallet/recharge-orders/{order['id']}/payment-proof",
        headers=customer_headers,
    )
    manager_proof = mysql_app_client.get(
        f"/api/admin/billing/recharge-orders/{order['id']}/payment-proof",
        headers=manager_headers,
    )
    assert customer_proof.status_code == 200
    assert customer_proof.content == proof_bytes
    assert manager_proof.status_code == 200
    assert manager_proof.content == proof_bytes

    wallet_pending = mysql_app_client.get(
        "/api/wallet",
        headers=customer_headers,
    ).json()["data"]
    assert wallet_pending["balance"] == wallet_before["balance"]

    confirmed = mysql_app_client.post(
        f"/api/admin/billing/recharge-orders/{order['id']}/confirm",
        headers=manager_headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == 6

    wallet_after = mysql_app_client.get(
        "/api/wallet",
        headers=customer_headers,
    ).json()["data"]
    assert wallet_after["balance"] == wallet_before["balance"]

    confirmed_again = mysql_app_client.post(
        f"/api/admin/billing/recharge-orders/{order['id']}/confirm",
        headers=manager_headers,
    )
    wallet_after_again = mysql_app_client.get(
        "/api/wallet",
        headers=customer_headers,
    ).json()["data"]
    assert confirmed_again.status_code == 200
    assert wallet_after_again["balance"] == wallet_after["balance"]


def test_manager_can_reject_payment_proof_without_crediting_wallet(
    mysql_conn,
    mysql_app_client,
):
    customer_headers = auth_headers(
        mysql_conn,
        mysql_app_client,
        suffix="proof-reject",
        initial_credits=18,
    )
    manager_headers = admin_headers(
        mysql_conn,
        mysql_app_client,
        suffix="proof-reject",
    )
    wallet_before = mysql_app_client.get(
        "/api/wallet",
        headers=customer_headers,
    ).json()["data"]
    order = mysql_app_client.post(
        "/api/wallet/recharge-orders",
        headers=customer_headers,
        json={
            "recharge_type": "online",
            "amount_cent": 1000,
            "payment_channel": "wechat",
        },
    ).json()["data"]
    proof_bytes = b"\x89PNG\r\n\x1a\n" + b"rejected-payment-proof"
    submitted = mysql_app_client.post(
        f"/api/wallet/recharge-orders/{order['id']}/payment-proof",
        headers=customer_headers,
        data={"payer_note": "李四 微信尾号 5678"},
        files={"proof": ("proof.png", proof_bytes, "image/png")},
    )
    assert submitted.status_code == 200

    rejected = mysql_app_client.post(
        f"/api/admin/billing/recharge-orders/{order['id']}/reject",
        headers=manager_headers,
        json={"reason": "付款金额与订单金额不一致"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["data"]["status"] == 5
    assert rejected.json()["data"]["remark"] == "付款金额与订单金额不一致"

    confirm_rejected = mysql_app_client.post(
        f"/api/admin/billing/recharge-orders/{order['id']}/confirm",
        headers=manager_headers,
    )
    assert confirm_rejected.status_code == 409
    wallet_after = mysql_app_client.get(
        "/api/wallet",
        headers=customer_headers,
    ).json()["data"]
    assert wallet_after["balance"] == wallet_before["balance"]

    resubmitted = mysql_app_client.post(
        f"/api/wallet/recharge-orders/{order['id']}/payment-proof",
        headers=customer_headers,
        data={"payer_note": "李四 微信尾号 5678，已核对金额"},
        files={
            "proof": (
                "proof-corrected.png",
                b"\x89PNG\r\n\x1a\n" + b"corrected-payment-proof",
                "image/png",
            )
        },
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["data"]["status"] == 2
    assert resubmitted.json()["data"]["remark"] == ""
    assert resubmitted.json()["data"]["proof_file_name"] == "proof-corrected.png"


def test_expired_paid_membership_reverts_to_default_plan(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, suffix="expire-revert")
    user = UserRepository(mysql_conn).get_by_login_name("wallet_user_expire-revert")
    user_id = int(user["id"])
    tenant_id = int(user["tenant_id"])
    now = int(time.time())
    grant_month = datetime.now(BUSINESS_TIMEZONE).strftime("%Y-%m")
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select id from membership_plan where plan_code = 'max' limit 1"
        )
        max_plan_id = int(cursor.fetchone()["id"])
        cursor.execute(
            """
            insert into user_membership (
                tenant_id, user_id, plan_id, status, start_time,
                expire_time, auto_renew, create_time, update_time
            ) values (%s, %s, %s, 1, %s, %s, 0, %s, %s)
            """,
            (
                tenant_id,
                user_id,
                max_plan_id,
                now - 40 * 86400,
                now - 60,
                now - 40 * 86400,
                now - 40 * 86400,
            ),
        )
        membership_id = int(cursor.lastrowid)
        cursor.execute(
            """
            insert into membership_monthly_credit_grant (
                tenant_id, user_id, membership_id, grant_month, credits,
                remaining_credits, expired_credits, expired_time, create_time
            ) values (%s, %s, %s, %s, 4000, 4000, 0, 0, %s)
            """,
            (tenant_id, user_id, membership_id, grant_month, now),
        )
    mysql_conn.commit()

    response = mysql_app_client.get("/api/wallet/membership", headers=headers)

    assert response.status_code == 200
    membership = response.json()["data"]
    assert membership["plan"]["plan_code"] == "pro"
    assert membership["status"] == 1
    assert membership["expire_time"] == 0
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select credits
            from membership_monthly_credit_grant
            where user_id = %s
            """,
            (user_id,),
        )
        grants = cursor.fetchall()
        cursor.execute(
            """
            select count(*) as total
            from credit_ledger
            where user_id = %s and business_type = 'membership_monthly'
            """,
            (user_id,),
        )
        monthly_ledger_count = int(cursor.fetchone()["total"])
    assert len(grants) == 1
    assert int(grants[0]["credits"]) == 4000
    assert monthly_ledger_count == 0


def test_active_paid_membership_is_not_reverted(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, suffix="expire-active")
    user = UserRepository(mysql_conn).get_by_login_name("wallet_user_expire-active")
    user_id = int(user["id"])
    tenant_id = int(user["tenant_id"])
    now = int(time.time())
    expire_time = now + 30 * 86400
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select id from membership_plan where plan_code = 'max' limit 1"
        )
        max_plan_id = int(cursor.fetchone()["id"])
        cursor.execute(
            """
            insert into user_membership (
                tenant_id, user_id, plan_id, status, start_time,
                expire_time, auto_renew, create_time, update_time
            ) values (%s, %s, %s, 1, %s, %s, 0, %s, %s)
            """,
            (tenant_id, user_id, max_plan_id, now, expire_time, now, now),
        )
    mysql_conn.commit()

    response = mysql_app_client.get("/api/wallet/membership", headers=headers)

    assert response.status_code == 200
    membership = response.json()["data"]
    assert membership["plan"]["plan_code"] == "max"
    assert membership["status"] == 1
    assert membership["expire_time"] == expire_time


def test_daily_checkin_awards_once_per_business_date(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, suffix="checkin", initial_credits=18)

    status = mysql_app_client.get("/api/wallet/check-in", headers=headers)
    first = mysql_app_client.post("/api/wallet/check-in", headers=headers)
    second = mysql_app_client.post("/api/wallet/check-in", headers=headers)
    wallet = mysql_app_client.get("/api/wallet", headers=headers).json()["data"]
    ledger = mysql_app_client.get("/api/wallet/ledger", headers=headers).json()["data"]

    assert status.status_code == 200
    assert status.json()["data"]["checked_in"] is False
    assert status.json()["data"]["credits"] == 20
    assert first.status_code == 200
    assert first.json()["data"]["already_checked_in"] is False
    assert first.json()["data"]["balance"] == 1538
    assert second.status_code == 200
    assert second.json()["data"]["already_checked_in"] is True
    assert second.json()["data"]["balance"] == 1538
    assert wallet["balance"] == 1538
    assert len([item for item in ledger if item["business_type"] == "daily_checkin"]) == 1


def test_wallet_requires_auth(app_client_without_db):
    response = app_client_without_db.get("/api/wallet")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_admin_summary_rejects_customer_without_database_connection():
    from app.core.dependencies import require_management_user

    with pytest.raises(HTTPException) as exc:
        require_management_user(user={"id": 5, "user_role": "customer"})

    assert exc.value.status_code == 403


def test_admin_summary_requires_management_role(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, suffix="admin-denied")

    response = mysql_app_client.get("/api/admin/summary", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_summary_returns_tenant_counts(mysql_conn, mysql_app_client):
    auth_headers(mysql_conn, mysql_app_client, suffix="admin-customer")
    headers = admin_headers(mysql_conn, mysql_app_client, suffix="summary")

    response = mysql_app_client.get("/api/admin/summary", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["total_users"] == 1
    assert payload["data"]["total_xhs_accounts"] == 0
    assert payload["data"]["total_matrix_plans"] == 0


def test_admin_summary_scopes_all_counts_to_the_manager_tenant(mysql_conn, mysql_app_client):
    repository = UserRepository(mysql_conn)
    manager_id = repository.create_user(
        login_name="tenant_manager",
        nickname="Tenant Manager",
        password_hash="not-used-by-token-auth",
        user_role="client_owner",
        invite_code="",
        tenant_id=20,
    )
    tenant_user_id = repository.create_user(
        login_name="tenant_customer",
        nickname="Tenant Customer",
        password_hash="not-used-by-token-auth",
        user_role="customer",
        invite_code="",
        tenant_id=20,
    )
    other_user_id = repository.create_user(
        login_name="other_customer",
        nickname="Other Customer",
        password_hash="not-used-by-token-auth",
        user_role="customer",
        invite_code="",
        tenant_id=21,
    )
    with mysql_conn.cursor() as cursor:
        for user_id, suffix in ((tenant_user_id, "tenant"), (other_user_id, "other")):
            cursor.execute(
                """
                insert into xhs_account (
                    user_id, display_name, account_group, status, daily_limit,
                    min_interval_minutes, last_publish_time, today_publish_count,
                    login_state_path, create_time, update_time
                ) values (%s, %s, '', 1, 1, 360, 0, 0, '', 1, 1)
                """,
                (user_id, f"account-{suffix}"),
            )
            cursor.execute(
                """
                insert into matrix_publish_plan (
                    user_id, plan_name, source_type, content_type, product_id, status,
                    schedule_start_time, schedule_end_time, scheduling_rule_json,
                    create_time, update_time
                ) values (%s, %s, 'temporary_material', 'video', 0, 1, 0, 0, '{}', 1, 1)
                """,
                (user_id, f"plan-{suffix}"),
            )
            cursor.execute(
                """
                insert into video_edit_job (
                    user_id, job_title, post_body, script_text, requirement_text, material_json, status,
                    expected_delivery_time, operator_user_id, developer_note, delivery_json,
                    delivered_time, create_time, update_time
                ) values (%s, %s, '', 'script', '', '[]', 1, 2, 0, '', '{}', 0, 1, 1)
                """,
                (user_id, f"job-{suffix}"),
            )
    mysql_conn.commit()
    token = create_access_token(
        {"user_id": manager_id, "role": "client_owner"},
        mysql_app_client.app.state.config.auth.token_secret,
        mysql_app_client.app.state.config.auth.access_token_seconds,
    )

    response = mysql_app_client.get("/api/admin/summary", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["data"] == {
        "total_users": 1,
        "total_xhs_accounts": 1,
        "total_matrix_plans": 1,
        "total_video_edit_jobs": 1,
        "pending_video_edit_jobs": 1,
    }
