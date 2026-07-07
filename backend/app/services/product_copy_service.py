import json
from typing import Any

from app.schemas.content_draft import ContentDraftGenerateRequest


def generate_product_content_draft(
    product: dict,
    account: dict | None,
    request: ContentDraftGenerateRequest,
) -> dict[str, Any]:
    product_name = _clean_text(product.get("product_name")) or "Product"
    brand_name = _clean_text(product.get("brand_name"))
    category = _clean_text(product.get("category"))
    selling_points = _flatten_values(product.get("selling_point"))
    ai_materials = _flatten_values(product.get("ai_material"))
    profile = (account or {}).get("profile") or {}

    title_parts = [brand_name, product_name] if brand_name else [product_name]
    title = " ".join(part for part in title_parts if part).strip()[:100]

    body_lines = [
        f"Product: {product_name}",
        f"Direction: {request.content_direction}",
        f"Tone: {request.tone}",
    ]
    if brand_name:
        body_lines.append(f"Brand: {brand_name}")
    if category:
        body_lines.append(f"Category: {category}")
    if selling_points:
        body_lines.append(f"Selling points: {', '.join(selling_points[:6])}")
    if ai_materials:
        body_lines.append(f"Creative material: {', '.join(ai_materials[:6])}")
    if account:
        display_name = _clean_text(account.get("display_name"))
        if display_name:
            body_lines.append(f"Account: {display_name}")
    for field, label in (
        ("persona", "Persona"),
        ("target_audience", "Audience"),
        ("tone", "Account tone"),
    ):
        value = _clean_text(profile.get(field))
        if value:
            body_lines.append(f"{label}: {value}")
    extra_requirement = request.extra_requirement.strip()
    if extra_requirement:
        body_lines.append(f"Extra requirement: {extra_requirement}")

    tags = _tags_from_profile(profile)
    if not tags:
        tags = ["#xiaohongshu", "#seed", "#product"]

    return {
        "title": title or "Product note",
        "body": "\n".join(body_lines),
        "tags": tags[:10],
        "material": {
            "product_id": request.product_id,
            "xhs_account_id": request.xhs_account_id,
            "product_name": product_name,
            "brand_name": brand_name,
            "content_direction": request.content_direction,
        },
        "ai_provider": "local",
        "model_name": "product-copy-template-v1",
        "prompt": {
            "content_direction": request.content_direction,
            "tone": request.tone,
            "extra_requirement": request.extra_requirement,
        },
    }


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _flatten_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        flattened: list[str] = []
        for item in value.values():
            flattened.extend(_flatten_values(item))
        return flattened
    if isinstance(value, (list, tuple, set)):
        flattened = []
        for item in value:
            flattened.extend(_flatten_values(item))
        return flattened
    return [str(value)]


def _tags_from_profile(profile: dict) -> list[str]:
    raw_value = profile.get("tag_preferences") or ""
    try:
        parsed = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    except json.JSONDecodeError:
        parsed = []
    if not isinstance(parsed, list):
        return []
    return [str(tag).strip() for tag in parsed if str(tag).strip()]
