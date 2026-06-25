from pathlib import Path
from pydantic import BaseModel


class AppConfig(BaseModel):
    app_root: Path
    data_dir: Path
    log_dir: Path
    runtime_dir: Path
    database_path: Path


def default_config() -> AppConfig:
    app_root = Path(__file__).resolve().parents[3]
    data_dir = app_root / "data"
    log_dir = app_root / "logs"
    runtime_dir = app_root / "runtime"
    return AppConfig(
        app_root=app_root,
        data_dir=data_dir,
        log_dir=log_dir,
        runtime_dir=runtime_dir,
        database_path=data_dir / "publisher.db",
    )
