import json

from app.core.security import create_access_token, hash_password
from app.repositories.user_repository import UserRepository


def create_portal_user(
    mysql_conn,
    *,
    login_name: str,
    password: str,
    user_role: str,
    tenant_id: int,
) -> int:
    return UserRepository(mysql_conn).create_user(
        login_name=login_name,
        nickname=login_name,
        password_hash=hash_password(password),
        user_role=user_role,
        invite_code="",
        tenant_id=tenant_id,
    )


def login_headers(
    mysql_app_client,
    portal: str,
    login_name: str,
    password: str,
) -> dict[str, str]:
    response = mysql_app_client.post(
        f"/api/auth/{portal}/login",
        json={"login_name": login_name, "password": password},
    )
    assert response.status_code == 200
    return {
        "Authorization": f"Bearer {response.json()['data']['access_token']}",
    }


def manager_headers(
    mysql_conn,
    mysql_app_client,
    *,
    role: str = "client_owner",
    tenant_id: int = 101,
) -> dict[str, str]:
    login_name = f"manager_{role}_{tenant_id}"
    create_portal_user(
        mysql_conn,
        login_name=login_name,
        password="manager-password",
        user_role=role,
        tenant_id=tenant_id,
    )
    return login_headers(
        mysql_app_client,
        "manager",
        login_name,
        "manager-password",
    )


def test_manager_creates_employee_that_can_login_customer_portal(
    mysql_conn,
    mysql_app_client,
):
    headers = manager_headers(mysql_conn, mysql_app_client)

    response = mysql_app_client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "login_name": "new_employee",
            "nickname": "新员工",
            "password": "employee-password",
            "status": 1,
        },
    )

    assert response.status_code == 200
    employee = response.json()["data"]
    assert employee["tenant_id"] == 101
    assert employee["user_role"] == "customer"
    assert employee["wallet_balance"] == 0
    assert "password" not in str(employee).lower()

    login = mysql_app_client.post(
        "/api/auth/customer/login",
        json={
            "login_name": "new_employee",
            "password": "employee-password",
        },
    )
    assert login.status_code == 200

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select tenant_id, action, detail_json
            from admin_audit_log
            where target_id = %s
            """,
            (employee["id"],),
        )
        audit = cursor.fetchone()
    assert audit["tenant_id"] == 101
    assert audit["action"] == "employee.create"
    assert "password" not in json.dumps(audit["detail_json"]).lower()


def test_client_admin_cannot_enter_owner_management_portal(
    mysql_conn,
    mysql_app_client,
):
    create_portal_user(
        mysql_conn,
        login_name="legacy_client_admin",
        password="manager-password",
        user_role="client_admin",
        tenant_id=101,
    )

    response = mysql_app_client.post(
        "/api/auth/manager/login",
        json={
            "login_name": "legacy_client_admin",
            "password": "manager-password",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PORTAL_FORBIDDEN"


def test_create_employee_rejects_duplicate_and_short_password(
    mysql_conn,
    mysql_app_client,
):
    headers = manager_headers(mysql_conn, mysql_app_client)
    payload = {
        "login_name": "duplicate_employee",
        "nickname": "重复员工",
        "password": "employee-password",
        "status": 1,
    }

    first = mysql_app_client.post(
        "/api/admin/users",
        headers=headers,
        json=payload,
    )
    duplicate = mysql_app_client.post(
        "/api/admin/users",
        headers=headers,
        json=payload,
    )
    short_password = mysql_app_client.post(
        "/api/admin/users",
        headers=headers,
        json={
            **payload,
            "login_name": "short_password",
            "password": "short",
        },
    )

    assert first.status_code == 200
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "USER_EXISTS"
    assert short_password.status_code == 422
    assert UserRepository(mysql_conn).get_by_login_name("short_password") is None


def test_manager_can_disable_and_reset_employee_password(
    mysql_conn,
    mysql_app_client,
):
    headers = manager_headers(mysql_conn, mysql_app_client)
    employee = mysql_app_client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "login_name": "managed_employee",
            "nickname": "受管员工",
            "password": "employee-password",
            "status": 1,
        },
    ).json()["data"]
    first_login = mysql_app_client.post(
        "/api/auth/customer/login",
        json={
            "login_name": "managed_employee",
            "password": "employee-password",
        },
    )
    old_headers = {
        "Authorization": (
            f"Bearer {first_login.json()['data']['access_token']}"
        ),
    }

    reset = mysql_app_client.put(
        f"/api/admin/users/{employee['id']}/password",
        headers=headers,
        json={"password": "new-employee-password"},
    )
    old_login = mysql_app_client.post(
        "/api/auth/customer/login",
        json={
            "login_name": "managed_employee",
            "password": "employee-password",
        },
    )
    new_login = mysql_app_client.post(
        "/api/auth/customer/login",
        json={
            "login_name": "managed_employee",
            "password": "new-employee-password",
        },
    )
    old_session = mysql_app_client.get("/api/auth/me", headers=old_headers)
    disabled = mysql_app_client.patch(
        f"/api/admin/users/{employee['id']}/status",
        headers=headers,
        json={"status": 2},
    )
    disabled_login = mysql_app_client.post(
        "/api/auth/customer/login",
        json={
            "login_name": "managed_employee",
            "password": "new-employee-password",
        },
    )

    assert reset.status_code == 200
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    assert old_session.status_code == 401
    assert disabled.status_code == 200
    assert disabled.json()["data"]["status"] == 2
    assert disabled_login.status_code == 401


def test_owner_can_edit_employee_and_view_summary_and_detail(
    mysql_conn,
    mysql_app_client,
):
    headers = manager_headers(mysql_conn, mysql_app_client)
    employee = mysql_app_client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "login_name": "editable_employee",
            "nickname": "待修改员工",
            "password": "employee-password",
            "status": 1,
        },
    ).json()["data"]

    updated = mysql_app_client.patch(
        f"/api/admin/users/{employee['id']}",
        headers=headers,
        json={
            "login_name": "updated_employee",
            "nickname": "已修改员工",
        },
    )
    detail = mysql_app_client.get(
        f"/api/admin/users/{employee['id']}",
        headers=headers,
    )
    summary = mysql_app_client.get(
        "/api/admin/users/summary",
        headers=headers,
    )

    assert updated.status_code == 200
    assert updated.json()["data"]["login_name"] == "updated_employee"
    assert detail.status_code == 200
    assert detail.json()["data"]["nickname"] == "已修改员工"
    assert detail.json()["data"]["xhs_account_count"] == 0
    assert detail.json()["data"]["publish_plan_count"] == 0
    assert detail.json()["data"]["inspiration_session_count"] == 0
    assert detail.json()["data"]["viral_analysis_count"] == 0
    assert summary.status_code == 200
    assert summary.json()["data"]["total"] == 1
    assert summary.json()["data"]["active"] == 1


def test_manager_cannot_reset_employee_from_another_tenant(
    mysql_conn,
    mysql_app_client,
):
    headers = manager_headers(mysql_conn, mysql_app_client, tenant_id=101)
    other_id = create_portal_user(
        mysql_conn,
        login_name="other_tenant_employee",
        password="employee-password",
        user_role="customer",
        tenant_id=202,
    )

    response = mysql_app_client.put(
        f"/api/admin/users/{other_id}/password",
        headers=headers,
        json={"password": "new-employee-password"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EMPLOYEE_NOT_FOUND"


def test_customer_cannot_manage_employees(mysql_conn, mysql_app_client):
    create_portal_user(
        mysql_conn,
        login_name="customer_operator",
        password="customer-password",
        user_role="customer",
        tenant_id=101,
    )
    headers = login_headers(
        mysql_app_client,
        "customer",
        "customer_operator",
        "customer-password",
    )

    response = mysql_app_client.get("/api/admin/users", headers=headers)

    assert response.status_code == 403


def test_manager_third_employee_requires_developer_approval(
    mysql_conn,
    mysql_app_client,
):
    tenant_id = 303
    headers = manager_headers(
        mysql_conn,
        mysql_app_client,
        tenant_id=tenant_id,
    )
    for index in range(2):
        created = mysql_app_client.post(
            "/api/admin/users",
            headers=headers,
            json={
                "login_name": f"quota_employee_{index}",
                "nickname": f"额度员工 {index}",
                "password": "employee-password",
                "status": 1,
            },
        )
        assert created.status_code == 200

    pending = mysql_app_client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "login_name": "quota_employee_2",
            "nickname": "待审核员工",
            "password": "employee-password",
            "status": 1,
        },
    )

    assert pending.status_code == 202
    request_row = pending.json()["data"]
    assert request_row["approval_required"] is True
    assert request_row["status"] == "pending"
    assert UserRepository(mysql_conn).get_by_login_name("quota_employee_2") is None
    assert "password" not in str(request_row).lower()

    developer_id = create_portal_user(
        mysql_conn,
        login_name="quota_reviewer",
        password="developer-password",
        user_role="developer_admin",
        tenant_id=0,
    )
    developer_token = create_access_token(
        {
            "user_id": developer_id,
            "tenant_id": 0,
            "role": "developer_admin",
            "auth_version": 1,
        },
        mysql_app_client.app.state.config.auth.token_secret,
        mysql_app_client.app.state.config.auth.access_token_seconds,
    )
    approved = mysql_app_client.post(
        (
            "/api/developer/platform/user-creation-requests/"
            f"{request_row['id']}/approve"
        ),
        headers={"Authorization": f"Bearer {developer_token}"},
        json={"reason": "已核实客户扩容需求"},
    )

    assert approved.status_code == 200
    approved_data = approved.json()["data"]
    assert approved_data["status"] == "approved"
    assert approved_data["approved_user_id"] > 0
    created_user = UserRepository(mysql_conn).get_by_login_name("quota_employee_2")
    assert created_user is not None
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select balance from credit_wallet where user_id = %s",
            (created_user["id"],),
        )
        wallet = cursor.fetchone()
        cursor.execute(
            "select count(*) as total from membership_monthly_credit_grant where user_id = %s",
            (created_user["id"],),
        )
        grants = int(cursor.fetchone()["total"])
    assert int(wallet["balance"]) == 0
    assert grants == 0
