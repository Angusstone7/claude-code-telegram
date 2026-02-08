"""
Runtime Configuration API routes.

Provides endpoints for reading and updating runtime configuration
without restarting the bot.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from presentation.api.security import require_api_key
from presentation.api.dependencies import get_runtime_config

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/config",
    tags=["configuration"],
    dependencies=[Depends(require_api_key)],
)


class ConfigValue(BaseModel):
    """Request body for setting a config value."""
    value: Any


class ConfigEntry(BaseModel):
    """Response model for a config entry."""
    key: str
    value: Any


@router.get("/", response_model=Dict[str, Any])
async def get_all_config():
    """Get all runtime configuration values."""
    config = get_runtime_config()
    return await config.get_all()


@router.get("/{key}")
async def get_config_value(key: str, default: Any = None):
    """Get a single config value by key."""
    config = get_runtime_config()
    value = await config.get(key, default)
    return {"key": key, "value": value}


@router.put("/{key}")
async def set_config_value(key: str, body: ConfigValue):
    """Set a config value. Creates or updates."""
    config = get_runtime_config()
    await config.set(key, body.value)
    return {"key": key, "value": body.value, "status": "ok"}


@router.delete("/{key}")
async def delete_config_value(key: str):
    """Delete a config value."""
    config = get_runtime_config()
    deleted = await config.delete(key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found")
    return {"key": key, "status": "deleted"}
