import ast
import base64
import hashlib
import json
import logging
import re
import time
from mimetypes import guess_type
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib import request as urlrequest

from app.schemas.settings import AISettingView
from app.schemas.vision import VisionAnalysisResult
from app.integrations.deepseek import TextGenerationResult

Transport = Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]

logger = logging.getLogger(__name__)


class VisionProviderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)

_VISION_PROMPT = """
Analyze the supplied product image or images for Xiaohongshu content creation.
Return exactly one JSON object and no markdown. Use concise Chinese for all values.
The JSON object must contain these keys:
- summary: overall visual summary
- product_name: product name when visible or inferable
- scene: shooting or usage scene
- colors: array of important colors
- materials: array of visible or likely materials
- selling_points: array of factual selling points supported by the images
- raw_text: readable text found in the images
Do not invent prices, ingredients, certifications, specifications, or efficacy.
""".strip()


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
            self._request_payload(image_paths),
            120,
        )
        content = _extract_text(payload)
        parsed = _normalize_vision_fields(_parse_json_object(content))
        return VisionAnalysisResult(provider=self.setting.provider, **parsed)

    def analyze_media(
        self,
        media_path: str,
        media_type: str,
        prompt: str,
    ) -> TextGenerationResult:
        if media_type not in {"image", "video"}:
            raise ValueError("unsupported multimodal media type")
        if not self.setting.base_url.rstrip("/").endswith("/responses"):
            raise ValueError("multimodal media analysis requires Responses API")

        started_at = time.monotonic()
        payload = self.transport(
            self.setting.base_url,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            {
                "model": self.setting.model,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": f"input_{media_type}",
                                f"{media_type}_url": _file_to_data_url(media_path),
                            },
                        ],
                    }
                ],
                "thinking": {"type": "disabled"},
            },
            300,
        )
        content = _extract_text(payload)
        return TextGenerationResult(
            content=content,
            provider=self.setting.provider,
            model_name=self.setting.model,
            latency_ms=int((time.monotonic() - started_at) * 1000),
            input_chars=len(prompt),
            output_chars=len(content),
            request_id=str(payload.get("id") or "")[:128],
        )

    def test_connection(self) -> TextGenerationResult:
        if not self.setting.base_url.rstrip("/").endswith("/responses"):
            raise ValueError("vision connection test requires Responses API")

        prompt = "连接测试，请只回复 OK"
        started_at = time.monotonic()
        payload = self.transport(
            self.setting.base_url,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            {
                "model": self.setting.model,
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": prompt}],
                    }
                ],
                "thinking": {"type": "disabled"},
            },
            60,
        )
        content = _extract_text(payload)
        return TextGenerationResult(
            content=content,
            provider=self.setting.provider,
            model_name=self.setting.model,
            latency_ms=int((time.monotonic() - started_at) * 1000),
            input_chars=len(prompt),
            output_chars=len(content),
            request_id=str(payload.get("id") or "")[:128],
        )

    def generate_with_images(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[tuple[str, str]],
        image_paths: list[str],
    ) -> TextGenerationResult:
        if not image_paths:
            raise ValueError("at least one image is required")
        if len(image_paths) > 4:
            raise ValueError("at most four images are supported")
        if not self.setting.base_url.rstrip("/").endswith("/responses"):
            raise ValueError("image chat requires Responses API")

        started_at = time.monotonic()
        input_messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            }
        ]
        input_messages.extend(
            {
                "role": role,
                "content": [{"type": "input_text", "text": content}],
            }
            for role, content in history
            if role in {"user", "assistant"} and content.strip()
        )
        input_messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_prompt},
                    *[
                        {"type": "input_image", "image_url": _image_to_data_url(path)}
                        for path in image_paths
                    ],
                ],
            }
        )
        payload = self.transport(
            self.setting.base_url,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            {
                "model": self.setting.model,
                "input": input_messages,
                "thinking": {"type": "disabled"},
            },
            180,
        )
        content = _extract_text(payload)
        return TextGenerationResult(
            content=content,
            provider=self.setting.provider,
            model_name=self.setting.model,
            latency_ms=int((time.monotonic() - started_at) * 1000),
            input_chars=len(system_prompt)
            + len(user_prompt)
            + sum(len(item[1]) for item in history),
            output_chars=len(content),
            request_id=str(payload.get("id") or "")[:128],
        )

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[tuple[str, str]],
    ) -> TextGenerationResult:
        if not self.setting.base_url.rstrip("/").endswith("/responses"):
            raise ValueError("text generation requires Responses API")

        started_at = time.monotonic()
        input_messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            }
        ]
        input_messages.extend(
            {
                "role": role,
                "content": [{"type": "input_text", "text": content}],
            }
            for role, content in history
            if role in {"user", "assistant"} and content.strip()
        )
        input_messages.append(
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            }
        )
        payload = self.transport(
            self.setting.base_url,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            {
                "model": self.setting.model,
                "input": input_messages,
                "thinking": {"type": "disabled"},
            },
            180,
        )
        content = _extract_text(payload)
        return TextGenerationResult(
            content=content,
            provider=self.setting.provider,
            model_name=self.setting.model,
            latency_ms=int((time.monotonic() - started_at) * 1000),
            input_chars=len(system_prompt)
            + len(user_prompt)
            + sum(len(item[1]) for item in history),
            output_chars=len(content),
            request_id=str(payload.get("id") or "")[:128],
        )

    def _request_payload(self, image_paths: list[str]) -> dict[str, Any]:
        if self.setting.base_url.rstrip("/").endswith("/responses"):
            return {
                "model": self.setting.model,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": _VISION_PROMPT},
                            *[
                                {
                                    "type": "input_image",
                                    "image_url": _image_to_data_url(path),
                                }
                                for path in image_paths
                            ],
                        ],
                    }
                ],
                "thinking": {"type": "disabled"},
            }

        return {
            "model": self.setting.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _VISION_PROMPT},
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
        }


def _extract_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct

    for output in payload.get("output", []):
        if not isinstance(output, dict):
            continue
        for content in output.get("content", []):
            if (
                isinstance(content, dict)
                and content.get("type") == "output_text"
                and isinstance(content.get("text"), str)
            ):
                return content["text"]

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("vision provider returned no text output") from exc
    if not isinstance(content, str) or not content.strip():
        raise ValueError("vision provider returned no text output")
    return content


def _parse_json_object(content: str) -> dict[str, Any]:
    normalized = content.strip().lstrip("\ufeff")
    candidates = [normalized]

    fenced = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        normalized,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced is not None:
        candidates.append(fenced.group(1).strip())

    embedded = _extract_embedded_json_object(normalized)
    if embedded is not None:
        candidates.append(embedded)

    for candidate in candidates:
        for prepared in (
            candidate,
            re.sub(r",\s*([}\]])", r"\1", candidate),
        ):
            try:
                value = json.loads(prepared)
            except json.JSONDecodeError:
                try:
                    value = ast.literal_eval(prepared)
                except (SyntaxError, ValueError):
                    continue
            if isinstance(value, dict):
                return value

    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    logger.warning(
        "vision response used natural-language fallback: chars=%s digest=%s",
        len(normalized),
        digest,
    )
    if normalized:
        return {"summary": normalized[:8000]}
    raise ValueError("视觉模型未返回可用的图片分析结果，请重新解析")


def _extract_embedded_json_object(content: str) -> str | None:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"{", content):
        try:
            value, end = decoder.raw_decode(content[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return content[match.start() : match.start() + end]
    return None


def _normalize_vision_fields(value: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(value)
    for field in ("colors", "materials", "selling_points"):
        normalized[field] = _normalize_string_list(normalized.get(field))

    for field in ("summary", "product_name", "scene", "raw_text"):
        item = normalized.get(field, "")
        if item is None:
            normalized[field] = ""
        elif not isinstance(item, str):
            normalized[field] = json.dumps(item, ensure_ascii=False)

    if not normalized.get("summary"):
        normalized["summary"] = (
            normalized.get("product_name")
            or normalized.get("scene")
            or normalized.get("raw_text")
            or "已完成图片内容识别"
        )
    return normalized


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [
            item.strip()
            for item in re.split(r"[\n,，;；、]+", value)
            if item.strip()
        ]
    return [str(value).strip()] if str(value).strip() else []


def _image_to_data_url(image_path: str) -> str:
    return _file_to_data_url(image_path)


def _file_to_data_url(file_path: str) -> str:
    path = Path(file_path)
    mime_type = guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    provider_request = urlrequest.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    opener = urlrequest.build_opener(_RejectRedirectHandler())
    for attempt in range(3):
        try:
            with opener.open(provider_request, timeout=timeout) as response:
                raw_body = response.read()
            try:
                decoded = json.loads(raw_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                if attempt < 2:
                    time.sleep(0.25 * (attempt + 1))
                    continue
                raise VisionProviderError(
                    "invalid_response",
                    "AI provider returned an invalid response",
                ) from exc
            if not isinstance(decoded, dict):
                raise VisionProviderError(
                    "invalid_response",
                    "AI provider returned an invalid response",
                )
            return decoded
        except HTTPError as exc:
            status = int(exc.code)
            transient = status == 429 or status in {500, 502, 503, 504}
            if transient and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            if status in {401, 403}:
                code, message = "authentication", "AI provider authentication failed"
            elif status == 413:
                code, message = "payload_too_large", "AI provider payload is too large"
            elif status == 429:
                code, message = "rate_limit", "AI provider rate limit exceeded"
            elif status >= 500:
                code, message = "upstream", "AI provider is temporarily unavailable"
            else:
                code, message = "invalid_request", "AI provider rejected the request"
            raise VisionProviderError(code, message) from exc
        except VisionProviderError:
            raise
        except (URLError, TimeoutError, OSError) as exc:
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            reason = str(getattr(exc, "reason", exc)).lower()
            code = "timeout" if "timed out" in reason or "timeout" in reason else "transport"
            raise VisionProviderError(code, "AI provider transport failed") from exc

    raise VisionProviderError("transport", "AI provider transport failed")


class _RejectRedirectHandler(urlrequest.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
