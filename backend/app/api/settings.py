from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_developer_user
from app.core.responses import fail, ok
from app.core.secret_cipher import encrypt_secret
from app.repositories.setting_repository import SettingRepository
from app.schemas.settings import AI_SETTING_SLOTS, AISettingUpdate
from app.services.ai_settings_service import (
    AISettingConnectionError,
    AISettingKeyMissingError,
    get_ai_settings_view,
    setting_key,
    test_ai_setting_connection,
)


router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(require_developer_user)],
    include_in_schema=False,
)


def _validate_slot(slot: str):
    if slot not in AI_SETTING_SLOTS:
        return JSONResponse(
            status_code=400,
            content=fail("VALIDATION_ERROR", "未知 AI 配置类型"),
        )
    return None


@router.get("/ai")
def get_ai_settings(conn=Depends(get_db_connection)) -> dict:
    repo = SettingRepository(conn)
    return ok(get_ai_settings_view(repo).model_dump())


@router.put("/ai/{slot}")
def save_ai_setting(slot: str, payload: AISettingUpdate, conn=Depends(get_db_connection)):
    invalid = _validate_slot(slot)
    if invalid is not None:
        return invalid

    repo = SettingRepository(conn)
    if payload.api_key:
        repo.set(setting_key(slot, "api_key"), encrypt_secret(payload.api_key))
    repo.set(setting_key(slot, "model"), payload.model)
    repo.set(setting_key(slot, "enabled"), "true" if payload.enabled else "false")
    return ok(get_ai_settings_view(repo).model_dump())


@router.delete("/ai/{slot}/key")
def clear_ai_setting_key(slot: str, conn=Depends(get_db_connection)):
    invalid = _validate_slot(slot)
    if invalid is not None:
        return invalid

    repo = SettingRepository(conn)
    repo.delete(setting_key(slot, "api_key"))
    return ok(get_ai_settings_view(repo).model_dump())


@router.post("/ai/{slot}/test")
def test_ai_setting(slot: str, conn=Depends(get_db_connection)):
    invalid = _validate_slot(slot)
    if invalid is not None:
        return invalid

    repo = SettingRepository(conn)
    try:
        result = test_ai_setting_connection(repo, slot)
    except AISettingKeyMissingError:
        return JSONResponse(
            status_code=400,
            content=fail("AI_KEY_MISSING", "请先保存该 Provider 的 API Key"),
        )
    except AISettingConnectionError:
        return JSONResponse(
            status_code=502,
            content=fail(
                "AI_PROVIDER_UNAVAILABLE",
                "Provider 连接测试失败，请检查 Key、模型名称及服务状态",
            ),
        )
    return ok(result.model_dump() if hasattr(result, "model_dump") else result)
