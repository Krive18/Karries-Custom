from contextlib import asynccontextmanager

import pymysql
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.accounts import router as accounts_router
from app.api.admin import router as admin_router
from app.api.admin_inspiration import router as admin_inspiration_router
from app.api.auth import router as auth_router
from app.api.ai import router as ai_router
from app.api.content_drafts import router as content_drafts_router
from app.api.developer_viral_analysis import router as developer_viral_analysis_router
from app.api.inspiration import router as inspiration_router
from app.api.matrix_plans import router as matrix_plans_router
from app.api.products import router as products_router
from app.api.runtime import router as runtime_router
from app.api.settings import router as settings_router
from app.api.tasks import router as tasks_router
from app.api.video_edit import internal_router as internal_video_edit_router
from app.api.video_edit import router as video_edit_router
from app.api.wallet import router as wallet_router
from app.api.worker_matrix_publish import router as worker_matrix_publish_router
from app.api.xhs_accounts import router as xhs_accounts_router
from app.api.admin_viral_analysis import router as admin_viral_analysis_router
from app.api.viral_analysis import router as viral_analysis_router
from app.core.config import default_config
from app.core.responses import fail, ok
from app.db.connection import connect
from app.db.errors import DatabaseConstraintError
from app.db.migrations import migrate
from app.middleware.upload_size_limit import UploadBodyLimitMiddleware


def create_app() -> FastAPI:
    config = default_config()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        conn = connect(config.mysql)
        try:
            migrate(conn)
        finally:
            conn.close()

        try:
            yield
        finally:
            _app.state.conn = None

    app = FastAPI(title="Xiaohongshu Publisher Backend", lifespan=lifespan)
    app.state.config = config
    app.state.conn = None
    app.state.connect_db = lambda: connect(config.mysql)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:3000",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5175",
            "http://localhost:5175",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        UploadBodyLimitMiddleware,
        max_body_bytes=200 * 1024 * 1024 + 2 * 1024 * 1024,
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request, _exc):
        return JSONResponse(
            status_code=422,
            content=fail("VALIDATION_ERROR", "请求参数格式不正确"),
        )

    @app.exception_handler(pymysql.err.IntegrityError)
    @app.exception_handler(DatabaseConstraintError)
    async def database_constraint_exception_handler(request, exc):
        conn = getattr(request.state, "db_conn", None)
        if conn is not None:
            conn.rollback()
        return JSONResponse(
            status_code=400,
            content=fail("DATABASE_CONSTRAINT", str(exc)),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException):
        if exc.status_code == 401:
            code = "UNAUTHORIZED"
        elif exc.status_code == 403:
            code = "FORBIDDEN"
        elif exc.status_code == 503:
            code = "SERVICE_UNAVAILABLE"
        else:
            code = "HTTP_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(code, str(exc.detail)),
        )

    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(admin_inspiration_router)
    app.include_router(admin_viral_analysis_router)
    app.include_router(ai_router)
    app.include_router(accounts_router)
    app.include_router(content_drafts_router)
    app.include_router(inspiration_router)
    app.include_router(viral_analysis_router)
    app.include_router(developer_viral_analysis_router)
    app.include_router(matrix_plans_router)
    app.include_router(products_router)
    app.include_router(runtime_router)
    app.include_router(settings_router)
    app.include_router(tasks_router)
    app.include_router(video_edit_router)
    app.include_router(internal_video_edit_router)
    app.include_router(wallet_router)
    app.include_router(worker_matrix_publish_router)
    app.include_router(xhs_accounts_router)

    @app.get("/api/health")
    def health() -> dict:
        return ok({"status": "ok"})

    return app


app = create_app()
