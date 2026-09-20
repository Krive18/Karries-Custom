from pathlib import Path

from app.core.security import create_access_token
from app.repositories.user_repository import UserRepository
from app.repositories.wallet_repository import WalletRepository


MP4_BYTES = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 96
MP3_BYTES = b"ID3\x04\x00\x00\x00\x00\x00\x15" + b"\x00" * 32
SRT_BYTES = b"1\n00:00:00,000 --> 00:00:01,000\nHello\n"


def _customer_headers(
    mysql_conn,
    mysql_app_client,
    suffix: str,
    *,
    initial_credits: int = 1000,
) -> dict[str, str]:
    invite_code = f"INV-TRANSLATION-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=initial_credits,
        max_uses=1,
        expires_time=0,
        remark="ai-translation-api",
    )
    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": f"translation_user_{suffix}",
            "nickname": f"Translation User {suffix}",
            "password": "translation-secret",
            "invite_code": invite_code,
        },
    )
    assert response.status_code == 200, response.text
    return {
        "Authorization": f"Bearer {response.json()['data']['access_token']}"
    }


def _developer_headers(mysql_conn, mysql_app_client, suffix: str) -> dict[str, str]:
    developer_id = UserRepository(mysql_conn).create_user(
        login_name=f"translation_developer_{suffix}",
        nickname="Translation Developer",
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


def _wallet_balance(mysql_app_client, headers: dict[str, str]) -> int:
    response = mysql_app_client.get("/api/wallet", headers=headers)
    assert response.status_code == 200, response.text
    return int(response.json()["data"]["balance"])


def _create_upload_task(
    mysql_app_client,
    headers: dict[str, str],
    suffix: str,
    tmp_path: Path,
) -> dict:
    mysql_app_client.app.state.config.data_dir = tmp_path
    response = mysql_app_client.post(
        "/api/ai-translations/tasks/upload",
        headers=headers,
        data={
            "source_language": "auto",
            "target_language": "en",
            "client_request_id": f"translation-create-{suffix}",
        },
        files={"file": (f"source-{suffix}.mp4", MP4_BYTES, "video/mp4")},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _post_action(
    mysql_app_client,
    developer_headers: dict[str, str],
    task_id: int,
    action: str,
) -> dict:
    response = mysql_app_client.post(
        f"/api/internal/ai-translations/tasks/{task_id}/{action}",
        headers=developer_headers,
        json={"note": f"{action} translation task"},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _deliver(
    mysql_app_client,
    developer_headers: dict[str, str],
    task_id: int,
    client_request_id: str,
    file_name: str,
    *,
    resource_type: str = "video",
    complete_delivery: bool = True,
    file_bytes: bytes = MP4_BYTES,
    mime_type: str = "video/mp4",
):
    return mysql_app_client.post(
        f"/api/internal/ai-translations/tasks/{task_id}/delivery/upload",
        headers=developer_headers,
        data={
            "client_request_id": client_request_id,
            "note": "translated finished video",
            "resource_type": resource_type,
            "complete_delivery": str(complete_delivery).lower(),
        },
        files=[("files", (file_name, file_bytes, mime_type))],
    )


def test_translation_delivery_resources_are_independent_until_completed(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    customer = _customer_headers(mysql_conn, mysql_app_client, "resources")
    developer = _developer_headers(mysql_conn, mysql_app_client, "resources")
    initial_balance = _wallet_balance(mysql_app_client, customer)
    task = _create_upload_task(mysql_app_client, customer, "resources", tmp_path)
    _post_action(mysql_app_client, developer, task["id"], "claim")
    _post_action(mysql_app_client, developer, task["id"], "start")

    voiceover = _deliver(
        mysql_app_client,
        developer,
        task["id"],
        "translation-voiceover",
        "voiceover.mp3",
        resource_type="voiceover",
        complete_delivery=False,
        file_bytes=MP3_BYTES,
        mime_type="audio/mpeg",
    )
    assert voiceover.status_code == 200, voiceover.text
    voiceover_task = voiceover.json()["data"]
    assert voiceover_task["status"] == "in_progress"
    assert voiceover_task["delivery_resource_counts"] == {
        "video": 0,
        "voiceover": 1,
        "subtitle": 0,
    }
    assert _wallet_balance(mysql_app_client, customer) == initial_balance

    subtitle = _deliver(
        mysql_app_client,
        developer,
        task["id"],
        "translation-subtitle",
        "captions.srt",
        resource_type="subtitle",
        complete_delivery=False,
        file_bytes=SRT_BYTES,
        mime_type="application/x-subrip",
    )
    assert subtitle.status_code == 200, subtitle.text
    subtitle_task = subtitle.json()["data"]
    assert subtitle_task["delivery_resource_counts"]["subtitle"] == 1
    assert subtitle_task["charged_credit_cost"] == 0

    completed = mysql_app_client.post(
        f"/api/internal/ai-translations/tasks/{task['id']}/delivery/complete",
        headers=developer,
        json={"note": "本次资源交付完成"},
    )
    assert completed.status_code == 200, completed.text
    completed_task = completed.json()["data"]
    assert completed_task["status"] == "awaiting_customer"
    assert completed_task["charged_credit_cost"] == 60
    assert _wallet_balance(mysql_app_client, customer) == initial_balance - 60

    completed_again = mysql_app_client.post(
        f"/api/internal/ai-translations/tasks/{task['id']}/delivery/complete",
        headers=developer,
        json={"note": "重复完成"},
    )
    assert completed_again.status_code == 200, completed_again.text
    assert _wallet_balance(mysql_app_client, customer) == initial_balance - 60


def test_translation_charges_once_on_first_successful_delivery(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    customer = _customer_headers(mysql_conn, mysql_app_client, "charge-once")
    developer = _developer_headers(mysql_conn, mysql_app_client, "charge-once")
    initial_balance = _wallet_balance(mysql_app_client, customer)

    task = _create_upload_task(
        mysql_app_client,
        customer,
        "charge-once",
        tmp_path,
    )
    assert task["status"] == "pending"
    assert task["charged_credit_cost"] == 0
    assert _wallet_balance(mysql_app_client, customer) == initial_balance

    claimed = _post_action(mysql_app_client, developer, task["id"], "claim")
    assert claimed["status"] == "claimed"
    started = _post_action(mysql_app_client, developer, task["id"], "start")
    assert started["status"] == "in_progress"
    assert _wallet_balance(mysql_app_client, customer) == initial_balance

    first = _deliver(
        mysql_app_client,
        developer,
        task["id"],
        "translation-delivery-first",
        "translated-v1.mp4",
    )
    assert first.status_code == 200, first.text
    first_task = first.json()["data"]
    assert first_task["status"] == "awaiting_customer"
    assert first_task["charged_credit_cost"] == 60
    assert first_task["delivery_count"] == 1
    assert len(first_task["deliveries"]) == 1
    assert _wallet_balance(mysql_app_client, customer) == initial_balance - 60

    duplicate = _deliver(
        mysql_app_client,
        developer,
        task["id"],
        "translation-delivery-first",
        "duplicate-v1.mp4",
    )
    assert duplicate.status_code == 200, duplicate.text
    duplicate_task = duplicate.json()["data"]
    assert duplicate_task["delivery_count"] == 1
    assert len(duplicate_task["deliveries"]) == 1
    assert _wallet_balance(mysql_app_client, customer) == initial_balance - 60

    revision = mysql_app_client.post(
        f"/api/ai-translations/tasks/{task['id']}/revision",
        headers=customer,
        json={"feedback": "Please correct the terminology and timing."},
    )
    assert revision.status_code == 200, revision.text
    assert revision.json()["data"]["status"] == "revision_requested"

    restarted = _post_action(mysql_app_client, developer, task["id"], "start")
    assert restarted["status"] == "in_progress"
    second = _deliver(
        mysql_app_client,
        developer,
        task["id"],
        "translation-delivery-second",
        "translated-v2.mp4",
    )
    assert second.status_code == 200, second.text
    second_task = second.json()["data"]
    assert second_task["status"] == "awaiting_customer"
    assert second_task["charged_credit_cost"] == 60
    assert second_task["delivery_count"] == 2
    assert [item["delivery_no"] for item in second_task["deliveries"]] == [2, 1]
    assert _wallet_balance(mysql_app_client, customer) == initial_balance - 60

    accepted = mysql_app_client.post(
        f"/api/ai-translations/tasks/{task['id']}/accept",
        headers=customer,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["status"] == "completed"

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select count(*) as ledger_count,
                   coalesce(sum(change_amount), 0) as total_amount
            from credit_ledger
            where business_type = 'ai_translation_delivery'
              and business_id = %s
            """,
            (task["id"],),
        )
        ledger = cursor.fetchone()
    assert int(ledger["ledger_count"]) == 1
    assert int(ledger["total_amount"]) == -60


def test_translation_pending_task_can_cancel_and_is_user_scoped(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    owner = _customer_headers(mysql_conn, mysql_app_client, "owner")
    other = _customer_headers(mysql_conn, mysql_app_client, "other")
    task = _create_upload_task(mysql_app_client, owner, "owner", tmp_path)

    hidden = mysql_app_client.get(
        f"/api/ai-translations/tasks/{task['id']}",
        headers=other,
    )
    assert hidden.status_code == 404

    cancelled = mysql_app_client.post(
        f"/api/ai-translations/tasks/{task['id']}/cancel",
        headers=owner,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"

    second_cancel = mysql_app_client.post(
        f"/api/ai-translations/tasks/{task['id']}/cancel",
        headers=owner,
    )
    assert second_cancel.status_code == 409


def test_translation_delivery_rolls_back_when_balance_is_insufficient(
    mysql_conn,
    mysql_app_client,
    tmp_path,
):
    customer = _customer_headers(
        mysql_conn,
        mysql_app_client,
        "insufficient",
        initial_credits=50,
    )
    user = UserRepository(mysql_conn).get_by_login_name(
        "translation_user_insufficient"
    )
    assert user is not None
    current_balance = _wallet_balance(mysql_app_client, customer)
    WalletRepository(mysql_conn).adjust_credits(
        int(user["id"]),
        50 - current_balance,
        "test_setup",
        0,
        "建立 AI 翻译余额不足场景",
    )
    developer = _developer_headers(mysql_conn, mysql_app_client, "insufficient")
    task = _create_upload_task(
        mysql_app_client,
        customer,
        "insufficient",
        tmp_path,
    )
    _post_action(mysql_app_client, developer, task["id"], "claim")
    _post_action(mysql_app_client, developer, task["id"], "start")

    response = _deliver(
        mysql_app_client,
        developer,
        task["id"],
        "translation-delivery-no-credit",
        "should-not-persist.mp4",
    )
    assert response.status_code == 409, response.text
    assert _wallet_balance(mysql_app_client, customer) == 50

    current = mysql_app_client.get(
        f"/api/ai-translations/tasks/{task['id']}",
        headers=customer,
    )
    assert current.status_code == 200
    current_task = current.json()["data"]
    assert current_task["status"] == "in_progress"
    assert current_task["delivery_count"] == 0
    assert current_task["charged_credit_cost"] == 0
    assert current_task["deliveries"] == []
