import os
from pathlib import Path

from pydantic import BaseModel

from app.core.secret_cipher import validate_secret_encryption_configuration


class MysqlConfig(BaseModel):
    host: str
    port: int
    database: str
    user: str
    password: str
    charset: str
    connect_timeout: int


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


def default_config() -> AppConfig:
    app_root = Path(__file__).resolve().parents[3]
    data_dir = Path(os.environ.get("XHS_PUBLISHER_DATA_DIR", app_root / "data"))
    log_dir = app_root / "logs"
    runtime_dir = app_root / "runtime"
    environment = os.environ.get("XHS_ENV", os.environ.get("APP_ENV", "development")).lower()
    token_secret = os.environ.get("XHS_AUTH_TOKEN_SECRET", "dev-insecure-change-me")
    if environment not in {"development", "dev", "local", "test"} and token_secret == "dev-insecure-change-me":
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
        ),
        auth=AuthConfig(
            token_secret=token_secret,
            access_token_seconds=int(os.environ.get("XHS_ACCESS_TOKEN_SECONDS", "86400")),
        ),
        worker_api_token=os.environ.get("WORKER_API_TOKEN", ""),
    )
