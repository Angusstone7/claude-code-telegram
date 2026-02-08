"""Common response schemas used across all API endpoints."""

from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: List[Any] = Field(default_factory=list, description="Result items")
    total: int = Field(0, description="Total number of items")
    offset: int = Field(0, description="Current offset")
    limit: int = Field(50, description="Items per page")
