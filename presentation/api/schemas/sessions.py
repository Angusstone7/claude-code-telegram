"""Session-related response schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    """Single session response."""

    session_id: str = Field(..., description="Session ID")
    user_id: int = Field(..., description="User ID")
    message_count: int = Field(0, description="Number of messages in session")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    is_active: bool = Field(False, description="Whether session is currently active")


class SessionListResponse(BaseModel):
    """List of sessions response."""

    sessions: List[SessionResponse] = Field(default_factory=list)
    total: int = Field(0, description="Total number of sessions")
