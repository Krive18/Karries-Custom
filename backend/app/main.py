import asyncio
from contextlib import asynccontextmanager, suppress
import logging
import os
from time import perf_counter
from typing import Literal
from uuid import uuid4

import pymysql
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.accounts import router as accounts_router
from app.api.admin import router as admin_router
from app.api.admin_billing import router as admin_billing_router
from app.api.admin_inspiration import router as admin_inspiration_router
from app.api.admin_operations import router as admin_operations_router
from app.api.admin_product_library import router as admin_product_library_router
from app.api.admin_users import router as admin_users_router
from app.api.admin_viral_analysis import router as admin_viral_analysis_router
from app.api.auth import router as auth_router
from app.api.ai import router as ai_router
from app.api.ai_translation import internal_router as internal_ai_translation_router
from app.api.ai_translation import router as ai_translation_router
from app.api.bootstrap_auth import router as bootstrap_auth_router
from app.api.content_drafts import router as content_drafts_router
from app.api.content_collections import router as content_collections_router
from app.api.developer_billing import router as developer_billing_router
from app.api.developer_platform import router as developer_platform_router
from app.api.developer_viral_analysis import router as developer_viral_analysis_router
from app.api.inspiration import router as inspiration_router
from app.api.material_library import router as material_library_router
from app.api.matrix_plans import router as matrix_plans_router
from app.api.notifications import admin_router as admin_notifications_router
from app.api.notifications import customer_router as customer_notifications_router
from app.api.products import router as products_router
from app.api.runtime import router as runtime_router
from app.api.settings import router as settings_router
from app.api.tasks import router as tasks_router
from app.api.user_feedback import customer_router as customer_feedback_router
from app.api.user_feedback import developer_router as developer_feedback_router
from app.api.video_edit import internal_router as internal_video_edit_router
from app.api.video_edit import router as video_edit_router
from app.api.wallet import router as wallet_router
from app.api.worker_matrix_publish import router as worker_matrix_publish_router
from app.api.xhs_accounts import router as xhs_accounts_router
from app.api.viral_analysis import router as viral_analysis_router
from app.core.config import default_config
from app.core.responses import fail, ok
from app.db.connection import ConnectionPool, connect
from app.db.errors import DatabaseConstraintError
from app.db.migrations import migrate
from app.middleware.upload_size_limit import UploadBodyLimitMiddleware
from app.workers.matrix_publish_worker import MatrixPublishWorker, MatrixWorkerApiClient


ApiSurface = Literal["all", "customer", "manager", "developer"]
logger = logging.getLogger("karries.api")


def create_app(surface: ApiSurface = "customer") -> FastAPI:
    config = default_config()
    db_pool = ConnectionPool(
        config.mysql,
        connect_factory=lambda: connect(config.mysql),
    )
    embedded_publish_worker = (
        os.environ.get("XHS_EMBEDDED_PUBLISH_WORKER", "0").strip() == "1"
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        publish_worker_task: asyncio.Task | None = None
        database_retry_task: asyncio.Task | None = None
        try:
            await _migrate_database_once(_app, db_pool)
        except Exception:
            logger.exception("database_startup_unavailable; retrying in background")
            database_retry_task = asyncio.create_task(
                _retry_database_migration(
                    _app,
                    db_pool,
                    config.mysql.reconnect_retry_seconds,
                )
            )

        publish_worker_enabled = embedded_publish_worker
        if publish_worker_enabled:
            if not config.worker_api_token:
                raise ValueError(
                    "WORKER_API_TOKEN is required when embedded publish worker is enabled"
                )
            worker = MatrixPublishWorker(
                MatrixWorkerApiClient(
                    os.environ.get(
                        "BACKEND_API_URL",
                        "http://127.0.0.1:8765",
                    ),
                    config.worker_api_token,
                ),
                headless=os.environ.get("XHS_WORKER_HEADLESS", "1").strip() != "0",
                claim_limit=int(os.environ.get("XHS_WORKER_CLAIM_LIMIT", "3")),
            )
            publish_worker_task = asyncio.create_task(
                worker.run_forever(
                    int(os.environ.get("XHS_WORKER_POLL_SECONDS", "10"))
                )
            )
        _app.state.publish_worker_enabled = publish_worker_enabled
        _app.state.publish_worker_task = publish_worker_task

        try:
            yield
        finally:
            if publish_worker_task is not None:
                publish_worker_task.cancel()
                with suppress(asyncio.CancelledError):
                    await publish_worker_task
            if database_retry_task is not None:
                database_retry_task.cancel()
                with suppress(asyncio.CancelledError):
                    await database_retry_task
            db_pool.close()
            _app.state.conn = None

    app = FastAPI(
        title="Xiaohongshu Publisher Backend",
        lifespan=lifespan,
        docs_url="/docs" if config.expose_api_docs else None,
        redoc_url="/redoc" if config.expose_api_docs else None,
        openapi_url="/openapi.json" if config.expose_api_docs else None,
    )
    app.state.config = config
    app.state.conn = None
    app.state.db_pool = db_pool
    app.state.database_migrated = False
    app.state.api_surface = surface
    app.state.publish_worker_enabled = False
    app.state.publish_worker_task = None
    app.state.connect_db = db_pool.acquire
    app.add_middleware(
        UploadBodyLimitMiddleware,
        max_body_bytes=500 * 1024 * 1024 + 2 * 1024 * 1024,
    )
    if config.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id
        started_at = perf_counter()
        response = await call_next(request)
        elapsed_ms = (perf_counter() - started_at) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response

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
        logger.warning(
            "database_constraint request_id=%s error_type=%s",
            getattr(request.state, "request_id", "-"),
            type(exc).__name__,
            exc_info=True,
        )
        return JSONResponse(
            status_code=400,
            content=fail("DATABASE_CONSTRAINT", "提交的数据不符合约束，请检查后重试"),
        )

    @app.exception_handler(pymysql.err.OperationalError)
    @app.exception_handler(pymysql.err.InterfaceError)
    async def database_connection_exception_handler(request, exc):
        logger.warning(
            "database_connection_failed request_id=%s error_type=%s",
            getattr(request.state, "request_id", "-"),
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=503,
            content=fail("SERVICE_UNAVAILABLE", "数据库暂时不可用，请稍后重试"),
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
    if surface == "all":
        app.include_router(bootstrap_auth_router)

    if surface in {"all", "customer"}:
        app.include_router(ai_router)
        app.include_router(ai_translation_router)
        app.include_router(accounts_router)
        app.include_router(content_drafts_router)
        app.include_router(content_collections_router)
        app.include_router(inspiration_router)
        app.include_router(material_library_router)
        app.include_router(viral_analysis_router)
        app.include_router(matrix_plans_router)
        app.include_router(customer_notifications_router)
        app.include_router(products_router)
        app.include_router(runtime_router)
        app.include_router(tasks_router)
        app.include_router(customer_feedback_router)
        app.include_router(video_edit_router)
        app.include_router(wallet_router)
        app.include_router(xhs_accounts_router)

    if surface in {"all", "manager"}:
        app.include_router(admin_router)
        app.include_router(admin_billing_router)
        app.include_router(admin_inspiration_router)
        app.include_router(admin_operations_router)
        app.include_router(admin_product_library_router)
        app.include_router(admin_notifications_router)
        app.include_router(admin_viral_analysis_router)
        app.include_router(admin_users_router)

    if surface in {"all", "developer"}:
        app.include_router(developer_billing_router)
        app.include_router(developer_platform_router)
        app.include_router(developer_feedback_router)
        app.include_router(developer_viral_analysis_router)
        app.include_router(settings_router)
        app.include_router(internal_ai_translation_router)
        app.include_router(internal_video_edit_router)
        app.include_router(worker_matrix_publish_router)
    elif surface == "customer" and embedded_publish_worker:
        app.include_router(worker_matrix_publish_router)

    @app.get("/api/health")
    def health() -> dict:
        return ok({"status": "ok"})

    @app.get("/api/ready")
    def readiness(request: Request):
        conn = None
        try:
            conn = request.app.state.connect_db()
            with conn.cursor() as cursor:
                cursor.execute("select 1")
            return ok({"status": "ready"})
        except Exception:
            logger.exception(
                "readiness_check_failed request_id=%s",
                getattr(request.state, "request_id", "-"),
            )
            return JSONResponse(
                status_code=503,
                content=fail("SERVICE_UNAVAILABLE", "数据库暂不可用"),
            )
        finally:
            if conn is not None:
                conn.close()

    return app


async def _migrate_database_once(app: FastAPI, pool: ConnectionPool) -> None:
    conn = pool.acquire()
    try:
        await asyncio.to_thread(migrate, conn)
        app.state.database_migrated = True
    finally:
        conn.close()


async def _retry_database_migration(
    app: FastAPI,
    pool: ConnectionPool,
    retry_seconds: float,
) -> None:
    while True:
        if retry_seconds:
            await asyncio.sleep(retry_seconds)
        else:
            await asyncio.sleep(0)
        try:
            await _migrate_database_once(app, pool)
            logger.info("database_migration_recovered")
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("database_migration_retry_failed")


app = create_app()
