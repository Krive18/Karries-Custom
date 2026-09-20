import os
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_customer_user
from app.core.responses import fail, ok
from app.integrations.deepseek import DeepSeekImageCopyClient
from app.integrations.vision import OpenAICompatibleVisionClient
from app.repositories.content_draft_repository import ContentDraftRepository
from app.repositories.material_library_repository import MaterialLibraryNotFoundError
from app.repositories.setting_repository import SettingRepository
from app.repositories.xhs_account_repository import XHSAccountRepository
from app.schemas.ai import ImageCopyRequest
from app.services.ai_settings_service import get_ai_setting_key, get_ai_settings_view
from app.services.ai_copy_service import generate_image_copy
from app.services.material_library_service import MaterialLibraryService


router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/image-copy")
def create_image_copy(
    payload: ImageCopyRequest,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        account = None
        if payload.xhs_account_id > 0:
            account = XHSAccountRepository(conn).get_for_user(
                user["id"],
                payload.xhs_account_id,
            )
            if account is None:
                return JSONResponse(
                    status_code=404,
                    content=fail("NOT_FOUND", "xhs account not found"),
                )

        if payload.material_ids:
            storage_root = Path(request.app.state.config.data_dir) / "product_materials"
            material_paths = MaterialLibraryService(
                conn,
                storage_root,
            ).resolve_asset_paths(
                user["tenant_id"],
                payload.material_ids,
                required_file_type="image",
            )
            payload = payload.model_copy(
                update={"image_paths": [*payload.image_paths, *material_paths]}
            )

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
            account=account,
        )
        history_id = ContentDraftRepository(conn).create_smart_create_draft(
            user["id"],
            xhs_account_id=payload.xhs_account_id,
            title=result.title,
            body=result.body,
            tags=result.tags,
            material={
                "material_ids": payload.material_ids,
                "image_paths": payload.image_paths,
            },
            prompt={
                "style": payload.style,
                "extra_prompt": payload.extra_prompt,
            },
        )
        result = result.model_copy(update={"history_id": history_id})
    except MaterialLibraryNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", str(exc)),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=fail("VALIDATION_ERROR", str(exc)),
        )

    return ok(result.model_dump())
