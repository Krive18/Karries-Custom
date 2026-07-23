import json


class UploadBodyTooLarge(Exception):
    pass


class UploadBodyLimitMiddleware:
    """Reject oversized upload bodies before Starlette parses multipart data."""

    def __init__(self, app, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or not self._is_upload_path(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        content_length = self._content_length(scope.get("headers", []))
        if content_length is not None and content_length > self.max_body_bytes:
            await self._send_too_large(send)
            return

        total_size = 0

        async def limited_receive():
            nonlocal total_size
            message = await receive()
            if message["type"] == "http.request":
                total_size += len(message.get("body", b""))
                if total_size > self.max_body_bytes:
                    raise UploadBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except UploadBodyTooLarge:
            await self._send_too_large(send)

    def _is_upload_path(self, path: str) -> bool:
        parts = path.strip("/").split("/")
        return (
            len(parts) == 5
            and parts[:3] == ["api", "viral-analysis", "jobs"]
            and parts[3].isdigit()
            and parts[4] == "upload"
        )

    def _content_length(self, headers) -> int | None:
        for key, value in headers:
            if key.lower() != b"content-length":
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        return None

    async def _send_too_large(self, send) -> None:
        payload = json.dumps(
            {
                "success": False,
                "data": None,
                "error": {"code": "PAYLOAD_TOO_LARGE", "message": "upload payload is too large"},
            },
            ensure_ascii=False,
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": payload})
