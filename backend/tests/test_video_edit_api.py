import json
import time
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote

from app.core.security import create_access_token
from app.repositories.user_repository import UserRepository


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
MP4_BYTES = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64
MOV_BYTES = b"\x00\x00\x00\x18ftypqt  " + b"\x00" * 64
MP3_BYTES = b"ID3\x04\x00\x00\x00\x00\x00\x15" + b"\x00" * 32
SRT_BYTES = "1\n00:00:00,000 --> 00:00:02,000\n欢迎使用禾一斯\n".encode()
INITIAL_CREDITS = 1000


def auth_headers(mysql_conn, mysql_app_client, suffix: str) -> dict[str, str]:
    invite_code = f"INV-VIDEO-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=INITIAL_CREDITS,
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


def manager_headers(mysql_conn, mysql_app_client, suffix: str) -> dict[str, str]:
    manager_id = UserRepository(mysql_conn).create_user(
        login_name=f"manager_{suffix}",
        nickname="Client Owner",
        password_hash="not-used-by-token-auth",
        user_role="client_owner",
        invite_code="",
    )
    token = create_access_token(
        {"user_id": manager_id, "tenant_id": 1, "role": "client_owner"},
        mysql_app_client.app.state.config.auth.token_secret,
        mysql_app_client.app.state.config.auth.access_token_seconds,
    )
    return {"Authorization": f"Bearer {token}"}


def create_product_asset(
    mysql_app_client,
    headers: dict[str, str],
    suffix: str,
    tmp_path: Path,
) -> dict:
    mysql_app_client.app.state.config.data_dir = tmp_path
    folder_response = mysql_app_client.post(
        "/api/material-library/folders",
        headers=headers,
        json={"parent_id": 0, "folder_name": f"视频素材-{suffix}"},
    )
    assert folder_response.status_code == 200
    folder_id = folder_response.json()["data"]["id"]

    upload_response = mysql_app_client.post(
        "/api/material-library/assets/upload",
        headers=headers,
        params={"folder_id": folder_id},
        files={"file": (f"product-{suffix}.png", PNG_BYTES, "image/png")},
    )
    assert upload_response.status_code == 200
    return upload_response.json()["data"]


def create_xhs_account(
    mysql_app_client,
    headers: dict[str, str],
    suffix: str,
) -> dict:
    response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=headers,
        json={
            "display_name": f"禾一斯矩阵账号-{suffix}",
            "account_group": "video",
            "daily_limit": 2,
            "min_interval_minutes": 360,
            "profile": {
                "domain_name": "美妆种草",
                "persona": "自然真诚的穿搭与美妆顾问",
                "tag_preferences": "[\"#禾一斯\", \"#美妆种草\"]",
                "word_count_preference": 350,
            },
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def create_video_edit_job(
    mysql_app_client,
    headers: dict[str, str],
    suffix: str,
    tmp_path: Path,
    creation_mode: str = "standard",
) -> dict:
    asset = create_product_asset(mysql_app_client, headers, suffix, tmp_path)
    account = create_xhs_account(mysql_app_client, headers, suffix)
    response = mysql_app_client.post(
        "/api/video-edit/jobs",
        headers=headers,
        json={
            "job_title": f"禾一斯新品种草剪辑 {suffix}",
            "post_title": f"新品上新 {suffix}",
            "post_body": "轻松展示产品细节和真实使用场景。",
            "post_tags": ["禾一斯", "新品种草"],
            "script_text": "前3秒展示产品细节，中段补充佩戴场景，结尾引导收藏咨询。",
            "requirement_text": "整体节奏自然，保留高级感，不要过度营销。",
            "creation_mode": creation_mode,
            "materials": [
                {
                    "material_file_id": asset["id"],
                    "file_name": asset["file_name"],
                    "file_type": asset["file_type"],
                    "file_path": "",
                    "mime_type": asset["mime_type"],
                    "file_size": asset["file_size"],
                    "remark": "客户选用的产品素材",
                }
            ],
            "xhs_account_id": account["id"],
            "planned_publish_time": int(time.time()) + 24 * 60 * 60 + 300,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_pro_video_creation_uses_price_snapshot_and_charges_once(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    user_headers = auth_headers(mysql_conn, mysql_app_client, "pro-price")
    developer = developer_headers(mysql_conn, mysql_app_client, "pro-price")
    balance_before = mysql_app_client.get(
        "/api/wallet",
        headers=user_headers,
    ).json()["data"]["balance"]

    job = create_video_edit_job(
        mysql_app_client,
        user_headers,
        "pro-price",
        tmp_path,
        creation_mode="pro",
    )
    assert job["creation_mode"] == "pro"
    assert job["creation_mode_label"] == "AI智能创作 Pro"
    assert job["credit_cost"] == 180
    assert job["request_snapshot"]["creation_mode"] == "pro"
    assert job["request_snapshot"]["credit_cost"] == 180
    assert job["request_snapshot"]["script_text"] == job["script_text"]
    assert job["request_snapshot"]["materials"] == job["materials"]

    claim = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/claim",
        headers=developer,
        json={"note": "开始 Pro 制作"},
    )
    assert claim.status_code == 200, claim.text

    first = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
        headers=developer,
        data={"resource_type": "video", "note": "Pro 成片"},
        files={"file": ("pro-v1.mp4", MP4_BYTES, "video/mp4")},
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["credit_cost"] == 180
    balance_after_first = mysql_app_client.get(
        "/api/wallet",
        headers=user_headers,
    ).json()["data"]["balance"]
    assert balance_after_first == balance_before - 180

    replacement = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
        headers=developer,
        data={"resource_type": "video", "note": "替换成片"},
        files={"file": ("pro-v2.mp4", MP4_BYTES, "video/mp4")},
    )
    assert replacement.status_code == 200, replacement.text
    balance_after_replacement = mysql_app_client.get(
        "/api/wallet",
        headers=user_headers,
    ).json()["data"]["balance"]
    assert balance_after_replacement == balance_after_first

    history = mysql_app_client.get(
        f"/api/video-edit/jobs/{job['id']}/history",
        headers=user_headers,
    )
    assert history.status_code == 200, history.text
    history_data = history.json()["data"]
    assert history_data["request_snapshot"]["creation_mode"] == "pro"
    assert len(history_data["delivery_versions"]) == 2


def test_user_creates_video_edit_job_with_24_hour_progress(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    headers = auth_headers(mysql_conn, mysql_app_client, "create")
    before = int(time.time())
    balance_before = mysql_app_client.get(
        "/api/wallet",
        headers=headers,
    ).json()["data"]["balance"]

    job = create_video_edit_job(mysql_app_client, headers, "create", tmp_path)

    assert job["job_title"] == "禾一斯新品种草剪辑 create"
    assert job["post_title"] == "新品上新 create"
    assert job["post_body"] == "轻松展示产品细节和真实使用场景。"
    assert job["post_tags"] == ["禾一斯", "新品种草"]
    assert job["status"] == 1
    assert job["status_name"] == "submitted"
    assert job["status_text"] == "视频待生成"
    assert "24 小时内完成" in job["user_progress_text"]
    assert before + 24 * 60 * 60 <= job["expected_delivery_time"]
    assert job["expected_delivery_time"] <= int(time.time()) + 24 * 60 * 60
    assert job["materials"][0]["file_type"] == "image"
    assert job["credit_cost"] == 160
    assert job["publish_credit_cost"] == 20
    assert job["total_credit_cost"] == 180
    assert job["publish_plan_id"] > 0
    assert job["publish_item_id"] > 0
    assert job["review_status"] == "draft"

    listing = mysql_app_client.get("/api/video-edit/jobs", headers=headers)
    wallet = mysql_app_client.get("/api/wallet", headers=headers)

    assert listing.status_code == 200
    rows = listing.json()["data"]
    assert len(rows) == 1
    assert rows[0]["id"] == job["id"]
    assert wallet.status_code == 200
    assert wallet.json()["data"]["balance"] == balance_before
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select count(*) as charge_count
            from credit_ledger
            where business_type in ('video_production', 'scheduled_publish')
              and business_id in (%s, %s)
            """,
            (job["id"], job["publish_item_id"]),
        )
        assert cursor.fetchone()["charge_count"] == 0


def test_user_creates_video_job_without_publish_account_or_schedule(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    headers = auth_headers(mysql_conn, mysql_app_client, "no-publish-fields")
    asset = create_product_asset(mysql_app_client, headers, "no-publish-fields", tmp_path)

    response = mysql_app_client.post(
        "/api/video-edit/jobs",
        headers=headers,
        json={
            "job_title": "仅制作不排期的视频",
            "script_text": "展示产品细节并输出可预览的视频成片。",
            "requirement_text": "无需绑定发布账号或计划时间。",
            "materials": [
                {
                    "material_file_id": asset["id"],
                    "file_name": asset["file_name"],
                    "file_type": asset["file_type"],
                    "mime_type": asset["mime_type"],
                    "file_size": asset["file_size"],
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    job = response.json()["data"]
    assert job["xhs_account_id"] == 0
    assert job["planned_publish_time"] == 0
    assert job["publish_plan_id"] == 0
    assert job["publish_item_id"] == 0
    assert job["publish_credit_cost"] == 0
    assert job["total_credit_cost"] == job["credit_cost"]

    developer = developer_headers(mysql_conn, mysql_app_client, "no-publish-fields")
    claim = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/claim",
        headers=developer,
        json={"note": "开始制作无需排期的视频"},
    )
    assert claim.status_code == 200, claim.text
    delivery = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
        headers=developer,
        data={"resource_type": "video", "note": "仅交付成片，不创建发布计划"},
        files={"file": ("no-schedule.mp4", MP4_BYTES, "video/mp4")},
    )
    assert delivery.status_code == 200, delivery.text
    delivered_job = delivery.json()["data"]
    assert delivered_job["publish_plan_id"] == 0
    assert delivered_job["publish_item_id"] == 0
    assert delivered_job["delivery_version_count"] == 1


def test_video_edit_history_backfills_partial_legacy_request_snapshot(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    headers = auth_headers(mysql_conn, mysql_app_client, "legacy-history")
    job = create_video_edit_job(
        mysql_app_client,
        headers,
        "legacy-history",
        tmp_path,
    )
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            update video_edit_job
            set request_snapshot_json = %s
            where id = %s
            """,
            (
                json.dumps(
                    {
                        "job_title": "legacy saved title",
                        "materials": [],
                    }
                ),
                job["id"],
            ),
        )
    mysql_conn.commit()

    history = mysql_app_client.get(
        f"/api/video-edit/jobs/{job['id']}/history",
        headers=headers,
    )

    assert history.status_code == 200, history.text
    snapshot = history.json()["data"]["request_snapshot"]
    assert snapshot["job_title"] == "legacy saved title"
    assert snapshot["script_text"] == job["script_text"]
    assert snapshot["requirement_text"] == job["requirement_text"]
    assert snapshot["materials"] == job["materials"]
    assert snapshot["creation_mode"] == "standard"
    assert snapshot["credit_cost"] == 160


def test_user_optimizes_video_script_before_submission_without_credit_charge(
    monkeypatch,
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    headers = auth_headers(mysql_conn, mysql_app_client, "optimize")
    asset = create_product_asset(mysql_app_client, headers, "optimize", tmp_path)
    wallet_before = mysql_app_client.get(
        "/api/wallet",
        headers=headers,
    ).json()["data"]["balance"]
    captured_payload: dict = {}
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-video-script-test")

    def fake_transport(_url, _headers, payload, _timeout):
        captured_payload.update(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "0-3秒用产品特写抓住注意力，中段切换真实使用场景，"
                            "结尾自然引导收藏咨询。"
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr("app.integrations.deepseek._post_json", fake_transport)

    response = mysql_app_client.post(
        "/api/video-edit/jobs/script-optimize",
        headers=headers,
        json={
            "script_text": "展示产品，然后介绍使用方式。",
            "requirement_text": "自然真诚，控制在30秒。",
            "material_file_ids": [asset["id"]],
            "adjustment": "增强前三秒吸引力",
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["original_script"] == "展示产品，然后介绍使用方式。"
    assert "0-3秒" in result["optimized_script"]
    assert "product-optimize.png" in captured_payload["messages"][-1]["content"]
    wallet_after = mysql_app_client.get(
        "/api/wallet",
        headers=headers,
    ).json()["data"]["balance"]
    assert wallet_after == wallet_before


def test_user_creates_video_edit_job_from_product_library_asset(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    headers = auth_headers(mysql_conn, mysql_app_client, "library")
    asset = create_product_asset(mysql_app_client, headers, "library", tmp_path)
    account = create_xhs_account(mysql_app_client, headers, "library")

    response = mysql_app_client.post(
        "/api/video-edit/jobs",
        headers=headers,
        json={
            "job_title": "从产品库创建剪辑任务",
            "script_text": "展示产品细节并在结尾引导收藏。",
            "requirement_text": "",
            "materials": [
                {
                    "material_file_id": asset["id"],
                    "file_name": "client-placeholder.png",
                    "file_type": "image",
                    "file_path": "",
                    "mime_type": "image/png",
                    "file_size": 0,
                    "remark": "",
                }
            ],
            "xhs_account_id": account["id"],
            "planned_publish_time": int(time.time()) + 24 * 60 * 60 + 300,
        },
    )

    assert response.status_code == 200
    material = response.json()["data"]["materials"][0]
    assert material["material_file_id"] == asset["id"]
    assert material["file_name"] == "product-library.png"
    assert material["file_size"] == len(PNG_BYTES)
    assert material["remark"] == "产品知识库素材"


def test_user_cannot_read_another_users_video_edit_job(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "other")
    job = create_video_edit_job(
        mysql_app_client,
        owner_headers,
        "owner",
        tmp_path,
    )

    response = mysql_app_client.get(
        f"/api/video-edit/jobs/{job['id']}",
        headers=other_headers,
    )
    listing = mysql_app_client.get("/api/video-edit/jobs", headers=other_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert listing.status_code == 200
    assert listing.json()["data"] == []


def test_rejecting_an_unclaimed_video_job_marks_it_returned_and_cancels_queues(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    user_headers = auth_headers(mysql_conn, mysql_app_client, "reject-unclaimed")
    developer = developer_headers(mysql_conn, mysql_app_client, "reject-unclaimed")
    job = create_video_edit_job(
        mysql_app_client,
        user_headers,
        "reject-unclaimed",
        tmp_path,
    )

    reject = mysql_app_client.put(
        f"/api/video-edit/jobs/{job['id']}/publish-content",
        headers=user_headers,
        json={
            "post_title": job["post_title"],
            "post_body": job["post_body"],
            "post_tags": job["post_tags"],
            "review_status": "rejected",
        },
    )

    assert reject.status_code == 200, reject.text
    returned_job = reject.json()["data"]
    assert returned_job["review_status"] == "rejected"
    assert returned_job["status"] == 5
    assert returned_job["status_name"] == "returned"
    assert returned_job["status_text"] == "已退回"
    assert returned_job["sla_status"] == "returned"
    assert returned_job["operator_user_id"] == 0

    pending_queue = mysql_app_client.get(
        "/api/internal/video-edit/jobs",
        headers=developer,
        params={"status": 1},
    )
    assert pending_queue.status_code == 200
    assert job["id"] not in [item["id"] for item in pending_queue.json()["data"]]

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select status from matrix_publish_item where id = %s",
            (job["publish_item_id"],),
        )
        publish_item = cursor.fetchone()
        cursor.execute(
            "select status from matrix_publish_plan where id = %s",
            (job["publish_plan_id"],),
        )
        publish_plan = cursor.fetchone()

    assert int(publish_item["status"]) == 7
    assert int(publish_plan["status"]) == 7


def test_developer_video_edit_lifecycle(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    user_headers = auth_headers(mysql_conn, mysql_app_client, "lifecycle")
    developer = developer_headers(mysql_conn, mysql_app_client, "lifecycle")
    job = create_video_edit_job(
        mysql_app_client,
        user_headers,
        "lifecycle",
        tmp_path,
    )

    denied = mysql_app_client.get("/api/internal/video-edit/jobs", headers=user_headers)
    assert denied.status_code == 403

    internal_list = mysql_app_client.get(
        "/api/internal/video-edit/jobs",
        headers=developer,
    )
    assert internal_list.status_code == 200
    assert [item["id"] for item in internal_list.json()["data"]] == [job["id"]]
    internal_job = internal_list.json()["data"][0]
    assert internal_job["tenant_name"]
    assert internal_job["user_login_name"] == "video_user_lifecycle"
    assert internal_job["xhs_account_name"] == "禾一斯矩阵账号-lifecycle"
    assert internal_job["sla_status"] in {"normal", "due_soon"}
    assert internal_job["delivery_version_count"] == 0

    material_archive = mysql_app_client.get(
        f"/api/internal/video-edit/jobs/{job['id']}/materials/archive",
        headers=developer,
    )
    assert material_archive.status_code == 200
    with zipfile.ZipFile(BytesIO(material_archive.content)) as archive:
        assert archive.namelist() == ["product-lifecycle.png"]
        assert archive.read("product-lifecycle.png") == PNG_BYTES

    claim = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/claim",
        headers=developer,
        json={"note": "已分配给剪辑人员 A"},
    )
    assert claim.status_code == 200
    assert claim.json()["data"]["status"] == 2
    assert claim.json()["data"]["status_text"] == "视频生成中"

    balance_before_delivery = mysql_app_client.get(
        "/api/wallet",
        headers=user_headers,
    ).json()["data"]["balance"]
    deliver = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
        headers=developer,
        data={"note": "已完成初剪版本"},
        files=[
            ("files", ("final-cut.mp4", MP4_BYTES, "video/mp4")),
            (
                "files",
                ("alternate-cut.mov", MOV_BYTES + b"alternate", "video/quicktime"),
            ),
        ],
    )
    assert deliver.status_code == 200, deliver.text
    delivered_job = deliver.json()["data"]
    assert delivered_job["status"] == 3
    assert delivered_job["status_text"] == "视频待发布"
    assert delivered_job["delivery"]["delivery_file_name"] == "alternate-cut.mov"
    assert delivered_job["delivery_version_count"] == 2
    assert [item["version"] for item in delivered_job["delivery_versions"]] == [1, 2]
    assert [
        item["delivery_file_name"] for item in delivered_job["delivery_versions"]
    ] == ["final-cut.mp4", "alternate-cut.mov"]
    balance_after_delivery = mysql_app_client.get(
        "/api/wallet",
        headers=user_headers,
    ).json()["data"]["balance"]
    assert balance_after_delivery == balance_before_delivery - 160
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select business_type, change_amount, reason
            from credit_ledger
            where business_id in (%s, %s)
              and business_type in ('video_production', 'scheduled_publish')
            order by id asc
            """,
            (job["id"], job["publish_item_id"]),
        )
        assert cursor.fetchall() == [
            {
                "business_type": "video_production",
                "change_amount": -160,
                "reason": "视频制作完成",
            }
        ]

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select status from matrix_publish_item where id = %s",
            (job["publish_item_id"],),
        )
        delivered_item = cursor.fetchone()
        cursor.execute(
            "select status from matrix_publish_plan where id = %s",
            (job["publish_plan_id"],),
        )
        delivered_plan = cursor.fetchone()

    assert int(delivered_item["status"]) == 1
    assert int(delivered_plan["status"]) == 2

    review = mysql_app_client.put(
        f"/api/video-edit/jobs/{job['id']}/publish-content",
        headers=user_headers,
        json={
            "post_title": "审核后的视频发布标题",
            "post_body": "审核后的视频发布正文",
            "post_tags": ["禾一斯", "视频种草"],
            "review_status": "confirmed",
        },
    )
    assert review.status_code == 200, review.text
    reviewed_job = review.json()["data"]
    assert reviewed_job["post_title"] == "审核后的视频发布标题"
    assert reviewed_job["post_body"] == "审核后的视频发布正文"
    assert reviewed_job["post_tags"] == ["禾一斯", "视频种草"]
    assert reviewed_job["review_status"] == "confirmed"

    replace_delivery = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
        headers=developer,
        data={"note": "根据内部复核替换为第二版"},
        files={
            "file": (
                "final-cut-v2.mp4",
                MP4_BYTES + b"version-two",
                "video/mp4",
            )
        },
    )
    assert replace_delivery.status_code == 200, replace_delivery.text
    replaced_job = replace_delivery.json()["data"]
    assert replaced_job["delivery_version_count"] == 3
    assert [item["version"] for item in replaced_job["delivery_versions"]] == [1, 2, 3]
    assert replaced_job["delivery"]["delivery_file_name"] == "final-cut-v2.mp4"
    balance_after_replacement = mysql_app_client.get(
        "/api/wallet",
        headers=user_headers,
    ).json()["data"]["balance"]
    assert balance_after_replacement == balance_after_delivery

    first_version = mysql_app_client.get(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/versions/1/content",
        headers=developer,
    )
    history = mysql_app_client.get(
        f"/api/internal/video-edit/jobs/{job['id']}/history",
        headers=developer,
    )
    assert first_version.status_code == 200
    assert first_version.content == MP4_BYTES
    assert history.status_code == 200
    assert [entry["action"] for entry in history.json()["data"]] == [
        "video_delivery_replaced",
        "video_delivery_replaced",
        "video_delivery_uploaded",
        "video_job_claimed",
    ]

    user_view = mysql_app_client.get(
        f"/api/video-edit/jobs/{job['id']}",
        headers=user_headers,
    )
    user_first_version = mysql_app_client.get(
        f"/api/video-edit/jobs/{job['id']}/delivery/versions/1/content",
        headers={**user_headers, "Range": "bytes=0-7"},
    )
    preview = mysql_app_client.get(
        f"/api/video-edit/jobs/{job['id']}/delivery/content",
        headers=user_headers,
    )
    assert user_view.status_code == 200
    assert user_view.json()["data"]["status"] == 3
    assert user_view.json()["data"]["delivery_version_count"] == 3
    assert len(user_view.json()["data"]["delivery_versions"]) == 3
    assert "可预览" in user_view.json()["data"]["user_progress_text"]
    assert user_first_version.status_code == 206
    assert user_first_version.content == MP4_BYTES[:8]
    assert user_first_version.headers["accept-ranges"] == "bytes"
    assert user_first_version.headers["content-range"] == (
        f"bytes 0-7/{len(MP4_BYTES)}"
    )
    assert "final-cut.mp4" in user_first_version.headers["content-disposition"]
    assert preview.status_code == 200
    assert preview.content == MP4_BYTES + b"version-two"

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select content_type, status, material_json
            from matrix_publish_item
            where id = %s
            """,
            (job["publish_item_id"],),
        )
        publish_item = cursor.fetchone()
        cursor.execute(
            "select status from matrix_publish_plan where id = %s",
            (job["publish_plan_id"],),
        )
        publish_plan = cursor.fetchone()

    assert int(publish_item["status"]) == 2
    assert publish_item["content_type"] == "video"
    publish_material = json.loads(publish_item["material_json"])
    assert Path(publish_material["video_path"]).is_file()
    assert int(publish_plan["status"]) == 3


def test_delivery_resources_are_independent_and_visible_before_video_completion(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    user_headers = auth_headers(mysql_conn, mysql_app_client, "resource-owner")
    developer = developer_headers(mysql_conn, mysql_app_client, "resource-owner")
    job = create_video_edit_job(
        mysql_app_client,
        user_headers,
        "resource-owner",
        tmp_path,
    )
    claim = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/claim",
        headers=developer,
        json={"note": "开始制作"},
    )
    assert claim.status_code == 200

    voiceover = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
        headers=developer,
        data={"resource_type": "voiceover", "note": "口播音频"},
        files={"file": ("voiceover.mp3", MP3_BYTES, "audio/mpeg")},
    )
    assert voiceover.status_code == 200, voiceover.text
    voiceover_job = voiceover.json()["data"]
    assert voiceover_job["status"] == 2
    assert voiceover_job["delivery_version_count"] == 0
    assert voiceover_job["delivery_resource_counts"] == {
        "video": 0,
        "voiceover": 1,
        "subtitle": 0,
    }

    subtitle = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
        headers=developer,
        data={"resource_type": "subtitle", "note": "字幕文件"},
        files={"file": ("captions.srt", SRT_BYTES, "application/x-subrip")},
    )
    assert subtitle.status_code == 200, subtitle.text
    subtitle_job = subtitle.json()["data"]
    assert subtitle_job["status"] == 2
    assert subtitle_job["delivery_resource_counts"]["voiceover"] == 1
    assert subtitle_job["delivery_resource_counts"]["subtitle"] == 1

    user_view = mysql_app_client.get(
        f"/api/video-edit/jobs/{job['id']}",
        headers=user_headers,
    )
    assert user_view.status_code == 200
    assets = user_view.json()["data"]["delivery_assets"]
    assert [(item["resource_type"], item["version"]) for item in assets] == [
        ("voiceover", 1),
        ("subtitle", 1),
    ]

    audio_content = mysql_app_client.get(
        f"/api/video-edit/jobs/{job['id']}/delivery/resources/voiceover/1/content",
        headers={**user_headers, "Range": "bytes=0-9"},
    )
    subtitle_content = mysql_app_client.get(
        f"/api/video-edit/jobs/{job['id']}/delivery/resources/subtitle/1/content",
        headers=user_headers,
    )
    assert audio_content.status_code == 206
    assert audio_content.content == MP3_BYTES[:10]
    assert audio_content.headers["content-type"].startswith("audio/mpeg")
    assert subtitle_content.status_code == 200
    assert subtitle_content.content == SRT_BYTES
    assert subtitle_content.headers["content-type"].startswith("application/x-subrip")

    video = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
        headers=developer,
        data={"resource_type": "video", "note": "最终成片"},
        files={"file": ("final.mp4", MP4_BYTES, "video/mp4")},
    )
    assert video.status_code == 200, video.text
    completed = video.json()["data"]
    assert completed["status"] == 3
    assert completed["delivery_resource_counts"] == {
        "video": 1,
        "voiceover": 1,
        "subtitle": 1,
    }
    assert len(completed["delivery_assets"]) == 3


def test_user_downloads_complete_delivery_archive(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    user_headers = auth_headers(mysql_conn, mysql_app_client, "archive-owner")
    developer = developer_headers(mysql_conn, mysql_app_client, "archive-owner")
    job = create_video_edit_job(
        mysql_app_client,
        user_headers,
        "archive-owner",
        tmp_path,
    )
    claim = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/claim",
        headers=developer,
        json={"note": "开始制作"},
    )
    assert claim.status_code == 200, claim.text

    uploads = [
        ("video", "final.mp4", MP4_BYTES, "video/mp4"),
        ("voiceover", "voiceover.mp3", MP3_BYTES, "audio/mpeg"),
        ("subtitle", "captions.srt", SRT_BYTES, "application/x-subrip"),
    ]
    for resource_type, file_name, body, mime_type in uploads:
        response = mysql_app_client.post(
            f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
            headers=developer,
            data={"resource_type": resource_type, "note": "交付文件"},
            files={"file": (file_name, body, mime_type)},
        )
        assert response.status_code == 200, response.text

    response = mysql_app_client.get(
        f"/api/video-edit/jobs/{job['id']}/delivery/archive",
        headers=user_headers,
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/zip")
    assert "完整交付包.zip" in unquote(response.headers["content-disposition"])
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert archive.read("视频/final.mp4") == MP4_BYTES
        assert archive.read("口播音频/voiceover.mp3") == MP3_BYTES
        assert archive.read("字幕/captions.srt") == SRT_BYTES


def test_delivery_archive_is_owner_scoped(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "archive-scope-owner")
    other_headers = auth_headers(mysql_conn, mysql_app_client, "archive-scope-other")
    developer = developer_headers(mysql_conn, mysql_app_client, "archive-scope")
    job = create_video_edit_job(
        mysql_app_client,
        owner_headers,
        "archive-scope-owner",
        tmp_path,
    )
    mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/claim",
        headers=developer,
        json={"note": "开始制作"},
    )
    upload = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
        headers=developer,
        data={"resource_type": "video", "note": "交付视频"},
        files={"file": ("final.mp4", MP4_BYTES, "video/mp4")},
    )
    assert upload.status_code == 200, upload.text

    response = mysql_app_client.get(
        f"/api/video-edit/jobs/{job['id']}/delivery/archive",
        headers=other_headers,
    )

    assert response.status_code == 404


def test_delivery_archive_requires_assets(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    user_headers = auth_headers(mysql_conn, mysql_app_client, "archive-empty")
    job = create_video_edit_job(
        mysql_app_client,
        user_headers,
        "archive-empty",
        tmp_path,
    )

    response = mysql_app_client.get(
        f"/api/video-edit/jobs/{job['id']}/delivery/archive",
        headers=user_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DELIVERY_ARCHIVE_EMPTY"


def test_delivery_archive_fails_when_recorded_file_is_missing(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    user_headers = auth_headers(mysql_conn, mysql_app_client, "archive-missing")
    developer = developer_headers(mysql_conn, mysql_app_client, "archive-missing")
    job = create_video_edit_job(
        mysql_app_client,
        user_headers,
        "archive-missing",
        tmp_path,
    )
    mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/claim",
        headers=developer,
        json={"note": "开始制作"},
    )
    upload = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
        headers=developer,
        data={"resource_type": "video", "note": "交付视频"},
        files={"file": ("final.mp4", MP4_BYTES, "video/mp4")},
    )
    assert upload.status_code == 200, upload.text
    uploaded_job = upload.json()["data"]
    stored_path = (
        Path(mysql_app_client.app.state.config.data_dir)
        / "video_deliveries"
        / uploaded_job["delivery_assets"][0]["delivery_file_path"]
    )
    stored_path.unlink()

    response = mysql_app_client.get(
        f"/api/video-edit/jobs/{job['id']}/delivery/archive",
        headers=user_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DELIVERY_ARCHIVE_INCOMPLETE"


def test_rejected_video_delivery_becomes_terminal_and_cannot_be_reworked(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    user_headers = auth_headers(mysql_conn, mysql_app_client, "revision-owner")
    original_developer = developer_headers(
        mysql_conn,
        mysql_app_client,
        "revision-owner",
    )
    other_developer = developer_headers(
        mysql_conn,
        mysql_app_client,
        "revision-other",
    )
    job = create_video_edit_job(
        mysql_app_client,
        user_headers,
        "revision-owner",
        tmp_path,
    )

    claim = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/claim",
        headers=original_developer,
        json={"note": "由原制作人员处理"},
    )
    assert claim.status_code == 200, claim.text
    original_operator_id = claim.json()["data"]["operator_user_id"]

    delivery = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
        headers=original_developer,
        data={"note": "初版视频已交付"},
        files={"file": ("revision-v1.mp4", MP4_BYTES, "video/mp4")},
    )
    assert delivery.status_code == 200, delivery.text
    assert delivery.json()["data"]["status"] == 3

    reject = mysql_app_client.put(
        f"/api/video-edit/jobs/{job['id']}/publish-content",
        headers=user_headers,
        json={
            "post_title": "请调整节奏后的标题",
            "post_body": "请根据客户反馈继续优化视频。",
            "post_tags": ["禾一斯", "返工"],
            "review_status": "rejected",
        },
    )
    assert reject.status_code == 200, reject.text
    returned_job = reject.json()["data"]
    assert returned_job["status"] == 5
    assert returned_job["status_name"] == "returned"
    assert returned_job["status_text"] == "已退回"
    assert returned_job["sla_status"] == "returned"
    assert returned_job["review_status"] == "rejected"
    assert returned_job["operator_user_id"] == original_operator_id

    revision_queue = mysql_app_client.get(
        "/api/internal/video-edit/jobs",
        headers=other_developer,
        params={"status": 4},
    )
    assert revision_queue.status_code == 200
    assert [item["id"] for item in revision_queue.json()["data"]] == []

    competing_claim = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/claim",
        headers=other_developer,
        json={"note": "不应接走原制作人员的退回任务"},
    )
    assert competing_claim.status_code == 400

    resume_revision = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/claim",
        headers=original_developer,
        json={"note": "已接收客户反馈，继续修改"},
    )
    assert resume_revision.status_code == 400

    competing_delivery = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/deliver",
        headers=other_developer,
        json={
            "delivery_file_name": "hijack.mp4",
            "delivery_file_path": "deliveries/hijack.mp4",
            "delivery_url": "",
            "note": "不应由其他开发者覆盖交付",
        },
    )
    assert competing_delivery.status_code == 400

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select status from matrix_publish_item where id = %s",
            (job["publish_item_id"],),
        )
        publish_item = cursor.fetchone()
        cursor.execute(
            "select status from matrix_publish_plan where id = %s",
            (job["publish_plan_id"],),
        )
        publish_plan = cursor.fetchone()

    assert int(publish_item["status"]) == 7
    assert int(publish_plan["status"]) == 7


def test_delivered_video_can_request_a_charged_revision_with_feedback(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    user_headers = auth_headers(mysql_conn, mysql_app_client, "paid-revision")
    original_developer = developer_headers(
        mysql_conn,
        mysql_app_client,
        "paid-revision-original",
    )
    revision_developer = developer_headers(
        mysql_conn,
        mysql_app_client,
        "paid-revision-next",
    )
    job = create_video_edit_job(
        mysql_app_client,
        user_headers,
        "paid-revision",
        tmp_path,
    )
    assert mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/claim",
        headers=original_developer,
        json={"note": "制作首版"},
    ).status_code == 200
    first_delivery = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
        headers=original_developer,
        data={"note": "首版交付"},
        files={"file": ("revision-first.mp4", MP4_BYTES, "video/mp4")},
    )
    assert first_delivery.status_code == 200, first_delivery.text
    assert first_delivery.json()["data"]["delivery_version_count"] == 1

    balance_before_revision = mysql_app_client.get(
        "/api/wallet",
        headers=user_headers,
    ).json()["data"]["balance"]
    payload = {
        "feedback": "请缩短前三秒，把产品特写提前，并更换结尾音乐。",
        "client_request_id": "video-revision-request-001",
    }
    revision = mysql_app_client.post(
        f"/api/video-edit/jobs/{job['id']}/revisions",
        headers=user_headers,
        json=payload,
    )
    assert revision.status_code == 200, revision.text
    revised_job = revision.json()["data"]
    assert revised_job["status"] == 4
    assert revised_job["status_name"] == "revision_requested"
    assert revised_job["review_status"] == "draft"
    assert revised_job["revision_count"] == 1
    assert revised_job["latest_revision_feedback"] == payload["feedback"]
    assert revised_job["operator_user_id"] == 0
    assert revised_job["delivery_version_count"] == 1
    assert revised_job["publish_plan_id"] == 0
    assert revised_job["publish_item_id"] == 0

    balance_after_revision = mysql_app_client.get(
        "/api/wallet",
        headers=user_headers,
    ).json()["data"]["balance"]
    assert balance_after_revision == balance_before_revision - 180

    repeated = mysql_app_client.post(
        f"/api/video-edit/jobs/{job['id']}/revisions",
        headers=user_headers,
        json=payload,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["data"]["revision_count"] == 1
    assert mysql_app_client.get(
        "/api/wallet",
        headers=user_headers,
    ).json()["data"]["balance"] == balance_after_revision

    revision_queue = mysql_app_client.get(
        "/api/internal/video-edit/jobs",
        headers=revision_developer,
        params={"status": 4},
    )
    assert revision_queue.status_code == 200
    assert [item["id"] for item in revision_queue.json()["data"]] == [job["id"]]
    assert revision_queue.json()["data"][0]["latest_revision_feedback"] == payload["feedback"]

    claim = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/claim",
        headers=revision_developer,
        json={"note": "已领取客户返修任务"},
    )
    assert claim.status_code == 200, claim.text
    assert claim.json()["data"]["status"] == 2

    second_delivery = mysql_app_client.post(
        f"/api/internal/video-edit/jobs/{job['id']}/delivery/upload",
        headers=revision_developer,
        data={"note": "返修版交付"},
        files={
            "file": (
                "revision-second.mp4",
                MP4_BYTES + b"revision-two",
                "video/mp4",
            )
        },
    )
    assert second_delivery.status_code == 200, second_delivery.text
    completed_job = second_delivery.json()["data"]
    assert completed_job["status"] == 3
    assert completed_job["delivery_version_count"] == 2
    assert mysql_app_client.get(
        "/api/wallet",
        headers=user_headers,
    ).json()["data"]["balance"] == balance_after_revision

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select business_type, change_amount, reason
            from credit_ledger
            where user_id = %s and business_type = 'video_revision'
            """,
            (completed_job["user_id"],),
        )
        assert cursor.fetchall() == [
            {
                "business_type": "video_revision",
                "change_amount": -180,
                "reason": "视频返修任务",
            }
        ]
        cursor.execute(
            """
            select status
            from video_edit_revision_request
            where job_id = %s
            """,
            (job["id"],),
        )
        assert cursor.fetchone()["status"] == "completed"


def test_developer_filters_video_edit_jobs(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    user_headers = auth_headers(mysql_conn, mysql_app_client, "filter")
    developer = developer_headers(mysql_conn, mysql_app_client, "filter")
    job = create_video_edit_job(
        mysql_app_client,
        user_headers,
        "filter",
        tmp_path,
    )

    matched = mysql_app_client.get(
        "/api/internal/video-edit/jobs",
        headers=developer,
        params={"status": 1, "keyword": "新品种草", "sla_status": "normal"},
    )
    missed = mysql_app_client.get(
        "/api/internal/video-edit/jobs",
        headers=developer,
        params={"keyword": "不存在的客户或工单"},
    )

    assert matched.status_code == 200
    assert [item["id"] for item in matched.json()["data"]] == [job["id"]]
    assert missed.status_code == 200
    assert missed.json()["data"] == []


def test_admin_summary_includes_video_edit_jobs(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    user_headers = auth_headers(mysql_conn, mysql_app_client, "summary-user")
    manager = manager_headers(mysql_conn, mysql_app_client, "summary-admin")
    create_video_edit_job(
        mysql_app_client,
        user_headers,
        "summary",
        tmp_path,
    )

    response = mysql_app_client.get("/api/admin/summary", headers=manager)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_video_edit_jobs"] == 1
    assert data["pending_video_edit_jobs"] == 1
