from contextlib import asynccontextmanager
import sqlite3

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.accounts import router as accounts_router
from app.api.ai import router as ai_router
from app.api.runtime import router as runtime_router
from app.api.tasks import router as tasks_router
from app.core.config import default_config
from app.core.responses import fail, ok
from app.db.migrations import migrate


def create_app() -> FastAPI:
    config = default_config()
    config.database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    migrate(conn)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            conn.close()

    app = FastAPI(title="Xiaohongshu Publisher Backend", lifespan=lifespan)
    app.state.config = config
    app.state.conn = conn

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request, _exc):
        return JSONResponse(
            status_code=422,
            content=fail("VALIDATION_ERROR", "请求参数格式不正确"),
        )

    @app.exception_handler(sqlite3.IntegrityError)
    async def database_constraint_exception_handler(request, exc):
        conn = getattr(request.app.state, "conn", None)
        if conn is not None:
            conn.rollback()
        return JSONResponse(
            status_code=400,
            content=fail("DATABASE_CONSTRAINT", str(exc)),
        )

    app.include_router(ai_router)
    app.include_router(accounts_router)
    app.include_router(runtime_router)
    app.include_router(tasks_router)

    @app.get("/api/health")
    def health() -> dict:
        return ok({"status": "ok"})

    return app


app = create_app()
