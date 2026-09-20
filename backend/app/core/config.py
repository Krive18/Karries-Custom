import os
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.secret_cipher import validate_secret_encryption_configuration


class MysqlConfig(BaseModel):
    host: str
    port: int
    database: str
    user: str
    password: str
    charset: str
    connect_timeout: int
    read_timeout: int = 15
    write_timeout: int = 15
    pool_size: int = Field(default=10, ge=1, le=100)
    pool_timeout: float = Field(default=10, gt=0, le=120)
    pool_recycle: int = Field(default=1800, ge=0)
    pool_pre_ping: bool = True
    reconnect_retry_seconds: float = Field(default=5, ge=0, le=300)


class AuthConfig(BaseModel):
    token_secret: str
    access_token_seconds: int


class AppConfig(BaseModel):
    environment: str
    app_root: Path
    data_dir: Path
    log_dir: Path
    runtime_dir: Path
    mysql: MysqlConfig
    auth: AuthConfig
    worker_api_token: str
    cors_allowed_origins: list[str] = Field(default_factory=list)
    expose_api_docs: bool = True


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _cors_origins(environment: str) -> list[str]:
    configured = os.environ.get("XHS_CORS_ALLOWED_ORIGINS")
    if configured is not None:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    if environment not in {"development", "dev", "local", "test"}:
        return []
    return [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5175",
        "http://localhost:5175",
        "http://127.0.0.1:5176",
        "http://localhost:5176",
        "http://127.0.0.1:5177",
        "http://localhost:5177",
    ]


def default_config() -> AppConfig:
    app_root = Path(__file__).resolve().parents[3]
    data_dir = Path(os.environ.get("XHS_PUBLISHER_DATA_DIR", app_root / "data"))
    log_dir = app_root / "logs"
    runtime_dir = app_root / "runtime"
    environment = os.environ.get("XHS_ENV", os.environ.get("APP_ENV", "development")).lower()
    is_non_production = environment in {"development", "dev", "local", "test"}
    token_secret = os.environ.get("XHS_AUTH_TOKEN_SECRET", "dev-insecure-change-me")
    if not is_non_production and token_secret == "dev-insecure-change-me":
        raise ValueError("XHS_AUTH_TOKEN_SECRET must be set outside development and test")
    validate_secret_encryption_configuration()

    return AppConfig(
        environment=environment,
        app_root=app_root,
        data_dir=data_dir,
        log_dir=log_dir,
        runtime_dir=runtime_dir,
        mysql=MysqlConfig(
            host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            database=os.environ.get("MYSQL_DATABASE", "xhs_publisher"),
            user=os.environ.get("MYSQL_USER", "xhs_publisher"),
            password=os.environ.get("MYSQL_PASSWORD", ""),
            charset=os.environ.get("MYSQL_CHARSET", "utf8mb4"),
            connect_timeout=int(os.environ.get("MYSQL_CONNECT_TIMEOUT", "5")),
            read_timeout=int(os.environ.get("MYSQL_READ_TIMEOUT", "15")),
            write_timeout=int(os.environ.get("MYSQL_WRITE_TIMEOUT", "15")),
            pool_size=int(os.environ.get("MYSQL_POOL_SIZE", "10")),
            pool_timeout=float(os.environ.get("MYSQL_POOL_TIMEOUT", "10")),
            pool_recycle=int(os.environ.get("MYSQL_POOL_RECYCLE", "1800")),
            pool_pre_ping=_env_bool("MYSQL_POOL_PRE_PING", True),
            reconnect_retry_seconds=float(
                os.environ.get("MYSQL_RECONNECT_RETRY_SECONDS", "5")
            ),
        ),
        auth=AuthConfig(
            token_secret=token_secret,
            access_token_seconds=int(os.environ.get("XHS_ACCESS_TOKEN_SECONDS", "86400")),
        ),
        worker_api_token=os.environ.get("WORKER_API_TOKEN", ""),
        cors_allowed_origins=_cors_origins(environment),
        expose_api_docs=_env_bool("XHS_EXPOSE_API_DOCS", is_non_production),
    )
