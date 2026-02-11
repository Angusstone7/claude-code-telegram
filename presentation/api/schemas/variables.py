"""Context variable schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VariableResponse(BaseModel):
    """Single variable response."""

    id: int = Field(..., description="Variable auto-increment ID")
    name: str = Field(..., description="Variable name")
    value: str = Field(..., description="Variable value")
    description: Optional[str] = Field(None, description="Description for AI context")
    scope: str = Field("local", description="Variable scope: 'local' or 'global'")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class VariableListResponse(BaseModel):
    """List of variables response."""

    variables: list[VariableResponse] = Field(default_factory=list)
    total: int = Field(0, description="Total number of variables")


class CreateVariableRequest(BaseModel):
    """Request to create a new variable."""

    name: str = Field(..., min_length=1, max_length=100, description="Variable name")
    value: str = Field(..., description="Variable value")
    description: Optional[str] = Field(None, max_length=500, description="Description for AI")
    scope: str = Field("local", pattern=r"^(local|global)$", description="Scope: 'local' or 'global'")


class UpdateVariableRequest(BaseModel):
    """Request to update an existing variable."""

    value: Optional[str] = Field(None, description="New variable value")
    description: Optional[str] = Field(None, max_length=500, description="New description")
