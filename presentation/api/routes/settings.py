"""Settings API routes.

Provides endpoints for reading and updating application settings.
Settings are stored in-memory via the runtime config service with
environment variable fallbacks for initial values.
"""

import logging
import os

from fastapi import APIRouter, Depends

from presentation.api.security import hybrid_auth
from presentation.api.dependencies import get_runtime_config
from presentation.api.schemas.settings import SettingsResponse, UpdateSettingsRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])

# Default available models
DEFAULT_MODELS = [
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "claude-3-5-haiku-20241022",
    "claude-3-5-sonnet-20241022",
]


def _get_current_settings_dict() -> dict:
    """Read current settings from environment + runtime config defaults."""
    return {
        "yolo_mode": os.getenv("CLAUDE_YOLO_MODE", "false").lower() == "true",
        "step_streaming": os.getenv("CLAUDE_STEP_STREAMING", "true").lower() == "true",
        "backend": os.getenv("CLAUDE_BACKEND", "sdk"),
        "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        "permission_mode": os.getenv("CLAUDE_PERMISSION_MODE", "default"),
        "language": os.getenv("CLAUDE_LANGUAGE", "ru"),
    }


@router.get(
    "",
    response_model=SettingsResponse,
    summary="Get settings",
    description="Return current application settings.",
)
async def get_settings(
    user: dict = Depends(hybrid_auth),
) -> SettingsResponse:
    """Return current settings, merging runtime overrides over env defaults."""
    config = get_runtime_config()

    # Start with env defaults
    defaults = _get_current_settings_dict()

    # Override with runtime config values if present
    for key in defaults:
        runtime_val = await config.get(f"settings.{key}")
        if runtime_val is not None:
            if isinstance(defaults[key], bool):
                defaults[key] = runtime_val if isinstance(runtime_val, bool) else str(runtime_val).lower() == "true"
            else:
                defaults[key] = runtime_val

    return SettingsResponse(
        yolo_mode=defaults["yolo_mode"],
        step_streaming=defaults["step_streaming"],
        backend=defaults["backend"],
        model=defaults["model"],
        available_models=DEFAULT_MODELS,
        permission_mode=defaults["permission_mode"],
        language=defaults["language"],
    )


@router.patch(
    "",
    response_model=SettingsResponse,
    summary="Update settings",
    description="Update application settings. Only provided fields are changed.",
)
async def update_settings(
    request: UpdateSettingsRequest,
    user: dict = Depends(hybrid_auth),
) -> SettingsResponse:
    """Update settings in runtime config and return the new state."""
    config = get_runtime_config()

    # Apply only the fields that were provided
    update_data = request.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        await config.set(f"settings.{key}", value)
        logger.info(
            "Setting updated: %s = %r (user=%s)",
            key,
            value,
            user.get("user_id"),
        )

    # Return the full updated settings
    return await get_settings(user=user)
