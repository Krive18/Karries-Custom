from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.responses import fail, ok
from app.repositories.setting_repository import SettingRepository
from app.schemas.settings import AI_SETTING_SLOTS, AISettingUpdate
from app.services.ai_settings_service import get_ai_settings_view, setting_key


router = APIRouter(prefix="/api/settings", tags=["settings"])


def _validate_slot(slot: str):
    if slot not in AI_SETTING_SLOTS:
        return JSONResponse(
            status_code=400,
            content=fail("VALIDATION_ERROR", "未知 AI 配置类型"),
        )
    return None


@router.get("/ai")
def get_ai_settings(request: Request) -> dict:
    repo = SettingRepository(request.app.state.conn)
    return ok(get_ai_settings_view(repo).model_dump())


@router.put("/ai/{slot}")
def save_ai_setting(slot: str, payload: AISettingUpdate, request: Request):
    invalid = _validate_slot(slot)
    if invalid is not None:
        return invalid

    repo = SettingRepository(request.app.state.conn)
    repo.set(setting_key(slot, "provider"), payload.provider)
    if payload.api_key:
        repo.set(setting_key(slot, "api_key"), payload.api_key)
    repo.set(setting_key(slot, "base_url"), payload.base_url)
    repo.set(setting_key(slot, "model"), payload.model)
    repo.set(setting_key(slot, "enabled"), "true" if payload.enabled else "false")
    return ok(get_ai_settings_view(repo).model_dump())


@router.delete("/ai/{slot}/key")
def clear_ai_setting_key(slot: str, request: Request):
    invalid = _validate_slot(slot)
    if invalid is not None:
        return invalid

    repo = SettingRepository(request.app.state.conn)
    repo.delete(setting_key(slot, "api_key"))
    return ok(get_ai_settings_view(repo).model_dump())
