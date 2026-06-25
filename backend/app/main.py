from fastapi import FastAPI

from app.core.responses import ok


def create_app() -> FastAPI:
    app = FastAPI(title="Xiaohongshu Publisher Backend")

    @app.get("/api/health")
    def health() -> dict:
        return ok({"status": "ok"})

    return app


app = create_app()
