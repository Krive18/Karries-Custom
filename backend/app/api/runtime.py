from fastapi import APIRouter, Request

from app.core.responses import ok
from app.runtime.browser_runtime import mark_browser_installed
from app.services.runtime_service import check_runtime


router = APIRouter(prefix="/api/runtime", tags=["runtime"])


@router.get("/check")
def runtime_check(request: Request) -> dict:
    return ok(check_runtime(request.app.state.config.runtime_dir))


@router.post("/install-browser")
def install_browser(request: Request) -> dict:
    marker = mark_browser_installed(request.app.state.config.runtime_dir)
    return ok({"marker": str(marker)})
