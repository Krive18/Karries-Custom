from typing import Any


def ok(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None}


def fail(code: str, message: str) -> dict[str, Any]:
    return {"success": False, "data": None, "error": {"code": code, "message": message}}
