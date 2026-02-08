"""Claude task request/response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    """Request to submit a Claude task."""

    prompt: str = Field(..., min_length=1, description="Task prompt for Claude")
    working_dir: Optional[str] = Field(None, description="Working directory for the task")
    session_id: Optional[str] = Field(None, description="Session ID to continue")
    model: Optional[str] = Field(None, description="Model override (e.g. claude-sonnet-4-20250514)")
    max_turns: Optional[int] = Field(None, ge=1, le=100, description="Max conversation turns")


class TaskResponse(BaseModel):
    """Response from a Claude task execution."""

    status: str = Field(..., description="Task status: completed, error, cancelled")
    result: Optional[str] = Field(None, description="Task result text")
    session_id: Optional[str] = Field(None, description="Session ID for continuation")
    cost_usd: Optional[float] = Field(None, description="Cost in USD")
    duration_ms: Optional[int] = Field(None, description="Duration in milliseconds")
    num_turns: Optional[int] = Field(None, description="Number of turns used")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
