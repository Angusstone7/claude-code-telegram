"""Settings schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    yolo_mode: bool
    step_streaming: bool
    backend: str  # "sdk" | "cli"
    model: str
    available_models: list[str]
    permission_mode: str  # "default" | "auto" | "never"
    language: str  # "ru" | "en" | "zh"


class UpdateSettingsRequest(BaseModel):
    yolo_mode: Optional[bool] = None
    step_streaming: Optional[bool] = None
    backend: Optional[str] = Field(None, pattern=r"^(sdk|cli)$")
    model: Optional[str] = None
    permission_mode: Optional[str] = Field(None, pattern=r"^(default|auto|never)$")
    language: Optional[str] = Field(None, pattern=r"^(ru|en|zh)$")
