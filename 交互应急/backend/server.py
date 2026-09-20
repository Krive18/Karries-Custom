from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"
DATA_DIR = ROOT_DIR / "data"
PRODUCT_DB = DATA_DIR / "product_knowledge_base.json"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"


def json_response(handler: SimpleHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
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


def now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def read_store() -> dict[str, Any]:
    if not PRODUCT_DB.exists():
        return {"products": [], "tasks": []}
    try:
        data = json.loads(PRODUCT_DB.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"products": [], "tasks": []}
    return {
        "products": data.get("products") if isinstance(data.get("products"), list) else [],
        "tasks": data.get("tasks") if isinstance(data.get("tasks"), list) else [],
    }


def write_store(store: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PRODUCT_DB.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json_payload(handler: SimpleHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8")
    return json.loads(raw or "{}")


def normalize_text_list(value: Any, fallback: list[str] | None = None) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = re.split(r"[\n,，、#]+", value)
    else:
        items = fallback or []
    normalized: list[str] = []
    for item in items:
        text = str(item).strip().strip("#")
        if text and text not in normalized:
            normalized.append(text[:40])
    return normalized[:12]


def compact_materials(materials: Any) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    if not isinstance(materials, list):
        return compact
    for item in materials[:12]:
        if not isinstance(item, dict):
            continue
        compact.append({
            "id": item.get("id") or item.get("file_id") or f"asset_{len(compact) + 1:03d}",
            "name": str(item.get("name") or item.get("file_name") or "未命名资料"),
            "kind": item.get("kind") or item.get("file_type") or item.get("type") or "file",
            "type": item.get("type") or "",
            "sizeLabel": item.get("sizeLabel") or "",
            "width": item.get("width"),
            "height": item.get("height"),
            "duration": item.get("duration"),
            "previewUrl": item.get("previewUrl") or "",
            "previewDataUrl": item.get("previewDataUrl") or "",
            "thumbnailUrl": item.get("thumbnailUrl") or "",
            "notes": item.get("notes") or "",
        })
    return compact


def guess_category(text: str) -> str:
    lower_text = text.lower()
    checks = [
        ("服饰配饰", ["项链", "戒指", "耳环", "首饰", "珠宝", "配饰", "服饰", "穿搭", "karries", "禾一斯"]),
        ("护肤美妆", ["护肤", "精华", "面膜", "口红", "彩妆", "补水"]),
        ("家居生活", ["家居", "香薰", "收纳", "摆件", "餐具"]),
        ("食品饮品", ["食品", "饮品", "茶", "咖啡", "零食"]),
        ("母婴用品", ["母婴", "宝宝", "儿童", "婴儿"]),
    ]
    for category, keywords in checks:
        if any(keyword in lower_text for keyword in keywords):
            return category
    return "其他"


def calculate_completeness(product: dict[str, Any]) -> int:
    basic = product.get("basic_info") or {}
    attrs = product.get("product_attributes") or {}
    content = product.get("content_info") or {}
    checks = [
        basic.get("product_name"),
        basic.get("category"),
        basic.get("brand"),
        basic.get("spec"),
        basic.get("price"),
        normalize_text_list(content.get("selling_points")),
        normalize_text_list(content.get("target_users")),
        normalize_text_list(content.get("use_scenarios")),
        attrs.get("features") or attrs.get("usage_method"),
        product.get("assets"),
    ]
    filled = sum(1 for item in checks if item)
    return int(round(filled / len(checks) * 100))


def fallback_product_analysis(payload: dict[str, Any], provider_error: str = "") -> dict[str, Any]:
    materials = compact_materials(payload.get("materials") or [])
    note = str(payload.get("operatorNote") or payload.get("extraPrompt") or "").strip()
    raw_text = " ".join([item["name"] for item in materials] + [note])
    first_name = Path(materials[0]["name"]).stem if materials else "KARRIES 禾一斯产品"
    cleaned_name = re.sub(r"[_\-]+", " ", first_name).strip()[:28] or "KARRIES 禾一斯产品"
    brand = "KARRIES 禾一斯" if re.search(r"karries|禾一斯", raw_text, re.I) else ""
    category = guess_category(raw_text)
    selling_points = [
        "适合小红书种草内容延展",
        "可围绕材质、细节和真实使用场景展开",
        "支持后续生成标题、正文、标签和拍摄脚本",
    ]
    if category == "服饰配饰":
        selling_points = ["视觉质感突出", "适合日常穿搭和礼赠场景", "可围绕细节、光泽和佩戴氛围种草"]

    result = {
        "basic_info": {
            "product_name": cleaned_name,
            "brand": brand,
            "category": category,
            "sku": "",
            "spec": "",
            "price": "",
        },
        "product_attributes": {
            "ingredients_or_materials": [],
            "features": selling_points,
            "usage_method": "请根据产品实际使用方式或佩戴方式补充。",
            "notices": ["价格、规格、材质和功效类信息建议人工确认后再入库。"],
        },
        "content_info": {
            "selling_points": selling_points,
            "pain_points": ["不知道如何提炼产品卖点", "每次创作文案都要重复整理资料"],
            "target_users": ["关注精致生活方式的用户", "小红书种草内容受众"],
            "use_scenarios": ["新品介绍", "门店体验", "日常搭配", "礼赠推荐"],
            "seeding_angles": ["第一眼质感", "细节控会喜欢", "日常也能高级"],
            "title_directions": ["把高级感戴进日常", "这组细节真的很适合发小红书"],
            "forbidden_words": ["最强", "100%有效", "根治", "全网第一"],
            "brand_tone": "自然真诚、精致但不夸张",
        },
        "assets": [
            {
                "file_id": item["id"],
                "file_name": item["name"],
                "file_type": item["kind"],
                "asset_type": "main_image" if index == 0 and item["kind"] == "image" else "raw_file",
                "type": item.get("type") or "",
                "sizeLabel": item.get("sizeLabel") or "",
                "width": item.get("width"),
                "height": item.get("height"),
                "duration": item.get("duration"),
                "previewUrl": item.get("previewUrl") or "",
                "previewDataUrl": item.get("previewDataUrl") or "",
                "thumbnailUrl": item.get("thumbnailUrl") or "",
                "notes": item.get("notes") or "",
                "tags": ["原始资料", "待确认"],
            }
            for index, item in enumerate(materials)
        ],
        "confidence": {
            "product_name": 0.68,
            "brand": 0.66 if brand else 0.38,
            "category": 0.64,
            "price": 0.22,
            "selling_points": 0.76,
        },
        "status": "pending_confirm",
        "completeness": 0,
        "provider": "local",
        "providerError": provider_error,
    }
    result["completeness"] = calculate_completeness(result)
    return result


def build_product_prompt(payload: dict[str, Any]) -> list[dict[str, str]]:
    materials = compact_materials(payload.get("materials") or [])
    operator_note = str(payload.get("operatorNote") or "").strip()
    user_payload = {
        "operator_note": operator_note,
        "materials": materials,
        "required_output": {
            "basic_info": ["product_name", "brand", "category", "sku", "spec", "price"],
            "product_attributes": ["ingredients_or_materials", "features", "usage_method", "notices"],
            "content_info": [
                "selling_points",
                "pain_points",
                "target_users",
                "use_scenarios",
                "seeding_angles",
                "title_directions",
                "forbidden_words",
                "brand_tone",
            ],
            "assets": ["file_id", "file_name", "file_type", "asset_type", "tags"],
            "confidence": ["product_name", "brand", "category", "price", "selling_points"],
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "你是产品知识库信息识别助手，只输出合法 JSON，不输出 markdown。"
                "任务是根据运营人员上传的产品资料元信息和补充说明，提取商品资料、卖点、参数和 AI 创作素材。"
                "如果资料里没有明确价格、规格或 SKU，请留空，不要编造。"
                "selling_points 至少给出 1 条，category 必须在 护肤美妆/食品饮品/家居生活/服饰配饰/母婴用品/其他 中选择。"
                "confidence 使用 0-1 的数字。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False),
        },
    ]


def normalize_product_result(result: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    fallback = fallback_product_analysis(payload)
    basic = merge_non_empty(fallback["basic_info"], result.get("basic_info"))
    attrs = merge_non_empty(fallback["product_attributes"], result.get("product_attributes"))
    content = merge_non_empty(fallback["content_info"], result.get("content_info"))
    for key in ["ingredients_or_materials", "features", "notices"]:
        attrs[key] = normalize_text_list(attrs.get(key), normalize_text_list(fallback["product_attributes"].get(key)))
    for key in ["selling_points", "pain_points", "target_users", "use_scenarios", "seeding_angles", "title_directions", "forbidden_words"]:
        content[key] = normalize_text_list(content.get(key), normalize_text_list(fallback["content_info"].get(key)))

    assets = result.get("assets") if isinstance(result.get("assets"), list) else fallback["assets"]
    fallback_assets = fallback["assets"]
    enriched_assets: list[dict[str, Any]] = []
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict):
            continue
        fallback_asset = fallback_assets[index] if index < len(fallback_assets) else {}
        fallback_key_map = {
            item.get("file_id") or item.get("file_name"): item
            for item in fallback_assets
            if isinstance(item, dict)
        }
        keyed_fallback = fallback_key_map.get(asset.get("file_id") or asset.get("file_name")) or {}
        source = {**fallback_asset, **keyed_fallback, **asset}
        for preview_key in ["previewUrl", "previewDataUrl", "thumbnailUrl", "type", "sizeLabel", "width", "height", "duration", "notes"]:
            if not source.get(preview_key):
                source[preview_key] = fallback_asset.get(preview_key) or keyed_fallback.get(preview_key) or ""
        enriched_assets.append(source)
    assets = enriched_assets or fallback_assets
    confidence = result.get("confidence") if isinstance(result.get("confidence"), dict) else fallback["confidence"]
    normalized = {
        "basic_info": basic,
        "product_attributes": attrs,
        "content_info": content,
        "assets": assets,
        "confidence": confidence,
        "status": "pending_confirm",
        "provider": result.get("provider") or "deepseek",
    }
    normalized["completeness"] = calculate_completeness(normalized)
    return normalized


def call_deepseek_product(payload: dict[str, Any]) -> dict[str, Any]:
    provider = str(payload.get("provider") or "deepseek").strip()
    api_key = str(payload.get("apiKey") or os.getenv("DEEPSEEK_API_KEY", "")).strip()
    model = str(payload.get("model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if not api_key or provider != "deepseek":
        return fallback_product_analysis(payload)

    endpoint = str(payload.get("endpoint") or DEEPSEEK_URL).strip() or DEEPSEEK_URL
    request_body = {
        "model": model,
        "messages": build_product_prompt(payload),
        "response_format": {"type": "json_object"},
        "temperature": 0.25,
        "max_tokens": 2600,
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
        with urllib.request.urlopen(req, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        parsed = parse_deepseek_json(content)
        parsed["provider"] = "deepseek"
        normalized = normalize_product_result(parsed, payload)
        normalized["rawModel"] = model
        return normalized
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        return fallback_product_analysis(payload, provider_error=str(exc))


def merge_non_empty(base: dict[str, Any], incoming: Any) -> dict[str, Any]:
    merged = dict(base)
    if not isinstance(incoming, dict):
        return merged
    for key, value in incoming.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        merged[key] = value
    return merged


def create_product_task(payload: dict[str, Any]) -> dict[str, Any]:
    store = read_store()
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    result = call_deepseek_product(payload)
    task = {
        "task_id": task_id,
        "status": "pending_confirm",
        "progress": 100,
        "source_files": compact_materials(payload.get("materials") or []),
        "ai_result": result,
        "provider": result.get("provider") or "local",
        "model": result.get("rawModel") or payload.get("model") or DEFAULT_MODEL,
        "error_message": result.get("providerError") or "",
        "created_at": now_text(),
        "finished_at": now_text(),
    }
    store["tasks"].insert(0, task)
    store["tasks"] = store["tasks"][:80]
    write_store(store)
    return {"task": task, "productDraft": result}


def validate_product(product: dict[str, Any]) -> str:
    basic = product.get("basic_info") or {}
    content = product.get("content_info") or {}
    if not str(basic.get("product_name") or "").strip():
        return "产品名称不能为空"
    if not str(basic.get("category") or "").strip():
        return "产品分类不能为空"
    if not normalize_text_list(content.get("selling_points")):
        return "核心卖点至少需要 1 条"
    return ""


def import_product(payload: dict[str, Any]) -> dict[str, Any]:
    product = payload.get("product_data") if isinstance(payload.get("product_data"), dict) else payload
    error = validate_product(product)
    if error:
        raise ValueError(error)

    store = read_store()
    product_id = str(product.get("id") or f"product_{uuid.uuid4().hex[:10]}")
    now = now_text()
    normalized = normalize_product_result(product, {"materials": product.get("assets") or []})
    normalized.update({
        "id": product_id,
        "status": "active",
        "source": "ai_upload",
        "task_id": payload.get("task_id") or product.get("task_id") or "",
        "created_at": product.get("created_at") or now,
        "updated_at": now,
    })
    normalized["completeness"] = calculate_completeness(normalized)

    existing_index = next((index for index, item in enumerate(store["products"]) if item.get("id") == product_id), None)
    if existing_index is None:
        store["products"].insert(0, normalized)
    else:
        store["products"][existing_index] = normalized
    write_store(store)
    return {"product": normalized, "products": store["products"]}


def update_product(product_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    store = read_store()
    for index, item in enumerate(store["products"]):
        if item.get("id") == product_id:
            merged = {**item, **payload, "id": product_id, "updated_at": now_text()}
            merged["completeness"] = calculate_completeness(merged)
            store["products"][index] = merged
            write_store(store)
            return {"product": merged}
    raise KeyError("产品不存在")


def delete_product(product_id: str) -> dict[str, Any]:
    store = read_store()
    before = len(store["products"])
    store["products"] = [item for item in store["products"] if item.get("id") != product_id]
    if len(store["products"]) == before:
        raise KeyError("产品不存在")
    write_store(store)
    return {"product_id": product_id, "products": store["products"]}


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

    scene = "爆款图文视频混合素材" if has_video and has_image else ("爆款视频素材" if has_video else "爆款图文截图")
    first_name = Path(names[0]).stem if names else "爆款素材"
    title = trim_title(f"{first_name}爆款拆解")
    body_lines = [
        f"这组{scene}适合围绕「{style}」做复用拆解：先提炼前三秒钩子，再拆出镜头节奏、内容结构、评论区选题和标签组合。",
        f"输出语气保持{tone}，重点是形成可迁移到自有素材的脚本框架，不直接照搬原视频表达。",
        "后续进入智能创作时，应把拆解结果套用到自有产品、授权素材或产品知识库资料中，再生成剪辑方案和发布任务。",
    ]
    insights = [
        f"素材数量：{material_count} 个",
        f"素材类型：{scene}",
        f"可复用方向：{style}",
        f"输出语气：{tone}",
    ]
    for item in materials[:4]:
        insights.append(f"素材观察：{material_label(item)}")

    tags = ["小红书", "爆款拆解", "内容灵感"]
    if has_video:
        tags.append("视频解析")
    if has_image:
        tags.append("图文解析")
    if "产品" in style or "种草" in style:
        tags.append("好物分享")

    result = {
        "provider": "local",
        "title": title,
        "body": "\n\n".join(body_lines),
        "tags": normalize_tags(tags),
        "summary": f"已基于{scene}生成{publish_content_type}方向的爆款拆解结果，可继续迁移到自有内容创作。",
        "mediaInsights": insights,
        "scheduleSuggestion": publish_time if publish_time else "建议选择用户活跃时段发布",
        "publishChecklist": [
            "确认拆解结果只作为创作参考，不直接搬运原素材",
            "确认后续使用自有素材、授权素材或产品知识库资料",
            "确认发布时间晚于当前时间",
        ],
        "riskTips": [
            "爆款解析结果需要人工筛选，不能替代最终发布审核",
            "未配置模型 Key 时将使用本地规则生成基础拆解结果",
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
                "你是小红书爆款内容拆解助手。请只输出合法 json，不能输出 markdown。"
                "用户上传的是别人的爆款视频或图文截图，你的任务是拆解选题、前三秒钩子、镜头节奏、内容结构、标签策略和可迁移到自有素材的脚本。"
                "不要鼓励直接搬运原素材，也不要把拆解结果写成已经可直接照搬发布的内容。"
                "返回字段必须包含 title, body, tags, summary, mediaInsights, scheduleSuggestion, publishChecklist, riskTips。"
                "title 不能超过 20 个中文字符，tags 最多 10 个。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请基于以下爆款素材信息生成拆解 json：\n"
                f"{json.dumps(user_payload, ensure_ascii=False)}\n\n"
                "json 示例："
                '{"title":"爆款内容拆解","body":"开头钩子、内容结构和复用脚本",'
                '"tags":["小红书","爆款拆解"],"summary":"摘要",'
                '"mediaInsights":["钩子观察","镜头节奏"],"scheduleSuggestion":"建议",'
                '"publishChecklist":["审核项"],"riskTips":["风险提示"]}'
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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path in {"/", "/index.html"}:
            self.serve_file(FRONTEND_DIR / "index.html")
            return
        if path.startswith("/assets/"):
            relative_asset = urllib.parse.unquote(path.lstrip("/"))
            asset_path = (FRONTEND_DIR / relative_asset).resolve()
            try:
                asset_path.relative_to(FRONTEND_DIR.resolve())
            except ValueError:
                self.send_error(403, "Forbidden")
                return
            self.serve_file(asset_path)
            return
        if path == "/api/health":
            json_response(self, 200, ok({"status": "ok", "time": int(time.time())}))
            return
        if path == "/api/config/ai-status":
            json_response(self, 200, ok(ai_key_status()))
            return
        if path == "/api/products":
            store = read_store()
            query = urllib.parse.parse_qs(parsed.query)
            keyword = str(query.get("keyword", [""])[0]).strip().lower()
            status = str(query.get("status", [""])[0]).strip()
            products = store["products"]
            if keyword:
                products = [
                    item for item in products
                    if keyword in json.dumps(item, ensure_ascii=False).lower()
                ]
            if status:
                products = [item for item in products if item.get("status") == status]
            json_response(self, 200, ok({"products": products, "total": len(products)}))
            return
        if path.startswith("/api/products/recognition-tasks/"):
            task_id = urllib.parse.unquote(path.rsplit("/", 1)[-1])
            task = next((item for item in read_store()["tasks"] if item.get("task_id") == task_id), None)
            if not task:
                json_response(self, 404, fail("not_found", "识别任务不存在"))
                return
            json_response(self, 200, ok({"task": task}))
            return
        if path.startswith("/api/products/"):
            product_id = urllib.parse.unquote(path.rsplit("/", 1)[-1])
            product = next((item for item in read_store()["products"] if item.get("id") == product_id), None)
            if not product:
                json_response(self, 404, fail("not_found", "产品不存在"))
                return
            json_response(self, 200, ok({"product": product}))
            return
        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        try:
            path = urllib.parse.urlparse(self.path).path
            payload = read_json_payload(self)
            if path == "/api/products/recognize":
                if not payload.get("materials"):
                    json_response(self, 400, fail("empty_materials", "请先上传产品图片、截图或资料文件"))
                    return
                json_response(self, 200, ok(create_product_task(payload)))
                return
            if path == "/api/products/import":
                json_response(self, 200, ok(import_product(payload)))
                return
            if path != "/api/analyze":
                json_response(self, 404, fail("not_found", "接口不存在"))
                return
            materials = payload.get("materials") or []
            if not materials:
                json_response(self, 400, fail("empty_materials", "请先上传图片或视频素材"))
                return
            result = call_deepseek(payload)
            json_response(self, 200, ok(result))
        except json.JSONDecodeError:
            json_response(self, 400, fail("bad_json", "请求内容不是合法 JSON"))
        except ValueError as exc:
            json_response(self, 400, fail("bad_request", str(exc)))
        except Exception as exc:  # noqa: BLE001 - local server should report friendly errors.
            json_response(self, 500, fail("server_error", str(exc)))

    def do_PUT(self) -> None:
        try:
            path = urllib.parse.urlparse(self.path).path
            if not path.startswith("/api/products/"):
                json_response(self, 404, fail("not_found", "接口不存在"))
                return
            product_id = urllib.parse.unquote(path.rsplit("/", 1)[-1])
            json_response(self, 200, ok(update_product(product_id, read_json_payload(self))))
        except json.JSONDecodeError:
            json_response(self, 400, fail("bad_json", "请求内容不是合法 JSON"))
        except KeyError as exc:
            json_response(self, 404, fail("not_found", str(exc)))
        except Exception as exc:  # noqa: BLE001
            json_response(self, 500, fail("server_error", str(exc)))

    def do_DELETE(self) -> None:
        try:
            path = urllib.parse.urlparse(self.path).path
            if not path.startswith("/api/products/"):
                json_response(self, 404, fail("not_found", "接口不存在"))
                return
            product_id = urllib.parse.unquote(path.rsplit("/", 1)[-1])
            json_response(self, 200, ok(delete_product(product_id)))
        except KeyError as exc:
            json_response(self, 404, fail("not_found", str(exc)))
        except Exception as exc:  # noqa: BLE001
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
