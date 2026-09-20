from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from threading import Event

import pytest

from app.db.connection import connect
from app.repositories.material_library_repository import (
    MaterialLibraryNotFoundError,
    MaterialLibraryRepository,
)
from app.repositories.user_repository import UserRepository
from app.services.material_library_service import MaterialLibraryService
from conftest import mysql_test_config


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
MP4_BYTES = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 40


def auth_headers(
    mysql_conn,
    mysql_app_client,
    suffix: str,
    tenant_id: int = 1,
) -> dict[str, str]:
    invite_code = f"INV-MATERIAL-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=0,
        max_uses=1,
        expires_time=0,
        remark="material-library-api",
        tenant_id=tenant_id,
    )
    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": f"material_user_{suffix}",
            "nickname": f"Material User {suffix}",
            "password": "material-secret",
            "invite_code": invite_code,
        },
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_material_library_folder_upload_content_and_delete(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    mysql_app_client.app.state.config.data_dir = tmp_path
    headers = auth_headers(mysql_conn, mysql_app_client, "flow")

    folder_response = mysql_app_client.post(
        "/api/material-library/folders",
        headers=headers,
        json={"parent_id": 0, "folder_name": "新品素材"},
    )
    assert folder_response.status_code == 200
    folder_id = folder_response.json()["data"]["id"]

    upload_response = mysql_app_client.post(
        "/api/material-library/assets/upload",
        headers=headers,
        params={"folder_id": folder_id},
        files={"file": ("product.png", PNG_BYTES, "image/png")},
    )
    assert upload_response.status_code == 200
    uploaded = upload_response.json()["data"]
    assert uploaded["folder_id"] == folder_id
    assert uploaded["file_name"] == "product.png"
    assert uploaded["file_type"] == "image"
    assert "file_path" not in uploaded

    list_response = mysql_app_client.get(
        "/api/material-library/items",
        headers=headers,
        params={"folder_id": folder_id},
    )
    assert list_response.status_code == 200
    listing = list_response.json()["data"]
    assert [item["folder_name"] for item in listing["breadcrumbs"]] == ["新品素材"]
    assert [item["id"] for item in listing["assets"]] == [uploaded["id"]]

    content_response = mysql_app_client.get(
        f"/api/material-library/assets/{uploaded['id']}/content",
        headers=headers,
    )
    assert content_response.status_code == 200
    assert content_response.headers["content-type"] == "image/png"
    assert content_response.content == PNG_BYTES

    not_empty = mysql_app_client.delete(
        f"/api/material-library/folders/{folder_id}",
        headers=headers,
    )
    assert not_empty.status_code == 409
    assert not_empty.json()["error"]["code"] == "FOLDER_NOT_EMPTY"

    delete_asset = mysql_app_client.delete(
        f"/api/material-library/assets/{uploaded['id']}",
        headers=headers,
    )
    assert delete_asset.status_code == 200
    delete_folder = mysql_app_client.delete(
        f"/api/material-library/folders/{folder_id}",
        headers=headers,
    )
    assert delete_folder.status_code == 200


def test_material_library_rejects_root_asset_upload(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    mysql_app_client.app.state.config.data_dir = tmp_path
    headers = auth_headers(mysql_conn, mysql_app_client, "root-upload")

    response = mysql_app_client.post(
        "/api/material-library/assets/upload",
        headers=headers,
        params={"folder_id": 0},
        files={"file": ("product.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ROOT_UPLOAD_FORBIDDEN"
    assert not any(tmp_path.rglob("product.png"))


def test_material_upload_refreshes_folder_ancestors_and_project_group_activity(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    mysql_app_client.app.state.config.data_dir = tmp_path
    headers = auth_headers(mysql_conn, mysql_app_client, "activity-sort", tenant_id=33)
    group = mysql_app_client.post(
        "/api/material-library/project-groups",
        headers=headers,
        json={"group_name": "近期项目"},
    ).json()["data"]
    root = mysql_app_client.post(
        "/api/material-library/folders",
        headers=headers,
        json={
            "project_group_id": group["id"],
            "parent_id": 0,
            "folder_name": "活动素材",
        },
    ).json()["data"]
    child = mysql_app_client.post(
        "/api/material-library/folders",
        headers=headers,
        json={
            "project_group_id": group["id"],
            "parent_id": root["id"],
            "folder_name": "原片",
        },
    ).json()["data"]
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "update product_material_folder set update_time = 1 where tenant_id = 33 and project_group_id = %s",
            (group["id"],),
        )
        cursor.execute(
            "update material_project_group set update_time = 1 where tenant_id = 33 and id = %s",
            (group["id"],),
        )
    mysql_conn.commit()

    uploaded = mysql_app_client.post(
        "/api/material-library/assets/upload",
        headers=headers,
        params={"folder_id": child["id"]},
        files={"file": ("latest.png", PNG_BYTES, "image/png")},
    )
    assert uploaded.status_code == 200
    uploaded_asset = uploaded.json()["data"]
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select update_time from product_material_folder where tenant_id = 33 and id = %s",
            (root["id"],),
        )
        assert int(cursor.fetchone()["update_time"]) > 1
        cursor.execute(
            "select update_time from material_project_group where tenant_id = 33 and id = %s",
            (group["id"],),
        )
        assert int(cursor.fetchone()["update_time"]) > 1
        cursor.execute(
            "update product_material_folder set update_time = 1 where tenant_id = 33 and project_group_id = %s",
            (group["id"],),
        )
        cursor.execute(
            "update material_project_group set update_time = 1 where tenant_id = 33 and id = %s",
            (group["id"],),
        )
    mysql_conn.commit()

    root_listing = mysql_app_client.get(
        "/api/material-library/items",
        headers=headers,
        params={"project_group_id": group["id"], "folder_id": 0},
    ).json()["data"]
    refreshed_group = next(
        item
        for item in mysql_app_client.get(
            "/api/material-library/project-groups",
            headers=headers,
        ).json()["data"]
        if item["id"] == group["id"]
    )

    assert root_listing["folders"][0]["activity_time"] == uploaded_asset["update_time"]
    assert refreshed_group["update_time"] == uploaded_asset["update_time"]


def test_material_library_is_shared_inside_tenant_and_isolated_between_tenants(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    mysql_app_client.app.state.config.data_dir = tmp_path
    owner_headers = auth_headers(mysql_conn, mysql_app_client, "owner", tenant_id=31)
    coworker_headers = auth_headers(
        mysql_conn,
        mysql_app_client,
        "coworker",
        tenant_id=31,
    )
    outsider_headers = auth_headers(
        mysql_conn,
        mysql_app_client,
        "outsider",
        tenant_id=32,
    )

    created = mysql_app_client.post(
        "/api/material-library/folders",
        headers=owner_headers,
        json={"parent_id": 0, "folder_name": "团队共享"},
    )
    assert created.status_code == 200
    folder_id = created.json()["data"]["id"]

    coworker_listing = mysql_app_client.get(
        "/api/material-library/items",
        headers=coworker_headers,
    )
    outsider_listing = mysql_app_client.get(
        "/api/material-library/items",
        headers=outsider_headers,
    )

    assert [item["id"] for item in coworker_listing.json()["data"]["folders"]] == [
        folder_id
    ]
    assert outsider_listing.json()["data"]["folders"] == []


def test_material_project_groups_are_shared_and_tenant_isolated(
    mysql_conn,
    mysql_app_client,
):
    owner = auth_headers(mysql_conn, mysql_app_client, "group-owner", tenant_id=41)
    coworker = auth_headers(mysql_conn, mysql_app_client, "group-peer", tenant_id=41)
    outsider = auth_headers(
        mysql_conn,
        mysql_app_client,
        "group-outsider",
        tenant_id=42,
    )

    created = mysql_app_client.post(
        "/api/material-library/project-groups",
        headers=owner,
        json={"group_name": "秋季上新"},
    )

    assert created.status_code == 200
    group = created.json()["data"]
    assert group["group_name"] == "秋季上新"
    assert group["folder_count"] == 0
    assert group["asset_count"] == 0
    assert group["created_by_user_id"] > 0
    assert group["create_time"] > 0
    assert group["update_time"] > 0

    coworker_groups = mysql_app_client.get(
        "/api/material-library/project-groups",
        headers=coworker,
    )
    outsider_groups = mysql_app_client.get(
        "/api/material-library/project-groups",
        headers=outsider,
    )

    assert coworker_groups.status_code == 200
    assert group["id"] in [item["id"] for item in coworker_groups.json()["data"]]
    assert outsider_groups.status_code == 200
    assert group["id"] not in [item["id"] for item in outsider_groups.json()["data"]]

    outsider_rename = mysql_app_client.patch(
        f"/api/material-library/project-groups/{group['id']}",
        headers=outsider,
        json={"group_name": "跨租户重命名"},
    )
    outsider_delete = mysql_app_client.delete(
        f"/api/material-library/project-groups/{group['id']}",
        headers=outsider,
    )

    assert outsider_rename.status_code == 404
    assert outsider_rename.json()["error"]["code"] == "NOT_FOUND"
    assert outsider_delete.status_code == 404
    assert outsider_delete.json()["error"]["code"] == "NOT_FOUND"


def test_material_project_group_names_are_trimmed_and_unique(
    mysql_conn,
    mysql_app_client,
):
    headers = auth_headers(mysql_conn, mysql_app_client, "group-name", tenant_id=43)

    created = mysql_app_client.post(
        "/api/material-library/project-groups",
        headers=headers,
        json={"group_name": "  品牌素材  "},
    )
    assert created.status_code == 200
    duplicate = mysql_app_client.post(
        "/api/material-library/project-groups",
        headers=headers,
        json={"group_name": "品牌素材"},
    )
    renamed = mysql_app_client.patch(
        f"/api/material-library/project-groups/{created.json()['data']['id']}",
        headers=headers,
        json={"group_name": "  品牌素材库  "},
    )
    whitespace_only = mysql_app_client.post(
        "/api/material-library/project-groups",
        headers=headers,
        json={"group_name": "   "},
    )
    invalid_character = mysql_app_client.post(
        "/api/material-library/project-groups",
        headers=headers,
        json={"group_name": "非法/项目组"},
    )
    structurally_too_long = mysql_app_client.post(
        "/api/material-library/project-groups",
        headers=headers,
        json={"group_name": "x" * 81},
    )

    assert created.json()["data"]["group_name"] == "品牌素材"
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "INVALID_PROJECT_GROUP"
    assert renamed.status_code == 200
    assert renamed.json()["data"]["group_name"] == "品牌素材库"
    assert whitespace_only.status_code == 400
    assert whitespace_only.json()["error"]["code"] == "INVALID_PROJECT_GROUP"
    assert invalid_character.status_code == 400
    assert invalid_character.json()["error"]["code"] == "INVALID_PROJECT_GROUP"
    assert structurally_too_long.status_code == 422


def test_material_project_group_scopes_folder_tree_and_deletion(
    mysql_conn,
    mysql_app_client,
):
    headers = auth_headers(mysql_conn, mysql_app_client, "group-folders", tenant_id=44)
    first_group_response = mysql_app_client.post(
        "/api/material-library/project-groups",
        headers=headers,
        json={"group_name": "第一项目组"},
    )
    assert first_group_response.status_code == 200
    first_group = first_group_response.json()["data"]
    second_group_response = mysql_app_client.post(
        "/api/material-library/project-groups",
        headers=headers,
        json={"group_name": "第二项目组"},
    )
    assert second_group_response.status_code == 200
    second_group = second_group_response.json()["data"]
    empty_group_response = mysql_app_client.post(
        "/api/material-library/project-groups",
        headers=headers,
        json={"group_name": "可删除项目组"},
    )
    assert empty_group_response.status_code == 200
    empty_group = empty_group_response.json()["data"]

    root = mysql_app_client.post(
        "/api/material-library/folders",
        headers=headers,
        json={
            "project_group_id": first_group["id"],
            "parent_id": 0,
            "folder_name": "根目录",
        },
    )
    assert root.status_code == 200
    root_folder = root.json()["data"]
    assert root_folder["project_group_id"] == first_group["id"]

    child = mysql_app_client.post(
        "/api/material-library/folders",
        headers=headers,
        json={
            "project_group_id": first_group["id"],
            "parent_id": root_folder["id"],
            "folder_name": "子目录",
        },
    )
    assert child.status_code == 200
    assert child.json()["data"]["project_group_id"] == first_group["id"]

    mismatch = mysql_app_client.post(
        "/api/material-library/folders",
        headers=headers,
        json={
            "project_group_id": second_group["id"],
            "parent_id": root_folder["id"],
            "folder_name": "跨组子目录",
        },
    )
    assert mismatch.status_code == 404
    assert mismatch.json()["error"]["code"] == "NOT_FOUND"

    first_listing = mysql_app_client.get(
        "/api/material-library/items",
        headers=headers,
        params={"project_group_id": first_group["id"], "folder_id": 0},
    )
    second_listing = mysql_app_client.get(
        "/api/material-library/items",
        headers=headers,
        params={"project_group_id": second_group["id"], "folder_id": 0},
    )
    assert [item["id"] for item in first_listing.json()["data"]["folders"]] == [
        root_folder["id"]
    ]
    assert second_listing.json()["data"]["folders"] == []

    non_empty_delete = mysql_app_client.delete(
        f"/api/material-library/project-groups/{first_group['id']}",
        headers=headers,
    )
    empty_delete = mysql_app_client.delete(
        f"/api/material-library/project-groups/{empty_group['id']}",
        headers=headers,
    )

    assert non_empty_delete.status_code == 409
    assert non_empty_delete.json()["error"]["code"] == "PROJECT_GROUP_NOT_EMPTY"
    assert empty_delete.status_code == 200
    assert empty_delete.json()["data"] == {"deleted": True}


def test_material_project_group_create_folder_serializes_with_group_deletion(
    mysql_conn,
):
    tenant_id = 45
    user_id = 9001
    group = MaterialLibraryRepository(mysql_conn).create_project_group(
        tenant_id,
        user_id,
        "并发删除项目组",
    )
    project_group_id = int(group["id"])
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select id
            from material_project_group
            where tenant_id = %s and id = %s
            for update
            """,
            (tenant_id, project_group_id),
        )
        assert int(cursor.fetchone()["id"]) == project_group_id

    create_conn = connect(mysql_test_config())
    started = Event()

    def create_folder_behind_group_lock():
        started.set()
        return MaterialLibraryRepository(create_conn).create_folder(
            tenant_id,
            user_id,
            project_group_id,
            0,
            "不应成为孤儿的文件夹",
        )

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(create_folder_behind_group_lock)
            assert started.wait(timeout=2)
            with pytest.raises(FutureTimeoutError):
                future.result(timeout=1)

            with mysql_conn.cursor() as cursor:
                cursor.execute(
                    """
                    delete from material_project_group
                    where tenant_id = %s and id = %s
                    """,
                    (tenant_id, project_group_id),
                )
                assert cursor.rowcount == 1
            mysql_conn.commit()

            with pytest.raises(MaterialLibraryNotFoundError):
                future.result(timeout=5)
    finally:
        if mysql_conn.open:
            mysql_conn.rollback()
        create_conn.close()

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select count(*) as orphan_count
            from product_material_folder
            where tenant_id = %s and project_group_id = %s
            """,
            (tenant_id, project_group_id),
        )
        orphan_count = int(cursor.fetchone()["orphan_count"])
    assert orphan_count == 0


def test_material_library_requires_customer_auth(app_client_without_db):
    response = app_client_without_db.get("/api/material-library/items")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_material_library_lists_assets_recursively_for_folder_selection(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    mysql_app_client.app.state.config.data_dir = tmp_path
    headers = auth_headers(mysql_conn, mysql_app_client, "recursive")

    parent = mysql_app_client.post(
        "/api/material-library/folders",
        headers=headers,
        json={"parent_id": 0, "folder_name": "视频素材"},
    ).json()["data"]
    child = mysql_app_client.post(
        "/api/material-library/folders",
        headers=headers,
        json={"parent_id": parent["id"], "folder_name": "产品细节"},
    ).json()["data"]
    parent_video = mysql_app_client.post(
        "/api/material-library/assets/upload",
        headers=headers,
        params={"folder_id": parent["id"]},
        files={"file": ("parent.mp4", MP4_BYTES, "video/mp4")},
    ).json()["data"]
    child_video = mysql_app_client.post(
        "/api/material-library/assets/upload",
        headers=headers,
        params={"folder_id": child["id"]},
        files={"file": ("child.mp4", MP4_BYTES, "video/mp4")},
    ).json()["data"]

    direct_response = mysql_app_client.get(
        "/api/material-library/items",
        headers=headers,
        params={"folder_id": parent["id"], "file_type": "video"},
    )
    recursive_response = mysql_app_client.get(
        "/api/material-library/items",
        headers=headers,
        params={
            "folder_id": parent["id"],
            "file_type": "video",
            "recursive": True,
        },
    )

    assert direct_response.status_code == 200
    assert [item["id"] for item in direct_response.json()["data"]["assets"]] == [
        parent_video["id"]
    ]
    assert recursive_response.status_code == 200
    assert {
        item["id"] for item in recursive_response.json()["data"]["assets"]
    } == {parent_video["id"], child_video["id"]}

    root_recursive_response = mysql_app_client.get(
        "/api/material-library/items",
        headers=headers,
        params={"folder_id": 0, "file_type": "video", "recursive": True},
    )
    assert root_recursive_response.status_code == 200
    assert {
        item["id"] for item in root_recursive_response.json()["data"]["assets"]
    } == {parent_video["id"], child_video["id"]}


def test_material_library_storage_usage_uses_membership_quota(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    mysql_app_client.app.state.config.data_dir = tmp_path
    headers = auth_headers(mysql_conn, mysql_app_client, "storage-usage")
    folder = mysql_app_client.post(
        "/api/material-library/folders",
        headers=headers,
        json={"parent_id": 0, "folder_name": "容量测试"},
    ).json()["data"]
    mysql_app_client.post(
        "/api/material-library/assets/upload",
        headers=headers,
        params={"folder_id": folder["id"]},
        files={"file": ("product.png", PNG_BYTES, "image/png")},
    )

    response = mysql_app_client.get(
        "/api/material-library/storage-usage",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()["data"]
    assert data["used_bytes"] == len(PNG_BYTES)
    assert data["quota_gb"] == 100
    assert data["quota_bytes"] == 100 * 1024**3
    assert data["remaining_bytes"] == data["quota_bytes"] - len(PNG_BYTES)
    assert 0 <= data["usage_percent"] <= 100


def test_material_library_serves_and_caches_video_thumbnail(
    monkeypatch,
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    mysql_app_client.app.state.config.data_dir = tmp_path
    headers = auth_headers(mysql_conn, mysql_app_client, "thumbnail")
    folder = mysql_app_client.post(
        "/api/material-library/folders",
        headers=headers,
        json={"parent_id": 0, "folder_name": "视频封面"},
    ).json()["data"]
    video = mysql_app_client.post(
        "/api/material-library/assets/upload",
        headers=headers,
        params={"folder_id": folder["id"]},
        files={"file": ("cover.mp4", MP4_BYTES, "video/mp4")},
    ).json()["data"]
    generated: list[tuple] = []

    def fake_generate(source_path, thumbnail_path):
        generated.append((source_path, thumbnail_path))
        thumbnail_path.write_bytes(JPEG_BYTES)

    monkeypatch.setattr(
        MaterialLibraryService,
        "_generate_video_thumbnail",
        staticmethod(fake_generate),
        raising=False,
    )

    first = mysql_app_client.get(
        f"/api/material-library/assets/{video['id']}/thumbnail",
        headers=headers,
    )
    second = mysql_app_client.get(
        f"/api/material-library/assets/{video['id']}/thumbnail",
        headers=headers,
    )

    assert first.status_code == 200
    assert first.headers["content-type"] == "image/jpeg"
    assert first.content == JPEG_BYTES
    assert second.status_code == 200
    assert second.content == JPEG_BYTES
    assert len(generated) == 1
