from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.responses import fail, ok
from app.schemas.ai import ImageCopyRequest
from app.services.ai_copy_service import generate_image_copy


router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/image-copy")
def create_image_copy(request: ImageCopyRequest) -> dict:
    try:
        result = generate_image_copy(request)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=fail("VALIDATION_ERROR", str(exc)),
        )

    return ok(result.model_dump())
