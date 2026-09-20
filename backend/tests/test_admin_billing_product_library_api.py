import json
import time

from app.core.security import hash_password
from app.repositories.user_repository import UserRepository


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


def create_user(
    mysql_conn,
    *,
    login_name: str,
    role: str,
    tenant_id: int,
) -> int:
    return UserRepository(mysql_conn).create_user(
        login_name=login_name,
        nickname=login_name,
        password_hash=hash_password("test-password"),
        user_role=role,
        invite_code="",
        tenant_id=tenant_id,
    )


def login_headers(
    mysql_app_client,
    *,
    portal: str,
    login_name: str,
) -> dict[str, str]:
    response = mysql_app_client.post(
        f"/api/auth/{portal}/login",
        json={"login_name": login_name, "password": "test-password"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_manager_context(
    mysql_conn,
    mysql_app_client,
    *,
    tenant_id: int,
) -> tuple[int, dict[str, str]]:
    login_name = f"owner_{tenant_id}"
    manager_id = create_user(
        mysql_conn,
        login_name=login_name,
        role="client_owner",
        tenant_id=tenant_id,
    )
    return manager_id, login_headers(
        mysql_app_client,
        portal="manager",
        login_name=login_name,
    )


def test_manager_confirms_recharge_once(
    mysql_conn,
    mysql_app_client,
):
    tenant_id = 701
    _, headers = create_manager_context(
        mysql_conn,
        mysql_app_client,
        tenant_id=tenant_id,
    )
    employee_id = create_user(
        mysql_conn,
        login_name="billing_employee",
        role="customer",
        tenant_id=tenant_id,
    )
    packages_response = mysql_app_client.get(
        "/api/admin/billing/recharge-packages",
        headers=headers,
    )
    assert packages_response.status_code == 200
    package = packages_response.json()["data"][2]

    created = mysql_app_client.post(
        "/api/admin/billing/recharge-orders",
        headers=headers,
        json={
            "employee_id": employee_id,
            "recharge_type": "package",
            "package_id": package["id"],
            "amount_cent": 0,
            "payment_channel": "manual",
        },
    )
    assert created.status_code == 200
    order = created.json()["data"]
    assert order["status"] == 1
    assert order["requested_credits"] == package["credits"]

    confirmed = mysql_app_client.post(
        f"/api/admin/billing/recharge-orders/{order['id']}/confirm",
        headers=headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == 6

    confirmed_again = mysql_app_client.post(
        f"/api/admin/billing/recharge-orders/{order['id']}/confirm",
        headers=headers,
    )
    assert confirmed_again.status_code == 200
    assert confirmed_again.json()["data"]["status"] == 6

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select count(*) as total
            from credit_ledger
            where user_id = %s
              and business_type = 'recharge'
              and business_id = %s
            """,
            (employee_id, order["id"]),
        )
        pending_ledger_count = int(cursor.fetchone()["total"])
    assert pending_ledger_count == 0

    developer_login = "billing_developer"
    create_user(
        mysql_conn,
        login_name=developer_login,
        role="platform_admin",
        tenant_id=1,
    )
    developer_headers = login_headers(
        mysql_app_client,
        portal="developer",
        login_name=developer_login,
    )
    granted = mysql_app_client.post(
        f"/api/developer/billing/recharge-orders/{order['id']}/grant",
        headers=developer_headers,
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["data"]["status"] == 3

    granted_again = mysql_app_client.post(
        f"/api/developer/billing/recharge-orders/{order['id']}/grant",
        headers=developer_headers,
    )
    assert granted_again.status_code == 200
    assert granted_again.json()["data"]["status"] == 3

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select balance, total_recharged
            from credit_wallet
            where user_id = %s
            """,
            (employee_id,),
        )
        wallet = cursor.fetchone()
        cursor.execute(
            """
            select count(*) as total
            from credit_ledger
            where user_id = %s
              and business_type = 'recharge'
              and business_id = %s
            """,
            (employee_id, order["id"]),
        )
        ledger_count = int(cursor.fetchone()["total"])
    assert int(wallet["balance"]) == int(package["credits"])
    assert int(wallet["total_recharged"]) == int(package["credits"])
    assert ledger_count == 1

    overview = mysql_app_client.get(
        "/api/admin/billing/overview",
        headers=headers,
    )
    assert overview.status_code == 200
    overview_data = overview.json()["data"]
    assert overview_data["wallet"]["employee_count"] == 1
    assert overview_data["wallet"]["balance"] == package["credits"]
    assert overview_data["month_orders"]["completed_credits"] == package["credits"]

    ledger = mysql_app_client.get(
        "/api/admin/billing/ledger",
        headers=headers,
        params={"employee_id": employee_id},
    )
    assert ledger.status_code == 200
    assert ledger.json()["data"]["total"] >= 1
    assert all(
        item["user_id"] == employee_id
        for item in ledger.json()["data"]["items"]
    )


def test_manager_billing_is_tenant_scoped(mysql_conn, mysql_app_client):
    _, first_headers = create_manager_context(
        mysql_conn,
        mysql_app_client,
        tenant_id=711,
    )
    second_employee_id = create_user(
        mysql_conn,
        login_name="second_tenant_employee",
        role="customer",
        tenant_id=712,
    )
    _, second_headers = create_manager_context(
        mysql_conn,
        mysql_app_client,
        tenant_id=712,
    )
    created = mysql_app_client.post(
        "/api/admin/billing/recharge-orders",
        headers=second_headers,
        json={
            "employee_id": second_employee_id,
            "recharge_type": "online",
            "package_id": 0,
            "amount_cent": 1000,
            "payment_channel": "manual",
        },
    )
    assert created.status_code == 200
    order_id = created.json()["data"]["id"]

    forbidden_employee = mysql_app_client.post(
        "/api/admin/billing/recharge-orders",
        headers=first_headers,
        json={
            "employee_id": second_employee_id,
            "recharge_type": "online",
            "package_id": 0,
            "amount_cent": 1000,
            "payment_channel": "manual",
        },
    )
    assert forbidden_employee.status_code == 404

    hidden_order = mysql_app_client.post(
        f"/api/admin/billing/recharge-orders/{order_id}/confirm",
        headers=first_headers,
    )
    assert hidden_order.status_code == 404


def test_paid_membership_upgrade_requires_developer_approval(
    mysql_conn,
    mysql_app_client,
):
    tenant_id = 713
    manager_id, manager_headers = create_manager_context(
        mysql_conn,
        mysql_app_client,
        tenant_id=tenant_id,
    )
    employee_id = create_user(
        mysql_conn,
        login_name="membership_upgrade_employee",
        role="customer",
        tenant_id=tenant_id,
    )
    developer_login = "membership_upgrade_developer"
    create_user(
        mysql_conn,
        login_name=developer_login,
        role="platform_admin",
        tenant_id=1,
    )
    developer_headers = login_headers(
        mysql_app_client,
        portal="developer",
        login_name=developer_login,
    )

    plans = mysql_app_client.get(
        "/api/admin/billing/membership-plans",
        headers=manager_headers,
    ).json()["data"]
    pro_plan = next(plan for plan in plans if plan["plan_code"] == "pro")
    max_plan = next(plan for plan in plans if plan["plan_code"] == "max")
    now = int(time.time())
    with mysql_conn.cursor() as cursor:
        for user_id in (manager_id, employee_id):
            cursor.execute(
                """
                insert into user_membership (
                    tenant_id, user_id, plan_id, status, start_time,
                    expire_time, auto_renew, create_time, update_time
                )
                values (%s, %s, %s, 1, %s, 0, 0, %s, %s)
                """,
                (tenant_id, user_id, pro_plan["id"], now, now, now),
            )
    mysql_conn.commit()

    created = mysql_app_client.post(
        "/api/admin/billing/membership-orders",
        headers=manager_headers,
        json={
            "plan_id": max_plan["id"],
            "duration_months": 1,
            "payment_channel": "wechat",
            "amount_cent": 1,
        },
    )
    assert created.status_code == 200, created.text
    order = created.json()["data"]
    assert order["status"] == 1
    assert order["amount_cent"] == max_plan["price_cent"]
    assert order["plan"]["plan_code"] == "max"

    confirmed = mysql_app_client.post(
        f"/api/admin/billing/membership-orders/{order['id']}/confirm",
        headers=manager_headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["status"] == 2

    overview_before_review = mysql_app_client.get(
        "/api/admin/billing/overview",
        headers=manager_headers,
    )
    assert overview_before_review.json()["data"]["membership"]["plan"]["plan_code"] == "pro"

    pending = mysql_app_client.get(
        "/api/developer/billing/membership-orders",
        headers=developer_headers,
        params={"status": 2},
    )
    assert pending.status_code == 200, pending.text
    assert [item["id"] for item in pending.json()["data"]["items"]] == [order["id"]]

    approved = mysql_app_client.post(
        f"/api/developer/billing/membership-orders/{order['id']}/approve",
        headers=developer_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == 3
    assert approved.json()["data"]["affected_user_count"] == 2

    approved_again = mysql_app_client.post(
        f"/api/developer/billing/membership-orders/{order['id']}/approve",
        headers=developer_headers,
    )
    assert approved_again.status_code == 200
    assert approved_again.json()["data"]["status"] == 3

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select user_id, plan_id
            from user_membership
            where user_id in (%s, %s)
            order by user_id
            """,
            (manager_id, employee_id),
        )
        memberships = cursor.fetchall()
    assert len(memberships) == 2
    assert all(int(row["plan_id"]) == int(max_plan["id"]) for row in memberships)

    direct_activation = mysql_app_client.post(
        "/api/admin/billing/membership/activate",
        headers=manager_headers,
        json={"plan_id": max_plan["id"], "duration_months": 1},
    )
    assert direct_activation.status_code == 409


def test_rejected_membership_upgrade_does_not_change_current_plan(
    mysql_conn,
    mysql_app_client,
):
    tenant_id = 714
    manager_id, manager_headers = create_manager_context(
        mysql_conn,
        mysql_app_client,
        tenant_id=tenant_id,
    )
    developer_login = "membership_reject_developer"
    create_user(
        mysql_conn,
        login_name=developer_login,
        role="developer_admin",
        tenant_id=1,
    )
    developer_headers = login_headers(
        mysql_app_client,
        portal="developer",
        login_name=developer_login,
    )
    plans = mysql_app_client.get(
        "/api/admin/billing/membership-plans",
        headers=manager_headers,
    ).json()["data"]
    pro_plan = next(plan for plan in plans if plan["plan_code"] == "pro")
    storage_plan = next(plan for plan in plans if plan["plan_code"] == "storage")
    now = int(time.time())
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            insert into user_membership (
                tenant_id, user_id, plan_id, status, start_time,
                expire_time, auto_renew, create_time, update_time
            ) values (%s, %s, %s, 1, %s, 0, 0, %s, %s)
            """,
            (tenant_id, manager_id, pro_plan["id"], now, now, now),
        )
    mysql_conn.commit()

    created = mysql_app_client.post(
        "/api/admin/billing/membership-orders",
        headers=manager_headers,
        json={
            "plan_id": storage_plan["id"],
            "duration_months": 1,
            "payment_channel": "alipay",
        },
    ).json()["data"]
    mysql_app_client.post(
        f"/api/admin/billing/membership-orders/{created['id']}/confirm",
        headers=manager_headers,
    )

    rejected = mysql_app_client.post(
        f"/api/developer/billing/membership-orders/{created['id']}/reject",
        headers=developer_headers,
        json={"reason": "收款记录无法核对"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["data"]["status"] == 4
    assert rejected.json()["data"]["remark"] == "收款记录无法核对"

    overview = mysql_app_client.get(
        "/api/admin/billing/overview",
        headers=manager_headers,
    )
    assert overview.json()["data"]["membership"]["plan"]["plan_code"] == "pro"


def test_manager_can_cancel_membership_order_before_developer_decision(
    mysql_conn,
    mysql_app_client,
):
    tenant_id = 715
    manager_id, manager_headers = create_manager_context(
        mysql_conn,
        mysql_app_client,
        tenant_id=tenant_id,
    )
    plans = mysql_app_client.get(
        "/api/admin/billing/membership-plans",
        headers=manager_headers,
    ).json()["data"]
    pro_plan = next(plan for plan in plans if plan["plan_code"] == "pro")
    max_plan = next(plan for plan in plans if plan["plan_code"] == "max")
    now = int(time.time())
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            insert into user_membership (
                tenant_id, user_id, plan_id, status, start_time,
                expire_time, auto_renew, create_time, update_time
            ) values (%s, %s, %s, 1, %s, 0, 0, %s, %s)
            """,
            (tenant_id, manager_id, pro_plan["id"], now, now, now),
        )
    mysql_conn.commit()

    first_order = mysql_app_client.post(
        "/api/admin/billing/membership-orders",
        headers=manager_headers,
        json={
            "plan_id": max_plan["id"],
            "duration_months": 1,
            "payment_channel": "wechat",
        },
    ).json()["data"]
    cancelled_before_payment = mysql_app_client.post(
        f"/api/admin/billing/membership-orders/{first_order['id']}/cancel",
        headers=manager_headers,
    )
    assert cancelled_before_payment.status_code == 200, cancelled_before_payment.text
    assert cancelled_before_payment.json()["data"]["status"] == 5

    confirm_cancelled = mysql_app_client.post(
        f"/api/admin/billing/membership-orders/{first_order['id']}/confirm",
        headers=manager_headers,
    )
    assert confirm_cancelled.status_code == 409

    second_order = mysql_app_client.post(
        "/api/admin/billing/membership-orders",
        headers=manager_headers,
        json={
            "plan_id": max_plan["id"],
            "duration_months": 1,
            "payment_channel": "alipay",
        },
    ).json()["data"]
    confirmed = mysql_app_client.post(
        f"/api/admin/billing/membership-orders/{second_order['id']}/confirm",
        headers=manager_headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["status"] == 2

    cancelled_before_review = mysql_app_client.post(
        f"/api/admin/billing/membership-orders/{second_order['id']}/cancel",
        headers=manager_headers,
    )
    assert cancelled_before_review.status_code == 200, cancelled_before_review.text
    assert cancelled_before_review.json()["data"]["status"] == 5

    overview = mysql_app_client.get(
        "/api/admin/billing/overview",
        headers=manager_headers,
    )
    assert overview.json()["data"]["membership"]["plan"]["plan_code"] == "pro"


def test_manager_product_library_is_tenant_scoped_and_manageable(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    mysql_app_client.app.state.config.data_dir = tmp_path
    tenant_id = 721
    _, headers = create_manager_context(
        mysql_conn,
        mysql_app_client,
        tenant_id=tenant_id,
    )
    employee_id = create_user(
        mysql_conn,
        login_name="product_employee",
        role="customer",
        tenant_id=tenant_id,
    )
    outsider_id = create_user(
        mysql_conn,
        login_name="product_outsider",
        role="customer",
        tenant_id=722,
    )
    now = int(time.time())
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            insert into product (
                user_id, product_name, brand_name, category, sku,
                price_cent, activity_price_cent, status, cover_material_id,
                parameter_json, selling_point_json, ai_material_json,
                create_time, update_time
            )
            values (%s, 'Team Product', 'Karries', 'Beauty', 'TEAM-001',
                    19900, 16900, 1, 0, '{}', '{}', '{}', %s, %s)
            """,
            (employee_id, now, now),
        )
        product_id = int(cursor.lastrowid)
        cursor.execute(
            """
            insert into product (
                user_id, product_name, brand_name, category, sku,
                price_cent, activity_price_cent, status, cover_material_id,
                parameter_json, selling_point_json, ai_material_json,
                create_time, update_time
            )
            values (%s, 'Hidden Product', 'Other', 'Other', 'OTHER-001',
                    100, 100, 1, 0, '{}', '{}', '{}', %s, %s)
            """,
            (outsider_id, now, now),
        )
    mysql_conn.commit()

    products = mysql_app_client.get(
        "/api/admin/product-library/products",
        headers=headers,
    )
    assert products.status_code == 200
    product_data = products.json()["data"]
    assert product_data["total"] == 1
    assert product_data["items"][0]["id"] == product_id
    assert product_data["items"][0]["employee_login"] == "product_employee"

    disabled = mysql_app_client.patch(
        f"/api/admin/product-library/products/{product_id}/status",
        headers=headers,
        json={"status": 2},
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["status"] == 2

    folder = mysql_app_client.post(
        "/api/admin/product-library/folders",
        headers=headers,
        json={"parent_id": 0, "folder_name": "Campaign Materials"},
    )
    assert folder.status_code == 200
    folder_id = folder.json()["data"]["id"]

    upload = mysql_app_client.post(
        "/api/admin/product-library/assets/upload",
        headers=headers,
        params={"folder_id": folder_id},
        files={"file": ("product.png", PNG_BYTES, "image/png")},
    )
    assert upload.status_code == 200
    asset_id = upload.json()["data"]["id"]

    items = mysql_app_client.get(
        "/api/admin/product-library/items",
        headers=headers,
        params={"folder_id": folder_id},
    )
    assert items.status_code == 200
    assert [item["id"] for item in items.json()["data"]["assets"]] == [asset_id]

    content = mysql_app_client.get(
        f"/api/admin/product-library/assets/{asset_id}/content",
        headers=headers,
    )
    assert content.status_code == 200
    assert content.content == PNG_BYTES

    summary = mysql_app_client.get(
        "/api/admin/product-library/summary",
        headers=headers,
    )
    assert summary.status_code == 200
    summary_data = summary.json()["data"]
    assert summary_data["product_count"] == 1
    assert summary_data["active_product_count"] == 0
    assert summary_data["folder_count"] == 1
    assert summary_data["image_count"] == 1


def test_manager_project_groups_are_shared_tenant_scoped_audited_and_compatible(
    mysql_conn,
    mysql_app_client,
):
    tenant_id = 723
    manager_id, manager_headers = create_manager_context(
        mysql_conn,
        mysql_app_client,
        tenant_id=tenant_id,
    )
    customer_login = "project_group_customer"
    create_user(
        mysql_conn,
        login_name=customer_login,
        role="customer",
        tenant_id=tenant_id,
    )
    customer_headers = login_headers(
        mysql_app_client,
        portal="customer",
        login_name=customer_login,
    )
    _, outsider_headers = create_manager_context(
        mysql_conn,
        mysql_app_client,
        tenant_id=724,
    )

    customer_created = mysql_app_client.post(
        "/api/material-library/project-groups",
        headers=customer_headers,
        json={"group_name": "客户共享项目"},
    )
    assert customer_created.status_code == 200, customer_created.text
    shared_group = customer_created.json()["data"]

    manager_groups = mysql_app_client.get(
        "/api/admin/product-library/project-groups",
        headers=manager_headers,
    )
    assert manager_groups.status_code == 200, manager_groups.text
    assert shared_group["id"] in [
        group["id"] for group in manager_groups.json()["data"]
    ]

    manager_created = mysql_app_client.post(
        "/api/admin/product-library/project-groups",
        headers=manager_headers,
        json={"group_name": "管理端审计项目"},
    )
    assert manager_created.status_code == 200, manager_created.text
    audited_group = manager_created.json()["data"]

    duplicate_create = mysql_app_client.post(
        "/api/admin/product-library/project-groups",
        headers=manager_headers,
        json={"group_name": "管理端审计项目"},
    )
    duplicate_rename = mysql_app_client.patch(
        f"/api/admin/product-library/project-groups/{audited_group['id']}",
        headers=manager_headers,
        json={"group_name": shared_group["group_name"]},
    )
    assert duplicate_create.status_code == 400
    assert duplicate_create.json()["error"]["code"] == "INVALID_PROJECT_GROUP"
    assert duplicate_rename.status_code == 400
    assert duplicate_rename.json()["error"]["code"] == "INVALID_PROJECT_GROUP"

    renamed = mysql_app_client.patch(
        f"/api/admin/product-library/project-groups/{audited_group['id']}",
        headers=manager_headers,
        json={"group_name": "已重命名审计项目"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["group_name"] == "已重命名审计项目"

    outsider_rename = mysql_app_client.patch(
        f"/api/admin/product-library/project-groups/{audited_group['id']}",
        headers=outsider_headers,
        json={"group_name": "越租户改名"},
    )
    outsider_delete = mysql_app_client.delete(
        f"/api/admin/product-library/project-groups/{audited_group['id']}",
        headers=outsider_headers,
    )
    assert outsider_rename.status_code == 404
    assert outsider_rename.json()["error"]["code"] == "NOT_FOUND"
    assert outsider_delete.status_code == 404
    assert outsider_delete.json()["error"]["code"] == "NOT_FOUND"

    manager_folder = mysql_app_client.post(
        "/api/admin/product-library/folders",
        headers=manager_headers,
        json={
            "project_group_id": shared_group["id"],
            "parent_id": 0,
            "folder_name": "管理端共享文件夹",
        },
    )
    assert manager_folder.status_code == 200, manager_folder.text
    folder = manager_folder.json()["data"]
    assert folder["project_group_id"] == shared_group["id"]

    customer_items = mysql_app_client.get(
        "/api/material-library/items",
        headers=customer_headers,
        params={"project_group_id": shared_group["id"], "folder_id": 0},
    )
    assert customer_items.status_code == 200, customer_items.text
    assert [item["id"] for item in customer_items.json()["data"]["folders"]] == [
        folder["id"]
    ]

    manager_items = mysql_app_client.get(
        "/api/admin/product-library/items",
        headers=manager_headers,
        params={"project_group_id": shared_group["id"], "folder_id": 0},
    )
    assert manager_items.status_code == 200, manager_items.text
    assert manager_items.json()["data"]["project_group_id"] == shared_group["id"]
    assert [item["id"] for item in manager_items.json()["data"]["folders"]] == [
        folder["id"]
    ]

    legacy_folder = mysql_app_client.post(
        "/api/admin/product-library/folders",
        headers=manager_headers,
        json={"parent_id": 0, "folder_name": "旧调用兼容文件夹"},
    )
    assert legacy_folder.status_code == 200, legacy_folder.text
    legacy_items = mysql_app_client.get(
        "/api/admin/product-library/items",
        headers=manager_headers,
        params={"folder_id": 0},
    )
    assert legacy_items.status_code == 200, legacy_items.text
    assert legacy_folder.json()["data"]["id"] in [
        item["id"] for item in legacy_items.json()["data"]["folders"]
    ]

    non_empty_delete = mysql_app_client.delete(
        f"/api/admin/product-library/project-groups/{shared_group['id']}",
        headers=manager_headers,
    )
    assert non_empty_delete.status_code == 409
    assert non_empty_delete.json()["error"]["code"] == "PROJECT_GROUP_NOT_EMPTY"

    deleted = mysql_app_client.delete(
        f"/api/admin/product-library/project-groups/{audited_group['id']}",
        headers=manager_headers,
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"] == {"deleted": True}

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select action, target_type, target_id
            from admin_audit_log
            where tenant_id = %s
              and admin_user_id = %s
              and target_type = 'material_project_group'
              and target_id = %s
            order by id
            """,
            (tenant_id, manager_id, audited_group["id"]),
        )
        audit_rows = cursor.fetchall()
    assert [row["action"] for row in audit_rows] == [
        "material_project_group.create",
        "material_project_group.rename",
        "material_project_group.delete",
    ]


def test_developer_can_adjust_tenant_membership_directly(
    mysql_conn,
    mysql_app_client,
):
    tenant_id = 730
    manager_id, _manager_headers = create_manager_context(
        mysql_conn,
        mysql_app_client,
        tenant_id=tenant_id,
    )
    employee_id = create_user(
        mysql_conn,
        login_name="membership_adjust_employee",
        role="customer",
        tenant_id=tenant_id,
    )
    developer_login = "membership_adjust_developer"
    create_user(
        mysql_conn,
        login_name=developer_login,
        role="developer_admin",
        tenant_id=1,
    )
    developer_headers = login_headers(
        mysql_app_client,
        portal="developer",
        login_name=developer_login,
    )

    fetched = mysql_app_client.get(
        f"/api/developer/billing/tenants/{tenant_id}/membership",
        headers=developer_headers,
    )
    assert fetched.status_code == 200, fetched.text
    current = fetched.json()["data"]
    assert current["tenant_id"] == tenant_id
    assert current["affected_user_count"] == 2
    assert current["membership"] is None
    assert [
        plan["plan_code"] for plan in current["plans"]
    ] == ["free", "pro", "max", "storage"]
    max_plan = next(
        plan for plan in current["plans"] if plan["plan_code"] == "max"
    )

    updated = mysql_app_client.post(
        f"/api/developer/billing/tenants/{tenant_id}/membership",
        headers=developer_headers,
        json={"plan_id": max_plan["id"], "duration_months": 3},
    )
    assert updated.status_code == 200, updated.text
    result = updated.json()["data"]
    assert result["membership"]["plan"]["plan_code"] == "max"
    assert result["membership"]["plan"]["monthly_credits"] == max_plan["monthly_credits"]
    assert result["membership"]["status"] == 1
    assert result["membership"]["expire_time"] > int(time.time())
    assert result["affected_user_count"] == 2

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select plan_id, status, expire_time
            from user_membership
            where user_id in (%s, %s)
            order by user_id
            """,
            (manager_id, employee_id),
        )
        membership_rows = cursor.fetchall()
        cursor.execute(
            """
            select detail_json
            from admin_audit_log
            where action = 'developer.billing.membership_adjust'
              and target_type = 'tenant'
              and target_id = %s
            """,
            (tenant_id,),
        )
        audit_row = cursor.fetchone()
    assert len(membership_rows) == 2
    assert all(
        int(row["plan_id"]) == max_plan["id"]
        and int(row["status"]) == 1
        and int(row["expire_time"]) > int(time.time())
        for row in membership_rows
    )
    assert audit_row is not None
    detail = json.loads(audit_row["detail_json"])
    assert detail["plan_code"] == "max"
    assert detail["duration_months"] == 3
    assert detail["affected_user_count"] == 2

    long_term = mysql_app_client.post(
        f"/api/developer/billing/tenants/{tenant_id}/membership",
        headers=developer_headers,
        json={"plan_id": max_plan["id"], "duration_months": 0},
    )
    assert long_term.status_code == 200, long_term.text
    assert long_term.json()["data"]["membership"]["expire_time"] == 0


def test_developer_membership_adjust_rejects_invalid_plan(
    mysql_conn,
    mysql_app_client,
):
    tenant_id = 731
    create_manager_context(
        mysql_conn,
        mysql_app_client,
        tenant_id=tenant_id,
    )
    developer_login = "membership_invalid_plan_developer"
    create_user(
        mysql_conn,
        login_name=developer_login,
        role="developer_admin",
        tenant_id=1,
    )
    developer_headers = login_headers(
        mysql_app_client,
        portal="developer",
        login_name=developer_login,
    )

    missing_plan = mysql_app_client.post(
        f"/api/developer/billing/tenants/{tenant_id}/membership",
        headers=developer_headers,
        json={"plan_id": 999999, "duration_months": 1},
    )
    assert missing_plan.status_code == 404
    assert missing_plan.json()["error"]["code"] == "NOT_FOUND"

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "update membership_plan set status = 2 where plan_code = 'storage'"
        )
    mysql_conn.commit()
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select id from membership_plan where plan_code = 'storage'"
        )
        disabled_plan_id = int(cursor.fetchone()["id"])
    disabled_plan = mysql_app_client.post(
        f"/api/developer/billing/tenants/{tenant_id}/membership",
        headers=developer_headers,
        json={"plan_id": disabled_plan_id, "duration_months": 1},
    )
    assert disabled_plan.status_code == 400
    assert disabled_plan.json()["error"]["code"] == "INVALID_PLAN"


def test_developer_tenant_membership_returns_404_for_unknown_tenant(
    mysql_conn,
    mysql_app_client,
):
    developer_login = "membership_unknown_tenant_developer"
    create_user(
        mysql_conn,
        login_name=developer_login,
        role="developer_admin",
        tenant_id=1,
    )
    developer_headers = login_headers(
        mysql_app_client,
        portal="developer",
        login_name=developer_login,
    )

    response = mysql_app_client.get(
        "/api/developer/billing/tenants/999999/membership",
        headers=developer_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
