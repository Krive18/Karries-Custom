import json
from typing import Any, Callable
from urllib import request as urlrequest

from app.schemas.ai import ImageCopyRequest, ImageCopyResult
from app.schemas.vision import VisionAnalysisResult


Transport = Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]


class DeepSeekImageCopyClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com/chat/completions",
        model: str = "deepseek-chat",
        transport: Transport | None = None,
    ) -> None:
        self.api_key = api_key or ""
        self.base_url = base_url
        self.model = model
        self.transport = transport or _post_json

    def generate_image_copy(self, request: ImageCopyRequest) -> ImageCopyResult:
        analysis = VisionAnalysisResult(
            provider="local",
            summary="未启用视觉识图，已基于本地图片素材生成草稿。",
            raw_text="local fallback",
        )
        return self.generate_from_analysis(request, analysis)

    def generate_from_analysis(
        self,
        request: ImageCopyRequest,
        analysis: VisionAnalysisResult,
    ) -> ImageCopyResult:
        if not self.api_key:
            return _fallback_copy(request, analysis)

        payload = self.transport(
            self.base_url,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是小红书种草文案助手。只返回 JSON，字段为 title、body、tags。"
                            "title 最多 20 个中文字符，tags 最多 10 个。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "style": request.style,
                                "extra_prompt": request.extra_prompt,
                                "vision_analysis": analysis.model_dump(),
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                "temperature": 0.7,
            },
            60,
        )
        content = payload["choices"][0]["message"]["content"]
        data = json.loads(content)
        return ImageCopyResult(
            title=str(data["title"])[:20],
            body=str(data["body"]),
            tags=[str(tag) for tag in data["tags"][:10]],
        )


def _fallback_copy(
    request: ImageCopyRequest,
    analysis: VisionAnalysisResult,
) -> ImageCopyResult:
    style = request.style.strip() or "小红书种草"
    body_parts = [
        f"按「{style}」风格生成的图片文案草稿。",
        analysis.summary,
        "当前未启用完整 AI Key，可保存为草稿后人工微调。",
    ]
    extra_prompt = request.extra_prompt.strip()
    if extra_prompt:
        body_parts.append(f"补充要求：{extra_prompt}")
    return ImageCopyResult(
        title="这组图太好种草",
        body="\n".join(body_parts),
        tags=["小红书", "种草", "图片文案"],
    )


def _post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    request = urlrequest.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlrequest.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))
