import time

from app.core.security import hash_password
from app.repositories.user_repository import UserRepository


def create_user(mysql_conn, *, login_name: str, password: str, role: str, tenant_id: int) -> int:
    return UserRepository(mysql_conn).create_user(
        login_name=login_name,
        nickname=login_name,
        password_hash=hash_password(password),
        user_role=role,
        invite_code="",
        tenant_id=tenant_id,
    )


def login(mysql_app_client, portal: str, login_name: str, password: str) -> dict[str, str]:
    response = mysql_app_client.post(
        f"/api/auth/{portal}/login",
        json={"login_name": login_name, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def seed_operations_data(mysql_conn, user_id: int) -> tuple[int, int]:
    now = int(time.time())
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            insert into xhs_account (
                user_id, display_name, account_group, status, daily_limit,
                min_interval_minutes, last_publish_time, today_publish_count,
                login_state_path, create_time, update_time
            )
            values (%s, '品牌主号', '品牌矩阵', 1, 3, 180, %s, 1, 'state.json', %s, %s)
            """,
            (user_id, now - 300, now, now),
        )
        account_id = int(cursor.lastrowid)
        cursor.execute(
            """
            insert into matrix_publish_plan (
                user_id, plan_name, source_type, content_type, product_id,
                status, schedule_start_time, schedule_end_time,
                scheduling_rule_json, create_time, update_time
            )
            values (%s, '新品发布计划', 'content_draft', 'image_text', 0, 3, %s, %s, '{}', %s, %s)
            """,
            (user_id, now - 60, now + 3600, now, now),
        )
        plan_id = int(cursor.lastrowid)
        cursor.execute(
            """
            insert into matrix_publish_item (
                plan_id, user_id, xhs_account_id, content_type, title, body,
                tag_json, material_json, scheduled_time, status, last_error,
                create_time, update_time
            )
            values (%s, %s, %s, 'image_text', '新品首发', '正文', '[]', '[]', %s, 2, '', %s, %s)
            """,
            (plan_id, user_id, account_id, now - 30, now, now),
        )
    mysql_conn.commit()
    return account_id, plan_id


def test_manager_operations_are_visualization_ready_and_tenant_scoped(mysql_conn, mysql_app_client):
    manager_id = create_user(
        mysql_conn,
        login_name="owner_ops",
        password="manager-password",
        role="client_owner",
        tenant_id=301,
    )
    assert manager_id > 0
    employee_id = create_user(
        mysql_conn,
        login_name="employee_ops",
        password="employee-password",
        role="customer",
        tenant_id=301,
    )
    other_employee_id = create_user(
        mysql_conn,
        login_name="other_ops",
        password="employee-password",
        role="customer",
        tenant_id=302,
    )
    account_id, plan_id = seed_operations_data(mysql_conn, employee_id)
    seed_operations_data(mysql_conn, other_employee_id)
    headers = login(mysql_app_client, "manager", "owner_ops", "manager-password")

    overview = mysql_app_client.get("/api/admin/operations/overview", headers=headers)
    assert overview.status_code == 200
    data = overview.json()["data"]
    assert data["summary"]["total_employees"] == 1
    assert data["summary"]["total_accounts"] == 1
    assert len(data["publish_trend"]) == 7
    assert data["summary"]["pending_items"] == 1

    accounts = mysql_app_client.get("/api/admin/operations/xhs-accounts", headers=headers)
    assert accounts.status_code == 200
    assert accounts.json()["data"]["total"] == 1
    assert accounts.json()["data"]["items"][0]["id"] == account_id
    assert "login_state_path" not in accounts.json()["data"]["items"][0]

    plans = mysql_app_client.get("/api/admin/operations/publish-plans", headers=headers)
    assert plans.status_code == 200
    assert plans.json()["data"]["total"] == 1
    assert plans.json()["data"]["items"][0]["id"] == plan_id

    detail = mysql_app_client.get(
        f"/api/admin/operations/publish-plans/{plan_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["items"][0]["account_name"] == "品牌主号"


def test_manager_notification_reaches_employee_and_persists_read_state(mysql_conn, mysql_app_client):
    create_user(
        mysql_conn,
        login_name="owner_notice",
        password="manager-password",
        role="client_owner",
        tenant_id=401,
    )
    employee_id = create_user(
        mysql_conn,
        login_name="employee_notice",
        password="employee-password",
        role="customer",
        tenant_id=401,
    )
    manager_headers = login(mysql_app_client, "manager", "owner_notice", "manager-password")
    employee_headers = login(mysql_app_client, "customer", "employee_notice", "employee-password")

    created = mysql_app_client.post(
        "/api/admin/notifications",
        headers=manager_headers,
        json={
            "recipient_user_ids": [employee_id],
            "notification_type": "task",
            "title": "完成新品排期",
            "content": "请在今天下班前确认发布计划。",
            "priority": 2,
            "action_path": "schedule",
            "deadline_time": int(time.time()) + 3600,
        },
    )
    assert created.status_code == 200
    assert created.json()["data"]["recipient_count"] == 1

    unread = mysql_app_client.get("/api/notifications/unread-count", headers=employee_headers)
    assert unread.json()["data"]["count"] == 1
    notifications = mysql_app_client.get("/api/notifications", headers=employee_headers)
    notification = notifications.json()["data"]["items"][0]
    assert notification["title"] == "完成新品排期"
    assert notification["is_read"] is False

    marked = mysql_app_client.post(
        f"/api/notifications/{notification['id']}/read",
        headers=employee_headers,
    )
    assert marked.status_code == 200
    assert mysql_app_client.get(
        "/api/notifications/unread-count",
        headers=employee_headers,
    ).json()["data"]["count"] == 0

    sent = mysql_app_client.get("/api/admin/notifications", headers=manager_headers)
    assert sent.status_code == 200
    assert sent.json()["data"]["items"][0]["recipient_count"] == 1
    assert sent.json()["data"]["items"][0]["read_count"] == 1
