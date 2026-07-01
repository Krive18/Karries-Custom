import os
from pathlib import Path

from pydantic import BaseModel


class MysqlConfig(BaseModel):
    host: str
    port: int
    database: str
    user: str
    password: str
    charset: str
    connect_timeout: int


class AppConfig(BaseModel):
    app_root: Path
    data_dir: Path
    log_dir: Path
    runtime_dir: Path
    mysql: MysqlConfig


def default_config() -> AppConfig:
    app_root = Path(__file__).resolve().parents[3]
    data_dir = Path(os.environ.get("XHS_PUBLISHER_DATA_DIR", app_root / "data"))
    log_dir = app_root / "logs"
    runtime_dir = app_root / "runtime"
    return AppConfig(
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
    )
