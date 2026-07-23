import time

from app.core.security import create_access_token
from app.repositories.user_repository import UserRepository


def auth_headers(mysql_conn, mysql_app_client, suffix: str) -> dict[str, str]:
    invite_code = f"INV-VIDEO-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=0,
        max_uses=1,
        expires_time=0,
        remark="video-edit-api",
    )
    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": f"video_user_{suffix}",
            "nickname": f"Video User {suffix}",
            "password": "matrix-secret",
            "invite_code": invite_code,
        },
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def developer_headers(mysql_conn, mysql_app_client, suffix: str) -> dict[str, str]:
    developer_id = UserRepository(mysql_conn).create_user(
        login_name=f"developer_{suffix}",
        nickname="Developer Admin",
        password_hash="not-used-by-token-auth",
        user_role="platform_admin",
        invite_code="",
    )
    token = create_access_token(
        {"user_id": developer_id, "role": "platform_admin"},
        mysql_app_client.app.state.config.auth.token_secret,
        mysql_app_client.app.state.config.auth.access_token_seconds,
    )
    return {"Authorization": f"Bearer {token}"}


def create_video_edit_job(mysql_app_client, headers: dict[str, str], suffix: str) -> dict:
    response = mysql_app_client.post(
        "/api/video-edit/jobs",
        headers=headers,
        json={
            "job_title": f"禾一斯新品种草剪辑 {suffix}",
            "script_text": "前3秒展示产品细节，中段补充佩戴场景，结尾引导收藏咨询。",
            "requirement_text": "整体节奏自然，保留高级感，不要过度营销。",
            "materials": [
                {
                    "file_name": f"素材-{suffix}.mp4",
                    "file_type": "video",
                    "file_path": f"/uploads/{suffix}.mp4",
                    "mime_type": "video/mp4",
                    "file_size": 2048,
                    "remark": "客户上传原片",
                }
            ],
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_user_creates_video_edit_job_with_24_hour_progress(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, "create")
    before = int(time.time())

    job = create_video_edit_job(mysql_app_client, headers, "create")

    assert job["job_title"] == "禾一斯新品种草剪辑 create"
    assert job["status"] == 1
    assert job["status_name"] == "submitted"
    assert job["status_text"] == "待生成视频"
    assert "24 小时内生成完毕" in job["user_progress_text"]
    assert before + 24 * 60 * 60 <= job["expected_delivery_time"] <= int(time.time()) + 24 * 60 * 60
    assert job["materials"][0]["file_type"] == "video"

    listing = mysql_app_client.get("/api/video-edit/jobs", headers=headers)

    assert listing.status_code == 200
    rows = listing.json()["data"]
    assert len(rows) == 1
    assert rows[0]["id"] == job["id"]


def test_user_cannot_read_another_users_video_edit_job(mysql_conn, mysql_app_client):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "other")
    job = create_video_edit_job(mysql_app_client, owner_headers, "owner")

    response = mysql_app_client.get(f"/api/video-edit/jobs/{job['id']}", headers=other_headers)
    listing = mysql_app_client.get("/api/video-edit/jobs", headers=other_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert listing.status_code == 200
    assert listing.json()["data"] == []


def test_developer_video_edit_lifecycle(mysql_conn, mysql_app_client):
    user_headers = auth_headers(mysql_conn, mysql_app_client, "lifecycle")
    developer = developer_headers(mysql_conn, mysql_app_client, "lifecycle")
    job = create_video_edit_job(mysql_app_client, user_headers, "lifecycle")

    denied = mysql_app_client.get("/api/internal/video-edit/jobs", headers=user_headers)
    assert denied.status_code == 403

    internal_list = mysql_app_client.get("/api/internal/video-edit/jobs", headers=developer)
    assert internal_list.status_code == 200
    assert [item["id"] for item in internal_list.json()["data"]] == [job["id"]]

    claim = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/claim",
        headers=developer,
        json={"note": "已分配给剪辑人员 A"},
    )
    assert claim.status_code == 200
    assert claim.json()["data"]["status"] == 2
    assert claim.json()["data"]["status_text"] == "智能剪辑生成中"

    deliver = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/deliver",
        headers=developer,
        json={
            "delivery_file_name": "final-cut.mp4",
            "delivery_file_path": "/deliveries/final-cut.mp4",
            "delivery_url": "https://cdn.example.test/final-cut.mp4",
            "note": "已完成初剪版本",
        },
    )
    assert deliver.status_code == 200
    delivered_job = deliver.json()["data"]
    assert delivered_job["status"] == 3
    assert delivered_job["status_text"] == "视频已生成"
    assert delivered_job["delivery"]["delivery_file_name"] == "final-cut.mp4"

    user_view = mysql_app_client.get(f"/api/video-edit/jobs/{job['id']}", headers=user_headers)
    assert user_view.status_code == 200
    assert user_view.json()["data"]["status"] == 3
    assert "查看交付文件" in user_view.json()["data"]["user_progress_text"]


def test_admin_summary_includes_video_edit_jobs(mysql_conn, mysql_app_client):
    user_headers = auth_headers(mysql_conn, mysql_app_client, "summary-user")
    developer = developer_headers(mysql_conn, mysql_app_client, "summary-admin")
    create_video_edit_job(mysql_app_client, user_headers, "summary")

    response = mysql_app_client.get("/api/admin/summary", headers=developer)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_video_edit_jobs"] == 1
    assert data["pending_video_edit_jobs"] == 1
