"""SSH command schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SSHCommandRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=10000)
    timeout: int = Field(30, ge=1, le=300)


class SSHCommandResponse(BaseModel):
    command: str
    output: str
    exit_code: int
    executed_at: datetime
    duration_ms: int


class SSHHistoryResponse(BaseModel):
    commands: list[SSHCommandResponse]
    total: int
