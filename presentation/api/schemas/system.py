"""System information and health check schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field("ok", description="Overall health status")
    sdk_available: bool = Field(False, description="Claude SDK backend available")
    cli_available: bool = Field(False, description="Claude CLI backend available")
    database_ok: bool = Field(False, description="Database connection healthy")
    uptime_seconds: Optional[float] = Field(None, description="Bot uptime in seconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SystemInfoResponse(BaseModel):
    """System information response."""

    bot_username: Optional[str] = Field(None, description="Telegram bot username")
    bot_id: Optional[int] = Field(None, description="Telegram bot ID")
    python_version: str = Field(..., description="Python version")
    working_dir: str = Field(..., description="Default working directory")
    sdk_available: bool = Field(False)
    cli_available: bool = Field(False)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MetricsResponse(BaseModel):
    """System metrics response (JSON alternative to Prometheus /metrics)."""

    cpu_percent: float = Field(0.0, description="CPU usage percentage")
    memory_percent: float = Field(0.0, description="Memory usage percentage")
    memory_used_gb: float = Field(0.0, description="Memory used in GB")
    disk_percent: float = Field(0.0, description="Disk usage percentage")
    load_avg_1m: float = Field(0.0, description="1-minute load average")
    active_tasks: int = Field(0, description="Currently active Claude tasks")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
