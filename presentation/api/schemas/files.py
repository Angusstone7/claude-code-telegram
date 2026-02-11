"""File browser schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FileEntry(BaseModel):
    name: str
    path: str
    is_directory: bool
    size: Optional[int] = None
    modified_at: Optional[datetime] = None


class FileBrowserResponse(BaseModel):
    current_path: str
    parent_path: Optional[str] = None
    entries: list[FileEntry]


class MkdirRequest(BaseModel):
    path: str = Field(..., description="Full path of the new directory")
