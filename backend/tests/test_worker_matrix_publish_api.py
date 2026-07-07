from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.core.responses import fail, ok


def test_worker_token_dependency_returns_503_when_not_configured():
    from app.core.dependencies import verify_worker_token

    app = FastAPI()
    app.state.config = type("Config", (), {"worker_api_token": ""})()

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request, exc):
        code = "SERVICE_UNAVAILABLE" if exc.status_code == 503 else "UNAUTHORIZED"
        return JSONResponse(status_code=exc.status_code, content=fail(code, str(exc.detail)))

    @app.get("/probe")
    def probe(_auth=Depends(verify_worker_token)):
        return ok({"ready": True})

    response = TestClient(app).get("/probe", headers={"X-Worker-Token": "abc"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
