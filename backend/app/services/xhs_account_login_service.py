import base64
from pathlib import Path

from app.integrations.xiaohongshu import check_cookie, login_account
from app.repositories.xhs_account_login_repository import XHSAccountLoginRepository
from app.repositories.xhs_account_repository import XHSAccountRepository


LOGIN_SESSION_SECONDS = 5 * 60
BROWSER_ERROR_MARKERS = (
    "browsertypelaunch",
    "executable doesn't exist",
    "distribution",
    "无法启动账号授权浏览器",
)


def build_login_state_path(
    data_dir: Path,
    tenant_id: int,
    user_id: int,
    account_id: int,
) -> Path:
    return (
        data_dir
        / "xhs_accounts"
        / str(tenant_id)
        / str(user_id)
        / str(account_id)
        / "storage_state.json"
    )


def to_public_login_session(session: dict) -> dict:
    return {
        "id": session["id"],
        "xhs_account_id": session["xhs_account_id"],
        "status": session["status"],
        "message": session["message"],
        "qrcode_image_data": session["qrcode_image_data"],
        "started_time": session["started_time"],
        "expires_time": session["expires_time"],
        "completed_time": session["completed_time"],
        "update_time": session["update_time"],
    }


def qrcode_payload_to_data_url(payload: dict) -> str:
    image_path = Path(str(payload.get("image_path", "")))
    if image_path.is_file():
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    image_data_url = str(payload.get("image_data_url", ""))
    return image_data_url if image_data_url.startswith("data:image/") else ""


def friendly_login_error(exc: Exception) -> str:
    error_text = str(exc).strip()
    normalized = error_text.lower().replace(" ", "")
    if any(marker.replace(" ", "") in normalized for marker in BROWSER_ERROR_MARKERS):
        return "无法启动账号授权浏览器，请安装或更新 Chrome、Microsoft Edge 后重试"
    if not error_text:
        return "小红书登录失败，请稍后重试"
    return f"小红书登录失败：{error_text}"


async def run_xhs_account_login(
    connect_db,
    *,
    user_id: int,
    account_id: int,
    session_id: int,
    operation_token: str,
    login_state_path: str,
) -> None:
    async def on_qrcode(payload: dict) -> None:
        qrcode_image_data = qrcode_payload_to_data_url(payload)
        conn = connect_db()
        try:
            XHSAccountLoginRepository(conn).mark_qrcode_ready(
                session_id,
                operation_token,
                qrcode_image_data,
            )
        finally:
            conn.close()

    try:
        result = await login_account(
            login_state_path,
            qrcode_callback=on_qrcode,
            headless=True,
        )
        status = str(result.get("status", "failed"))
        success = bool(result.get("success"))
        message = str(result.get("message", "小红书登录失败"))
    except Exception as exc:
        status = "failed"
        success = False
        message = friendly_login_error(exc)

    normalized_status = "success" if success else ("timeout" if status == "timeout" else "failed")
    conn = connect_db()
    try:
        login_repo = XHSAccountLoginRepository(conn)
        completed = login_repo.complete(
            session_id,
            operation_token,
            status=normalized_status,
            message=message,
        )
        if completed:
            XHSAccountRepository(conn).update_login_state(
                user_id,
                account_id,
                status=1 if success else 2,
                login_state_path=login_state_path if success else None,
            )
    finally:
        conn.close()


async def check_xhs_account_login(conn, user_id: int, account_id: int) -> tuple[bool, dict | None]:
    account_repo = XHSAccountRepository(conn)
    account = account_repo.get_for_user(user_id, account_id)
    if account is None:
        return False, None

    login_state_path = str(account["login_state_path"])
    valid = bool(login_state_path) and await check_cookie(login_state_path)
    account_repo.update_login_state(
        user_id,
        account_id,
        status=1 if valid else 2,
    )
    return valid, account_repo.get_for_user(user_id, account_id)
