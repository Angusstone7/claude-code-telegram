"""Project-related request/response schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ProjectResponse(BaseModel):
    """Single project response."""

    id: Optional[str] = Field(None, description="Project ID")
    name: str = Field(..., description="Project name")
    path: str = Field(..., description="Absolute path to project")
    is_current: bool = Field(False, description="Whether this is the active project")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")


class ProjectListResponse(BaseModel):
    """List of projects response."""

    projects: List[ProjectResponse] = Field(default_factory=list)
    total: int = Field(0, description="Total number of projects")


class CreateProjectRequest(BaseModel):
    """Request to create a new project."""

    name: str = Field(..., min_length=1, max_length=100, description="Project name")
    path: Optional[str] = Field(None, description="Custom path (auto-generated if omitted)")
