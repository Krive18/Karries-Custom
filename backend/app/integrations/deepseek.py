import json
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib import request as urlrequest

from app.schemas.ai import ImageCopyRequest, ImageCopyResult
from app.schemas.vision import VisionAnalysisResult


Transport = Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]
DEEPSEEK_CHAT_COMPLETIONS_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-flash"


@dataclass(frozen=True)
class TextGenerationResult:
    content: str
    provider: str
    model_name: str
    latency_ms: int
    input_chars: int
    output_chars: int
    request_id: str = ""


class DeepSeekTextClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEEPSEEK_CHAT_COMPLETIONS_URL,
        model: str = DEEPSEEK_DEFAULT_MODEL,
        transport: Transport | None = None,
    ) -> None:
        if base_url != DEEPSEEK_CHAT_COMPLETIONS_URL:
            raise ValueError("unsupported DeepSeek endpoint")
        self.api_key = api_key
        self.base_url = DEEPSEEK_CHAT_COMPLETIONS_URL
        self.model = model
        self.transport = transport or _post_json

    def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> TextGenerationResult:
        started_at = time.monotonic()
        payload = self.transport(
            self.base_url,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "thinking": {"type": "disabled"},
            },
            60,
        )
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty text generation response")
        return TextGenerationResult(
            content=content,
            provider="deepseek",
            model_name=self.model,
            latency_ms=int((time.monotonic() - started_at) * 1000),
            input_chars=sum(len(message.get("content", "")) for message in messages),
            output_chars=len(content),
            request_id=str(payload.get("id") or "")[:128],
        )


class DeepSeekImageCopyClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEEPSEEK_CHAT_COMPLETIONS_URL,
        model: str = DEEPSEEK_DEFAULT_MODEL,
        transport: Transport | None = None,
    ) -> None:
        if base_url != DEEPSEEK_CHAT_COMPLETIONS_URL:
            raise ValueError("unsupported DeepSeek endpoint")
        self.api_key = api_key or ""
        self.base_url = DEEPSEEK_CHAT_COMPLETIONS_URL
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
        account_context: dict[str, Any] | None = None,
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
                                "account_positioning": account_context or {},
                                "vision_analysis": analysis.model_dump(),
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                "temperature": 0.7,
                "thinking": {"type": "disabled"},
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
    opener = urlrequest.build_opener(_RejectRedirectHandler())
    with opener.open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class _RejectRedirectHandler(urlrequest.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
