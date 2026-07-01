import os
from pathlib import Path

from app.integrations.deepseek import DeepSeekImageCopyClient
from app.schemas.ai import ImageCopyRequest, ImageCopyResult
from app.schemas.vision import VisionAnalysisResult


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def generate_image_copy(
    request: ImageCopyRequest,
    client: DeepSeekImageCopyClient | None = None,
    vision_client=None,
    copy_client=None,
) -> ImageCopyResult:
    _validate_image_paths(request.image_paths)
    if vision_client is not None:
        analysis = vision_client.analyze(request.image_paths)
    else:
        analysis = _local_analysis(request.image_paths)

    deepseek_client = copy_client or client or DeepSeekImageCopyClient(
        api_key=os.getenv("DEEPSEEK_API_KEY")
    )
    if hasattr(deepseek_client, "generate_from_analysis"):
        return deepseek_client.generate_from_analysis(request, analysis)
    return deepseek_client.generate_image_copy(request)


def _local_analysis(image_paths: list[str]) -> VisionAnalysisResult:
    names = [Path(path).name for path in image_paths]
    return VisionAnalysisResult(
        provider="local",
        summary=f"未启用视觉识图，已读取 {len(image_paths)} 张本地图片：{', '.join(names)}。",
        raw_text="local material metadata",
    )


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
