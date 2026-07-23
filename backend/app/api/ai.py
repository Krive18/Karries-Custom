import os

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.dependencies import current_user, get_db_connection
from app.core.responses import fail, ok
from app.integrations.deepseek import DeepSeekImageCopyClient
from app.integrations.vision import OpenAICompatibleVisionClient
from app.repositories.setting_repository import SettingRepository
from app.schemas.ai import ImageCopyRequest
from app.services.ai_settings_service import get_ai_setting_key, get_ai_settings_view
from app.services.ai_copy_service import generate_image_copy


router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/image-copy")
def create_image_copy(
    payload: ImageCopyRequest,
    _user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        settings_repo = SettingRepository(conn)
        settings = get_ai_settings_view(settings_repo)
        vision_client = None
        vision_key = get_ai_setting_key(settings_repo, "vision")
        if settings.vision.enabled and vision_key:
            vision_client = OpenAICompatibleVisionClient(settings.vision, vision_key)

        copy_key = get_ai_setting_key(settings_repo, "copywriting") or os.getenv(
            "DEEPSEEK_API_KEY"
        )
        copy_client = DeepSeekImageCopyClient(
            api_key=copy_key,
            base_url=settings.copywriting.base_url,
            model=settings.copywriting.model,
        )

        result = generate_image_copy(
            payload,
            vision_client=vision_client,
            copy_client=copy_client,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=fail("VALIDATION_ERROR", str(exc)),
        )

    return ok(result.model_dump())
