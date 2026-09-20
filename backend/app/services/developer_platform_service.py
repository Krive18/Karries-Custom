import shutil
from pathlib import Path

from fastapi import Request

from app.repositories.developer_platform_repository import DeveloperPlatformRepository
from app.repositories.setting_repository import SettingRepository
from app.schemas.developer_platform import DeveloperOverview
from app.services.ai_settings_service import get_ai_settings_view


AI_FAILURE_RATE_THRESHOLD = 20.0
AI_P95_LATENCY_THRESHOLD_MS = 30_000


class DeveloperPlatformService:
    def __init__(self, conn, request: Request) -> None:
        self.repository = DeveloperPlatformRepository(conn)
        self.setting_repository = SettingRepository(conn)
        self.request = request

    def overview(self) -> dict:
        result = self.repository.overview_counts()
        pool = self.request.app.state.db_pool.snapshot()
        ai = result["ai"]
        worker_enabled = bool(
            getattr(self.request.app.state, "publish_worker_enabled", False)
        )
        worker_task = getattr(self.request.app.state, "publish_worker_task", None)
        worker_running = bool(worker_task is not None and not worker_task.done())
        storage_path = self._existing_path(
            self.request.app.state.config.data_dir,
            self.request.app.state.config.app_root,
        )
        disk = shutil.disk_usage(storage_path)
        free_percent = round(disk.free * 100 / disk.total, 1) if disk.total else 0.0
        ai_settings = get_ai_settings_view(self.setting_repository)
        if worker_enabled:
            worker_status = "healthy" if worker_running else "down"
            worker_detail = "内置发布 Worker 正常运行" if worker_running else "内置发布 Worker 已停止"
        else:
            worker_status = "unknown"
            worker_detail = "当前使用外部 Worker，尚无心跳数据"
        storage_status = "healthy" if free_percent >= 15 else "degraded"
        result.update(
            {
                "pool": pool,
                "services": [
                    {
                        "key": "database",
                        "label": "MySQL 数据库",
                        "status": "healthy",
                        "detail": f"连接池 {pool['in_use']}/{pool['size']} 使用中，预检已开启",
                    },
                    {
                        "key": "publish_worker",
                        "label": "发布 Worker",
                        "status": worker_status,
                        "detail": worker_detail,
                    },
                    self._provider_health(
                        key="provider_deepseek",
                        label="DeepSeek",
                        setting=ai_settings.copywriting,
                        metrics=ai["providers"].get("deepseek"),
                    ),
                    self._provider_health(
                        key="provider_doubao",
                        label="豆包",
                        setting=ai_settings.vision,
                        metrics=ai["providers"].get("doubao"),
                    ),
                    {
                        "key": "storage",
                        "label": "文件存储",
                        "status": storage_status,
                        "detail": f"磁盘可用空间 {free_percent}%",
                    },
                ],
            }
        )
        return DeveloperOverview.model_validate(result).model_dump()

    @staticmethod
    def _provider_health(*, key: str, label: str, setting, metrics: dict | None) -> dict:
        if not setting.enabled:
            return {"key": key, "label": label, "status": "unknown", "detail": "已停用"}
        if not setting.has_key:
            return {
                "key": key,
                "label": label,
                "status": "unknown",
                "detail": "未配置 API Key",
            }
        if metrics is None or int(metrics["calls"]) == 0:
            return {
                "key": key,
                "label": label,
                "status": "unknown",
                "detail": "已配置，近 24 小时暂无调用",
            }

        failure_rate = float(metrics["failure_rate"])
        p95_latency_ms = int(metrics["p95_latency_ms"])
        status = (
            "degraded"
            if failure_rate >= AI_FAILURE_RATE_THRESHOLD
            or p95_latency_ms >= AI_P95_LATENCY_THRESHOLD_MS
            else "healthy"
        )
        return {
            "key": key,
            "label": label,
            "status": status,
            "detail": (
                f"近 24 小时 {metrics['calls']} 次，失败率 {failure_rate}%，"
                f"P95 {p95_latency_ms} ms"
            ),
        }

    @staticmethod
    def _existing_path(preferred: Path, fallback: Path) -> Path:
        current = preferred
        while not current.exists() and current != current.parent:
            current = current.parent
        return current if current.exists() else fallback
