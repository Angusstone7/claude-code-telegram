"""Plugin schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class PluginCommand(BaseModel):
    name: str
    description: Optional[str] = None


class PluginResponse(BaseModel):
    name: str
    enabled: bool
    description: Optional[str] = None
    source: Optional[str] = None
    commands: list[PluginCommand]


class PluginListResponse(BaseModel):
    plugins: list[PluginResponse]
    total: int
