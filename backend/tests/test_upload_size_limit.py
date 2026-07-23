import asyncio

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.middleware.upload_size_limit import UploadBodyLimitMiddleware, UploadBodyTooLarge


def _run_app(scope, messages, limit):
    sent = []
    queue = list(messages)

    async def receive():
        return queue.pop(0) if queue else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    async def app(_scope, receive, send):
        while True:
            message = await receive()
            if message["type"] != "http.request" or not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    asyncio.run(UploadBodyLimitMiddleware(app, max_body_bytes=limit)(scope, receive, send))
    return sent


def _upload_scope(headers=()):
    return {
        "type": "http",
        "method": "POST",
        "path": "/api/viral-analysis/jobs/12/upload",
        "headers": list(headers),
    }


def test_upload_limit_rejects_content_length_before_downstream_parser():
    sent = _run_app(
        _upload_scope([(b"content-length", b"11")]),
        [{"type": "http.request", "body": b"ignored", "more_body": False}],
        limit=10,
    )

    assert sent[0]["status"] == 413
    assert b"PAYLOAD_TOO_LARGE" in sent[1]["body"]


def test_upload_limit_rejects_chunked_body_after_accumulated_limit():
    sent = _run_app(
        _upload_scope(),
        [
            {"type": "http.request", "body": b"123456", "more_body": True},
            {"type": "http.request", "body": b"78901", "more_body": False},
        ],
        limit=10,
    )

    assert sent[0]["status"] == 413


def test_upload_limit_does_not_limit_other_routes():
    scope = _upload_scope([(b"content-length", b"99")])
    scope["path"] = "/api/viral-analysis/jobs"

    sent = _run_app(
        scope,
        [{"type": "http.request", "body": b"small", "more_body": False}],
        limit=10,
    )

    assert sent[0]["status"] == 200


def test_upload_limit_reraises_after_downstream_response_has_started():
    sent = []
    queue = [
        {"type": "http.request", "body": b"123456", "more_body": True},
        {"type": "http.request", "body": b"78901", "more_body": False},
    ]

    async def receive():
        return queue.pop(0) if queue else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    async def app(_scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await receive()
        await receive()

    with pytest.raises(UploadBodyTooLarge):
        asyncio.run(UploadBodyLimitMiddleware(app, max_body_bytes=10)(_upload_scope(), receive, send))

    assert [message["type"] for message in sent] == ["http.response.start"]


def test_cors_wraps_early_upload_limit_response():
    app = FastAPI()
    app.add_middleware(UploadBodyLimitMiddleware, max_body_bytes=10)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5175"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/api/viral-analysis/jobs/12/upload")
    async def upload():
        return {"ok": True}

    response = TestClient(app).post(
        "/api/viral-analysis/jobs/12/upload",
        headers={"Origin": "http://localhost:5175", "Content-Length": "11"},
        content=b"small",
    )

    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == "http://localhost:5175"
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
