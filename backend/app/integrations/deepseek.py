from app.schemas.ai import ImageCopyRequest, ImageCopyResult


class DeepSeekImageCopyClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def generate_image_copy(self, request: ImageCopyRequest) -> ImageCopyResult:
        # The live DeepSeek call is intentionally behind this boundary for now.
        # Until it is enabled, both keyed and unkeyed runs return a stable draft.
        style = request.style.strip() or "小红书种草"
        title = "这组图太好种草"
        body_parts = [
            f"按「{style}」风格生成的图片文案。",
            "亮点清晰、语气自然，适合先作为发布草稿再人工微调。",
        ]
        extra_prompt = request.extra_prompt.strip()
        if extra_prompt:
            body_parts.append(f"补充要求：{extra_prompt}")

        return ImageCopyResult(
            title=title[:20],
            body="\n".join(body_parts),
            tags=["小红书", "种草", "图片文案"],
        )
