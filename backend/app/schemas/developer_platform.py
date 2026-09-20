from typing import Literal

from pydantic import BaseModel, Field


ServiceStatus = Literal["healthy", "degraded", "down", "unknown"]


class DeveloperServiceHealth(BaseModel):
    key: str
    label: str
    status: ServiceStatus
    detail: str


class DeveloperTaskCount(BaseModel):
    total: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0


class DeveloperAiTrendPoint(BaseModel):
    timestamp: int
    calls: int
    failures: int
    success_rate: float
    p95_latency_ms: int


class DeveloperAiHealth(BaseModel):
    calls_24h: int
    failures_24h: int
    failure_rate: float
    p95_latency_ms: int
    trend: list[DeveloperAiTrendPoint]


class DeveloperPoolHealth(BaseModel):
    size: int
    total: int
    idle: int
    in_use: int
    pre_ping: bool
    recycle_seconds: int
    closed: bool


class DeveloperOverview(BaseModel):
    services: list[DeveloperServiceHealth]
    tasks: dict[str, DeveloperTaskCount]
    ai: DeveloperAiHealth
    pool: DeveloperPoolHealth
    open_alerts: int
    page_alerts: int
    active_developers: int
    updated_at: int


class DeveloperActionReason(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class DeveloperAccountCreate(BaseModel):
    login_name: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    nickname: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["platform_admin", "developer_admin"]


class DeveloperAccountPasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    reason: str = Field(min_length=3, max_length=500)


class DeveloperAccountStatusUpdate(BaseModel):
    status: Literal[1, 2]
    reason: str = Field(min_length=3, max_length=500)
