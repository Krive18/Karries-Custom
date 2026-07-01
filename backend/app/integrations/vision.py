import base64
import json
from mimetypes import guess_type
from pathlib import Path
from typing import Any, Callable
from urllib import request as urlrequest


from app.schemas.settings import AISettingView
from app.schemas.vision import VisionAnalysisResult

Transport = Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]


class OpenAICompatibleVisionClient:
    def __init__(
        self,
        setting: AISettingView,
        api_key: str,
        transport: Transport | None = None,
    ) -> None:
        self.setting = setting
        self.api_key = api_key
        self.transport = transport or _post_json

    def analyze(self, image_paths: list[str]) -> VisionAnalysisResult:
        payload = self.transport(
            self.setting.base_url,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            {
                "model": self.setting.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "请识别这些图片中的商品、颜色、材质、场景和适合小红书"
                                    "种草的卖点。请只返回 JSON。"
                                ),
                            },
                            *[
                                {
                                    "type": "image_url",
                                    "image_url": {"url": _image_to_data_url(path)},
                                }
                                for path in image_paths
                            ],
                        ],
                    }
                ],
                "temperature": 0.2,
            },
            60,
        )
        content = payload["choices"][0]["message"]["content"]
        payload = json.loads(content)
        return VisionAnalysisResult(provider=self.setting.provider, **payload)


def _image_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    mime_type = guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


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
