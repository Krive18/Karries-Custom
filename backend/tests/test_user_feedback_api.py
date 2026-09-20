from app.core.security import create_access_token
from app.repositories.user_repository import UserRepository


def _headers(mysql_conn, mysql_app_client, *, login_name: str, role: str, tenant_id: int) -> dict[str, str]:
    user_id = UserRepository(mysql_conn).create_user(
        login_name=login_name,
        nickname=login_name,
        password_hash="not-used-by-token-auth",
        user_role=role,
        invite_code="",
        tenant_id=tenant_id,
    )
    token = create_access_token(
        {"user_id": user_id, "tenant_id": tenant_id, "role": role},
        mysql_app_client.app.state.config.auth.token_secret,
        mysql_app_client.app.state.config.auth.access_token_seconds,
    )
    return {"Authorization": f"Bearer {token}"}


def test_customer_feedback_is_private_and_developer_completion_notifies_once(
    mysql_conn,
    mysql_app_client,
):
    customer = _headers(
        mysql_conn,
        mysql_app_client,
        login_name="feedback_customer",
        role="customer",
        tenant_id=701,
    )
    colleague = _headers(
        mysql_conn,
        mysql_app_client,
        login_name="feedback_colleague",
        role="customer",
        tenant_id=701,
    )
    developer = _headers(
        mysql_conn,
        mysql_app_client,
        login_name="feedback_developer",
        role="developer_admin",
        tenant_id=0,
    )

    invalid = mysql_app_client.post(
        "/api/user-feedback",
        headers=customer,
        json={"category": "unknown", "title": "无效反馈", "description": "分类不应该被接受"},
    )
    assert invalid.status_code == 422

    created = mysql_app_client.post(
        "/api/user-feedback",
        headers=customer,
        json={
            "category": "bug",
            "title": "视频预览按钮没有响应",
            "description": "进入创作记录后，点击第一个交付视频的预览按钮没有打开播放器。",
        },
    )
    assert created.status_code == 200, created.text
    feedback = created.json()["data"]
    assert feedback["status"] == "pending"
    assert feedback["category"] == "bug"
    assert feedback["developer_reply"] == ""

    own_list = mysql_app_client.get("/api/user-feedback", headers=customer)
    assert own_list.status_code == 200
    assert own_list.json()["data"]["total"] == 1
    assert own_list.json()["data"]["items"][0]["id"] == feedback["id"]

    colleague_list = mysql_app_client.get("/api/user-feedback", headers=colleague)
    assert colleague_list.status_code == 200
    assert colleague_list.json()["data"]["total"] == 0

    developer_list = mysql_app_client.get(
        "/api/developer/user-feedback?status=pending&keyword=视频预览",
        headers=developer,
    )
    assert developer_list.status_code == 200
    developer_item = developer_list.json()["data"]["items"][0]
    assert developer_item["id"] == feedback["id"]
    assert developer_item["user_login_name"] == "feedback_customer"
    assert developer_item["tenant_id"] == 701

    processing = mysql_app_client.put(
        f"/api/developer/user-feedback/{feedback['id']}",
        headers=developer,
        json={"status": "in_progress", "developer_reply": "已定位，正在修复播放器初始化。"},
    )
    assert processing.status_code == 200
    assert processing.json()["data"]["status"] == "in_progress"
    assert mysql_app_client.get(
        "/api/notifications/unread-count", headers=customer
    ).json()["data"]["count"] == 0

    completed = mysql_app_client.put(
        f"/api/developer/user-feedback/{feedback['id']}",
        headers=developer,
        json={"status": "completed", "developer_reply": "已完成修复，请刷新后重新预览。"},
    )
    assert completed.status_code == 200
    assert completed.json()["data"]["status"] == "completed"
    assert completed.json()["data"]["completed_time"] > 0

    notifications = mysql_app_client.get("/api/notifications", headers=customer)
    assert notifications.status_code == 200
    matching = [
        item
        for item in notifications.json()["data"]["items"]
        if item["business_type"] == "user_feedback"
        and item["business_id"] == feedback["id"]
    ]
    assert len(matching) == 1
    assert matching[0]["action_path"] == "feedback"
    assert matching[0]["title"] == "您的需求反馈已处理完成"

    repeated = mysql_app_client.put(
        f"/api/developer/user-feedback/{feedback['id']}",
        headers=developer,
        json={"status": "completed", "developer_reply": "已完成修复，请刷新后重新预览。"},
    )
    assert repeated.status_code == 200
    notifications_after_repeat = mysql_app_client.get("/api/notifications", headers=customer)
    matching_after_repeat = [
        item
        for item in notifications_after_repeat.json()["data"]["items"]
        if item["business_type"] == "user_feedback"
        and item["business_id"] == feedback["id"]
    ]
    assert len(matching_after_repeat) == 1

