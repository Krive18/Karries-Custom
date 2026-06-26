from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"


def json_response(handler: SimpleHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


def ok(data: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None}


def fail(code: str, message: str) -> dict[str, Any]:
    return {"success": False, "data": None, "error": {"code": code, "message": message}}


def ai_key_status() -> dict[str, Any]:
    has_key = bool(os.getenv("DEEPSEEK_API_KEY", "").strip())
    return {
        "provider": "deepseek",
        "hasKey": has_key,
        "source": "environment" if has_key else "none",
    }


def trim_title(title: str) -> str:
    cleaned = re.sub(r"\s+", "", title).strip("，。,. ")
    return (cleaned or "今日灵感上新")[:20]


def normalize_tags(tags: Any) -> list[str]:
    if not isinstance(tags, list):
        return ["小红书", "图文笔记", "灵感"]
    normalized: list[str] = []
    for tag in tags:
        text = str(tag).replace("#", "").strip()
        if text and text not in normalized:
            normalized.append(text[:12])
    return normalized[:10] or ["小红书", "图文笔记", "灵感"]


def material_label(material: dict[str, Any]) -> str:
    name = str(material.get("name") or "未命名素材")
    kind = str(material.get("kind") or "material")
    width = material.get("width")
    height = material.get("height")
    duration = material.get("duration")
    bits = [name, kind]
    if width and height:
        bits.append(f"{width}x{height}")
    if duration:
        bits.append(f"{float(duration):.1f}s")
    return " / ".join(bits)


def build_fallback_copy(payload: dict[str, Any], provider_error: str = "") -> dict[str, Any]:
    materials = payload.get("materials") or []
    style = str(payload.get("style") or "小红书种草")
    tone = str(payload.get("tone") or "自然真诚")
    publish_content_type = str(payload.get("publishContentType") or "图文笔记")
    publish_time = str(payload.get("publishTime") or "待定")
    names = [str(item.get("name") or "") for item in materials]
    has_video = any(str(item.get("kind")) == "video" for item in materials)
    has_image = any(str(item.get("kind")) == "image" for item in materials)
    material_count = len(materials)

    scene = "视频图文混合" if has_video and has_image else ("视频素材" if has_video else "图片素材")
    first_name = Path(names[0]).stem if names else "今日素材"
    title = trim_title(f"{first_name}灵感合集")
    body_lines = [
        f"今天整理了 {material_count} 个{scene}，整体适合做成一篇{style}方向的小红书笔记。",
        f"画面重点可以围绕素材里的主体、使用场景、细节亮点和真实体验展开，语气保持{tone}，先讲第一眼吸引点，再补充细节和行动引导。",
        "发布前建议把真实产品名称、价格、地点、活动时间等信息补齐，避免文案看起来过于模板化。",
    ]
    insights = [
        f"素材数量：{material_count} 个",
        f"素材类型：{scene}",
        f"建议表达：{tone}",
    ]
    for item in materials[:4]:
        insights.append(f"素材观察：{material_label(item)}")

    tags = ["小红书", "图文笔记", "内容灵感"]
    if has_video:
        tags.append("视频解析")
    if has_image:
        tags.append("图片解析")
    if "产品" in style or "种草" in style:
        tags.append("好物分享")

    result = {
        "provider": "local",
        "title": title,
        "body": "\n\n".join(body_lines),
        "tags": normalize_tags(tags),
        "summary": f"已基于{scene}生成{publish_content_type}文案，可直接确认标题、正文、标签和发布任务。",
        "mediaInsights": insights,
        "scheduleSuggestion": publish_time if publish_time else "建议选择用户活跃时段发布",
        "publishChecklist": [
            "检查账号是否已登录小红书创作者中心",
            "确认标题不超过 20 个字符",
            "确认图片或视频顺序正确",
            "确认发布时间晚于当前时间",
        ],
        "riskTips": [
            "发布前请人工确认图片顺序、标题和标签",
            "未配置模型 Key 时将使用本地规则生成基础文案",
        ],
    }
    if provider_error:
        result["providerError"] = provider_error
    return result


def build_deepseek_prompt(payload: dict[str, Any]) -> list[dict[str, str]]:
    materials = payload.get("materials") or []
    compact_materials = [
        {
            "name": item.get("name"),
            "kind": item.get("kind"),
            "type": item.get("type"),
            "sizeLabel": item.get("sizeLabel"),
            "width": item.get("width"),
            "height": item.get("height"),
            "duration": item.get("duration"),
            "dominantColor": item.get("dominantColor"),
            "notes": item.get("notes"),
        }
        for item in materials
    ]
    user_payload = {
        "style": payload.get("style") or "小红书种草",
        "tone": payload.get("tone") or "自然真诚",
        "publishTime": payload.get("publishTime") or "",
        "extraPrompt": payload.get("extraPrompt") or "",
        "materials": compact_materials,
    }
    return [
        {
            "role": "system",
            "content": (
                "你是小红书内容运营助手。请只输出合法 json，不能输出 markdown。"
                "根据本地素材的文件名、类型、尺寸、时长、主色和用户补充信息，生成适合发布的小红书文案。"
                "返回字段必须包含 title, body, tags, summary, mediaInsights, scheduleSuggestion, publishChecklist, riskTips。"
                "title 不能超过 20 个中文字符，tags 最多 10 个。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请基于以下素材信息生成 json：\n"
                f"{json.dumps(user_payload, ensure_ascii=False)}\n\n"
                "json 示例："
                '{"title":"今日灵感上新","body":"正文","tags":["小红书"],'
                '"summary":"摘要","mediaInsights":["观察"],"scheduleSuggestion":"建议",'
                '"publishChecklist":["检查项"],"riskTips":["风险提示"]}'
            ),
        },
    ]


def parse_deepseek_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def call_deepseek(payload: dict[str, Any]) -> dict[str, Any]:
    provider = str(payload.get("provider") or "deepseek").strip()
    api_key = str(payload.get("apiKey") or os.getenv("DEEPSEEK_API_KEY", "")).strip()
    model = str(payload.get("model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if not api_key or provider != "deepseek":
        return build_fallback_copy(payload)

    endpoint = str(payload.get("endpoint") or DEEPSEEK_URL).strip() or DEEPSEEK_URL
    request_body = {
        "model": model,
        "messages": build_deepseek_prompt(payload),
        "response_format": {"type": "json_object"},
        "temperature": 0.8,
        "max_tokens": 1800,
        "stream": False,
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        generated = parse_deepseek_json(content)
        fallback = build_fallback_copy(payload)
        return {
            **fallback,
            **generated,
            "provider": "deepseek",
            "title": trim_title(str(generated.get("title") or fallback["title"])),
            "tags": normalize_tags(generated.get("tags") or fallback["tags"]),
            "rawModel": model,
        }
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        return build_fallback_copy(payload, provider_error=str(exc))


class WorkspaceHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self.serve_file(FRONTEND_DIR / "index.html")
            return
        if self.path == "/api/health":
            json_response(self, 200, ok({"status": "ok", "time": int(time.time())}))
            return
        if self.path == "/api/config/ai-status":
            json_response(self, 200, ok(ai_key_status()))
            return
        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        if self.path != "/api/analyze":
            json_response(self, 404, fail("not_found", "接口不存在"))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw or "{}")
            materials = payload.get("materials") or []
            if not materials:
                json_response(self, 400, fail("empty_materials", "请先上传图片或视频素材"))
                return
            result = call_deepseek(payload)
            json_response(self, 200, ok(result))
        except json.JSONDecodeError:
            json_response(self, 400, fail("bad_json", "请求内容不是合法 JSON"))
        except Exception as exc:  # noqa: BLE001 - local server should report friendly errors.
            json_response(self, 500, fail("server_error", str(exc)))

    def serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404, "Not Found")
            return
        content = path.read_bytes()
        mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stdout.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), format % args))


def main() -> None:
    parser = argparse.ArgumentParser(description="Xiaohongshu local interactive workspace server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), WorkspaceHandler)
    print(f"Workspace server running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
