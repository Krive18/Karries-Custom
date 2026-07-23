import pytest
from fastapi import HTTPException

from app.core.security import create_access_token
from app.repositories.user_repository import UserRepository


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
        login_name=f"platform_admin_{suffix}",
        nickname="Platform Admin",
        password_hash="not-used-by-token-auth",
        user_role="platform_admin",
        invite_code="",
    )
    token = create_access_token(
        {"user_id": admin_id, "role": "platform_admin"},
        mysql_app_client.app.state.config.auth.token_secret,
        mysql_app_client.app.state.config.auth.access_token_seconds,
    )
    return {"Authorization": f"Bearer {token}"}


def test_wallet_api_returns_balance_and_ledger(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, suffix="balance", initial_credits=33)

    response = mysql_app_client.get("/api/wallet", headers=headers)
    ledger = mysql_app_client.get("/api/wallet/ledger", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["balance"] == 33
    assert response.json()["data"]["total_recharged"] == 33
    assert ledger.status_code == 200
    rows = ledger.json()["data"]
    assert len(rows) == 1
    assert rows[0]["business_type"] == "invite_bonus"
    assert rows[0]["change_amount"] == 33


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


def test_admin_summary_returns_platform_counts(mysql_conn, mysql_app_client):
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
                    user_id, job_title, script_text, requirement_text, material_json, status,
                    expected_delivery_time, operator_user_id, developer_note, delivery_json,
                    delivered_time, create_time, update_time
                ) values (%s, %s, 'script', '', '[]', 1, 2, 0, '', '{}', 0, 1, 1)
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
