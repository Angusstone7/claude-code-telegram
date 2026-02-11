"""Docker container management schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ContainerResponse(BaseModel):
    """Single container info."""

    name: str = Field(..., description="Container name")
    status: str = Field(..., description="Container status (running, stopped, restarting, etc.)")
    image: str = Field(..., description="Docker image name:tag")
    ports: list[str] = Field(default_factory=list, description="Published port mappings")
    uptime: Optional[str] = Field(None, description="Human-readable uptime")
    created_at: Optional[datetime] = Field(None, description="Container creation time")


class ContainerListResponse(BaseModel):
    """List of containers."""

    containers: list[ContainerResponse] = Field(default_factory=list)
    total: int = Field(0, description="Total container count")


class ContainerLogsResponse(BaseModel):
    """Container log output."""

    name: str = Field(..., description="Container name")
    logs: str = Field("", description="Log text")
    lines: int = Field(0, description="Number of lines returned")


class ContainerActionResponse(BaseModel):
    """Result of a container action (start/stop/restart)."""

    name: str = Field(..., description="Container name")
    action: str = Field(..., description="Action performed")
    success: bool = Field(True, description="Whether the action succeeded")
    message: str = Field("", description="Descriptive message")
