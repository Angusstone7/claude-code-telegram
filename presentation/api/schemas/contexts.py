"""Context management schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ContextResponse(BaseModel):
    """Single project context response."""

    id: str = Field(..., description="Context UUID")
    name: str = Field(..., description="Context display name")
    is_active: bool = Field(False, description="Whether this is the current context")
    message_count: int = Field(0, description="Number of messages in this context")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")


class ContextListResponse(BaseModel):
    """List of contexts response."""

    contexts: list[ContextResponse] = Field(default_factory=list)
    total: int = Field(0, description="Total number of contexts")


class CreateContextRequest(BaseModel):
    """Request to create a new context."""

    name: str = Field(..., min_length=1, max_length=100, description="Context name")
