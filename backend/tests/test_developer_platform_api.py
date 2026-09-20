import time

from app.core.security import create_access_token, verify_password
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.user_repository import UserRepository
from app.repositories.wallet_repository import WalletRepository


def _auth_headers(mysql_conn, client, login_name: str, role: str) -> dict[str, str]:
    user_id = UserRepository(mysql_conn).create_user(
        login_name=login_name,
        nickname=login_name,
        password_hash="not-used-by-token-auth",
        user_role=role,
        invite_code="",
        tenant_id=1,
    )
    token = create_access_token(
        {
            "user_id": user_id,
            "tenant_id": 1,
            "role": role,
            "auth_version": 1,
        },
        client.app.state.config.auth.token_secret,
        client.app.state.config.auth.access_token_seconds,
    )
    return {"Authorization": f"Bearer {token}"}


def test_developer_alert_event_schema_is_created(mysql_conn):
    with mysql_conn.cursor() as cursor:
        cursor.execute("show columns from developer_alert_event")
        columns = {row["Field"] for row in cursor.fetchall()}

    assert {
        "alert_key",
        "alert_type",
        "severity",
        "status",
        "acknowledged_by",
        "resolved_by",
        "detail_json",
    }.issubset(columns)


def test_platform_overview_requires_developer_role(mysql_conn, mysql_app_client):
    headers = _auth_headers(mysql_conn, mysql_app_client, "overview_customer", "customer")

    response = mysql_app_client.get("/api/developer/platform/overview", headers=headers)

    assert response.status_code == 403


def test_platform_overview_reports_pool_tasks_ai_and_services(
    mysql_conn,
    mysql_app_client,
):
    now = int(time.time())
    trend_hour = ((now - 3600) // 3600) * 3600
    headers = _auth_headers(
        mysql_conn,
        mysql_app_client,
        "overview_developer",
        "developer_admin",
    )
    customer_id = UserRepository(mysql_conn).create_user(
        login_name="overview_operator",
        nickname="Overview Operator",
        password_hash="not-used",
        user_role="customer",
        invite_code="",
        tenant_id=1,
    )
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            insert into viral_analysis_job (
                tenant_id, user_id, title, source_type, source_url,
                material_file_id, analysis_goal, supplement_text, status,
                processing_token, processing_started_time, ai_provider,
                ai_model, credit_cost, error_message, create_time, update_time
            ) values (
                1, %s, 'Failed analysis', 'text', '', 0, '[]', '', 'failed',
                '', 0, 'doubao', 'vision-model', 0, 'provider timeout', %s, %s
            )
            """,
            (customer_id, now - 120, now - 60),
        )
        viral_id = int(cursor.lastrowid)
        cursor.execute(
            """
            insert into ai_usage_log (
                tenant_id, user_id, business_type, business_id, provider,
                model_name, request_id, status, credit_cost, latency_ms,
                input_chars, output_chars, error_message, create_time
            ) values
                (1, %s, 'viral_analysis', %s, 'doubao', 'vision-model',
                 'req-failed', 'failed', 0, 1800, 20, 0, 'timeout', %s),
                (1, %s, 'inspiration_chat', 0, 'deepseek', 'deepseek-chat',
                 'req-ok', 'success', 1, 420, 20, 40, '', %s)
            """,
            (
                customer_id,
                viral_id,
                trend_hour + 60,
                customer_id,
                trend_hour + 120,
            ),
        )
    mysql_conn.commit()

    response = mysql_app_client.get("/api/developer/platform/overview", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pool"]["pre_ping"] is True
    assert data["pool"]["size"] >= 1
    assert data["tasks"]["viral_analysis"]["failed"] == 1
    assert data["ai"]["calls_24h"] == 2
    assert data["ai"]["failures_24h"] == 1
    assert data["ai"]["p95_latency_ms"] == 1800
    assert data["ai"]["trend"] == [
        {
            "timestamp": trend_hour,
            "calls": 2,
            "failures": 1,
            "success_rate": 50.0,
            "p95_latency_ms": 1800,
        }
    ]
    assert {item["key"] for item in data["services"]} >= {
        "database",
        "publish_worker",
        "provider_deepseek",
        "provider_doubao",
        "storage",
    }


def test_unified_tasks_lists_all_core_task_types(mysql_conn, mysql_app_client):
    now = int(time.time())
    headers = _auth_headers(mysql_conn, mysql_app_client, "task_developer", "developer_admin")
    customer_id = UserRepository(mysql_conn).create_user(
        login_name="task_customer",
        nickname="Task Customer",
        password_hash="not-used",
        user_role="customer",
        invite_code="",
        tenant_id=1,
    )
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            insert into viral_analysis_job (
                tenant_id, user_id, title, source_type, source_url,
                material_file_id, analysis_goal, supplement_text, status,
                processing_token, processing_started_time, ai_provider,
                ai_model, credit_cost, error_message, create_time, update_time
            ) values (1, %s, 'Viral failure', 'text', '', 0, '[]', '',
                'failed', '', 0, '', '', 0, 'timeout', %s, %s)
            """,
            (customer_id, now - 30, now - 20),
        )
        cursor.execute(
            """
            insert into video_edit_job (
                user_id, job_title, post_body, script_text, requirement_text, material_json,
                status, expected_delivery_time, developer_note, delivery_json,
                create_time, update_time
            ) values (%s, 'Video delivery', '', '', '', '[]', 2, %s, '', '[]', %s, %s)
            """,
            (customer_id, now + 3600, now - 20, now - 10),
        )
        cursor.execute(
            """
            insert into matrix_publish_plan (
                user_id, plan_name, source_type, content_type, status,
                schedule_start_time, schedule_end_time, scheduling_rule_json,
                create_time, update_time
            ) values (%s, 'Matrix draft', 'product', 'image_text', 1,
                0, 0, '{}', %s, %s)
            """,
            (customer_id, now - 10, now),
        )
    mysql_conn.commit()

    response = mysql_app_client.get("/api/developer/platform/tasks", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 3
    assert {item["kind"] for item in data["items"]} == {
        "viral_analysis",
        "video_edit",
        "matrix_publish",
    }
    failed = next(item for item in data["items"] if item["kind"] == "viral_analysis")
    assert failed["status"] == "failed"
    assert failed["error_summary"] == "timeout"
    assert "password_hash" not in str(data)


def test_unified_task_cancel_requires_reason_and_creates_audit(
    mysql_conn,
    mysql_app_client,
):
    now = int(time.time())
    headers = _auth_headers(mysql_conn, mysql_app_client, "task_action_dev", "developer_admin")
    customer_id = UserRepository(mysql_conn).create_user(
        login_name="task_action_customer",
        nickname="Task Action Customer",
        password_hash="not-used",
        user_role="customer",
        invite_code="",
        tenant_id=1,
    )
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            insert into matrix_publish_plan (
                user_id, plan_name, source_type, content_type, status,
                schedule_start_time, schedule_end_time, scheduling_rule_json,
                create_time, update_time
            ) values (%s, 'Cancel me', 'product', 'image_text', 1,
                0, 0, '{}', %s, %s)
            """,
            (customer_id, now, now),
        )
        plan_id = int(cursor.lastrowid)
    mysql_conn.commit()

    invalid = mysql_app_client.post(
        f"/api/developer/platform/tasks/matrix_publish/{plan_id}/cancel",
        headers=headers,
        json={"reason": ""},
    )
    response = mysql_app_client.post(
        f"/api/developer/platform/tasks/matrix_publish/{plan_id}/cancel",
        headers=headers,
        json={"reason": "Duplicate campaign created by operator"},
    )

    assert invalid.status_code == 422
    assert response.status_code == 200
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from matrix_publish_plan where id = %s", (plan_id,))
        assert int(cursor.fetchone()["status"]) == 7
        cursor.execute(
            """
            select action, detail_json from admin_audit_log
            where target_type = 'matrix_publish_plan' and target_id = %s
            order by id desc limit 1
            """,
            (plan_id,),
        )
        audit = cursor.fetchone()
    assert audit["action"] == "developer.task.cancel"
    assert "Duplicate campaign" in audit["detail_json"]


def test_alert_center_detects_acknowledges_and_resolves_failure(
    mysql_conn,
    mysql_app_client,
):
    now = int(time.time())
    headers = _auth_headers(mysql_conn, mysql_app_client, "alert_developer", "developer_admin")
    customer_id = UserRepository(mysql_conn).create_user(
        login_name="alert_customer",
        nickname="Alert Customer",
        password_hash="not-used",
        user_role="customer",
        invite_code="",
        tenant_id=1,
    )
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            insert into viral_analysis_job (
                tenant_id, user_id, title, source_type, source_url,
                material_file_id, analysis_goal, supplement_text, status,
                processing_token, processing_started_time, ai_provider,
                ai_model, credit_cost, error_message, create_time, update_time
            ) values (1, %s, 'Broken analysis', 'text', '', 0, '[]', '',
                'failed', '', 0, '', '', 0, 'provider timeout', %s, %s)
            """,
            (customer_id, now - 60, now - 30),
        )
        job_id = int(cursor.lastrowid)
    mysql_conn.commit()

    response = mysql_app_client.get("/api/developer/platform/alerts", headers=headers)

    assert response.status_code == 200
    alert = next(
        item
        for item in response.json()["data"]["items"]
        if item["source_type"] == "viral_analysis_job" and item["source_id"] == job_id
    )
    assert alert["status"] == "open"
    assert alert["severity"] == "ticket"
    assert "provider timeout" in alert["summary"]

    acknowledged = mysql_app_client.post(
        f"/api/developer/platform/alerts/{alert['id']}/acknowledge",
        headers=headers,
        json={"reason": "Investigating provider timeout"},
    )
    resolved = mysql_app_client.post(
        f"/api/developer/platform/alerts/{alert['id']}/resolve",
        headers=headers,
        json={"reason": "Provider recovered and request was reviewed"},
    )

    assert acknowledged.status_code == 200
    assert acknowledged.json()["data"]["status"] == "acknowledged"
    assert resolved.status_code == 200
    assert resolved.json()["data"]["status"] == "resolved"
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select action from admin_audit_log
            where target_type = 'developer_alert_event' and target_id = %s
            order by id
            """,
            (alert["id"],),
        )
        actions = [row["action"] for row in cursor.fetchall()]
    assert actions == ["developer.alert.acknowledge", "developer.alert.resolve"]


def test_internal_account_management_enforces_roles_and_hides_credentials(
    mysql_conn,
    mysql_app_client,
):
    developer_headers = _auth_headers(
        mysql_conn,
        mysql_app_client,
        "access_developer",
        "developer_admin",
    )
    platform_headers = _auth_headers(
        mysql_conn,
        mysql_app_client,
        "access_platform",
        "platform_admin",
    )

    denied = mysql_app_client.post(
        "/api/developer/platform/accounts",
        headers=developer_headers,
        json={
            "login_name": "forbidden_platform",
            "nickname": "Forbidden Platform",
            "password": "strong-password",
            "role": "platform_admin",
        },
    )
    created = mysql_app_client.post(
        "/api/developer/platform/accounts",
        headers=platform_headers,
        json={
            "login_name": "new_developer",
            "nickname": "New Developer",
            "password": "strong-password",
            "role": "developer_admin",
        },
    )

    assert denied.status_code == 403
    assert created.status_code == 200
    account = created.json()["data"]
    assert account["login_name"] == "new_developer"
    assert "password" not in str(account).lower()

    listed = mysql_app_client.get(
        "/api/developer/platform/accounts?keyword=new_developer",
        headers=platform_headers,
    )
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1

    reset = mysql_app_client.put(
        f"/api/developer/platform/accounts/{account['id']}/password",
        headers=platform_headers,
        json={"password": "new-strong-password", "reason": "Scheduled credential rotation"},
    )
    assert reset.status_code == 200
    stored = UserRepository(mysql_conn).get_by_id(account["id"])
    assert verify_password("new-strong-password", stored["password_hash"])
    assert stored["password_hash"] != "new-strong-password"

    platform_user = UserRepository(mysql_conn).get_by_login_name("access_platform")
    self_disable = mysql_app_client.patch(
        f"/api/developer/platform/accounts/{platform_user['id']}/status",
        headers=platform_headers,
        json={"status": 2, "reason": "Trying self lockout"},
    )
    assert self_disable.status_code == 409


def test_audit_log_query_redacts_sensitive_details(mysql_conn, mysql_app_client):
    headers = _auth_headers(mysql_conn, mysql_app_client, "audit_developer", "developer_admin")
    actor = UserRepository(mysql_conn).get_by_login_name("audit_developer")
    AdminAuditRepository(mysql_conn).create(
        tenant_id=0,
        admin_user_id=int(actor["id"]),
        action="developer.test.sensitive",
        target_type="test_target",
        target_id=42,
        detail={
            "reason": "verification",
            "api_key": "do-not-return-this",
            "nested": {"access_token": "also-secret"},
        },
    )

    response = mysql_app_client.get(
        "/api/developer/platform/audit-logs?action=developer.test.sensitive",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    entry = data["items"][0]
    assert entry["operator_name"] == "audit_developer"
    assert entry["detail"]["api_key"] == "[REDACTED]"
    assert entry["detail"]["nested"]["access_token"] == "[REDACTED]"
    assert "do-not-return-this" not in str(data)
    assert "also-secret" not in str(data)


def test_developer_lists_and_controls_customer_accounts(
    mysql_conn,
    mysql_app_client,
):
    headers = _auth_headers(
        mysql_conn,
        mysql_app_client,
        "customer_account_developer",
        "developer_admin",
    )
    owner_id = UserRepository(mysql_conn).create_user(
        login_name="tenant_owner_control",
        nickname="租户管理员",
        password_hash="not-used",
        user_role="client_owner",
        invite_code="",
        tenant_id=77,
    )
    employee_id = UserRepository(mysql_conn).create_user(
        login_name="tenant_employee_control",
        nickname="租户用户",
        password_hash="not-used",
        user_role="customer",
        invite_code="",
        tenant_id=77,
    )
    WalletRepository(mysql_conn).create_wallet(
        employee_id,
        initial_credits=100,
        reason="测试初始算力",
    )

    listed = mysql_app_client.get(
        "/api/developer/platform/customer-accounts?keyword=tenant_",
        headers=headers,
    )
    disabled = mysql_app_client.patch(
        f"/api/developer/platform/customer-accounts/{employee_id}/status",
        headers=headers,
        json={"status": 2, "reason": "客户要求暂停账号"},
    )
    last_owner = mysql_app_client.patch(
        f"/api/developer/platform/customer-accounts/{owner_id}/status",
        headers=headers,
        json={"status": 2, "reason": "尝试停用最后一个管理员"},
    )

    assert listed.status_code == 200
    assert {item["user_role"] for item in listed.json()["data"]["items"]} == {
        "client_owner",
        "customer",
    }
    assert disabled.status_code == 200
    assert disabled.json()["data"]["status"] == 2
    assert last_owner.status_code == 409
    assert last_owner.json()["error"]["code"] == "LAST_TENANT_OWNER"


def test_developer_can_add_or_deduct_customer_credits(
    mysql_conn,
    mysql_app_client,
):
    headers = _auth_headers(
        mysql_conn,
        mysql_app_client,
        "credit_adjust_developer",
        "developer_admin",
    )
    user_id = UserRepository(mysql_conn).create_user(
        login_name="credit_adjust_customer",
        nickname="算力调整用户",
        password_hash="not-used",
        user_role="customer",
        invite_code="",
        tenant_id=88,
    )
    WalletRepository(mysql_conn).create_wallet(
        user_id,
        initial_credits=100,
        reason="测试初始算力",
    )

    response = mysql_app_client.post(
        "/api/developer/billing/credits/adjust",
        headers=headers,
        json={
            "user_id": user_id,
            "change_amount": -30,
            "reason": "纠正重复发放",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["before_balance"] == 100
    assert response.json()["data"]["change_amount"] == -30
    assert response.json()["data"]["after_balance"] == 70


def test_developer_payment_records_merge_recharges_and_memberships(
    mysql_conn,
    mysql_app_client,
):
    now = int(time.time())
    developer_headers = _auth_headers(
        mysql_conn,
        mysql_app_client,
        "payment_records_developer",
        "developer_admin",
    )
    customer_headers = _auth_headers(
        mysql_conn,
        mysql_app_client,
        "payment_records_customer_auth",
        "customer",
    )
    customer_id = UserRepository(mysql_conn).create_user(
        login_name="payment_records_customer",
        nickname="充值客户",
        password_hash="not-used",
        user_role="customer",
        invite_code="",
        tenant_id=91,
    )
    owner_id = UserRepository(mysql_conn).create_user(
        login_name="payment_records_owner",
        nickname="会员购买人",
        password_hash="not-used",
        user_role="client_owner",
        invite_code="",
        tenant_id=91,
    )
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            insert into tenant (
                id, tenant_code, tenant_name, status, create_time, update_time
            ) values (91, 'PAYMENT-RECORDS', '付款记录测试团队', 1, %s, %s)
            on duplicate key update tenant_name = values(tenant_name)
            """,
            (now, now),
        )
        cursor.execute(
            "select id from membership_plan where plan_code = 'max' limit 1"
        )
        plan_id = int(cursor.fetchone()["id"])
        cursor.execute(
            """
            insert into recharge_order (
                order_no, tenant_id, user_id, recharge_type, package_id,
                amount_cent, requested_credits, payment_channel, status,
                paid_time, completed_time, create_time, update_time
            ) values (
                'RC-PAYMENT-001', 91, %s, 'online', 0,
                5000, 1000, 'alipay', 6, %s, 0, %s, %s
            )
            """,
            (customer_id, now - 120, now - 180, now - 120),
        )
        cursor.execute(
            """
            insert into membership_upgrade_order (
                order_no, tenant_id, applicant_user_id, plan_id,
                duration_months, amount_cent, payment_channel, status,
                paid_time, reviewed_by_developer_id, reviewed_time,
                affected_user_count, remark, create_time, update_time
            ) values (
                'MU-PAYMENT-001', 91, %s, %s,
                2, 59800, 'wechat', 3,
                %s, 0, 0, 2, '', %s, %s
            )
            """,
            (owner_id, plan_id, now, now - 60, now),
        )
    mysql_conn.commit()

    first_page = mysql_app_client.get(
        "/api/developer/billing/payment-records?page=1&page_size=1",
        headers=developer_headers,
    )
    second_page = mysql_app_client.get(
        "/api/developer/billing/payment-records?page=2&page_size=1",
        headers=developer_headers,
    )
    forbidden = mysql_app_client.get(
        "/api/developer/billing/payment-records",
        headers=customer_headers,
    )

    assert first_page.status_code == 200
    assert first_page.json()["data"]["total"] == 2
    assert first_page.json()["data"]["items"] == [
        {
            "record_key": "membership_purchase:1",
            "record_type": "membership_purchase",
            "record_type_text": "会员购买",
            "order_id": 1,
            "order_no": "MU-PAYMENT-001",
            "tenant_id": 91,
            "tenant_name": "付款记录测试团队",
            "user_id": owner_id,
            "customer_name": "会员购买人",
            "customer_login": "payment_records_owner",
            "description": "Max会员版 · 2 个月",
            "amount_cent": 59800,
            "credits": 0,
            "payment_channel": "wechat",
            "status": 3,
            "status_text": "已开通",
            "paid_time": now,
            "create_time": now - 60,
            "update_time": now,
        }
    ]
    assert second_page.json()["data"]["items"][0] == {
        "record_key": "credit_recharge:1",
        "record_type": "credit_recharge",
        "record_type_text": "算力充值",
        "order_id": 1,
        "order_no": "RC-PAYMENT-001",
        "tenant_id": 91,
        "tenant_name": "付款记录测试团队",
        "user_id": customer_id,
        "customer_name": "充值客户",
        "customer_login": "payment_records_customer",
        "description": "自定义算力充值",
        "amount_cent": 5000,
        "credits": 1000,
        "payment_channel": "alipay",
        "status": 6,
        "status_text": "已付款待发放",
        "paid_time": now - 120,
        "create_time": now - 180,
        "update_time": now - 120,
    }
    assert forbidden.status_code == 403
