import os
from pathlib import Path

from app.integrations.deepseek import DeepSeekImageCopyClient
from app.schemas.ai import ImageCopyRequest, ImageCopyResult


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def generate_image_copy(
    request: ImageCopyRequest,
    client: DeepSeekImageCopyClient | None = None,
) -> ImageCopyResult:
    _validate_image_paths(request.image_paths)
    deepseek_client = client or DeepSeekImageCopyClient(
        api_key=os.getenv("DEEPSEEK_API_KEY")
    )
    return deepseek_client.generate_image_copy(request)


def _validate_image_paths(image_paths: list[str]) -> None:
    if not image_paths:
        raise ValueError("至少选择 1 张图片")

    for image_path in image_paths:
        path = Path(image_path)
        if not path.exists():
            raise ValueError(f"图片不存在: {image_path}")
        if not path.is_file():
            raise ValueError(f"图片不是文件: {image_path}")
        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(f"不支持的图片格式: {path.suffix}")
