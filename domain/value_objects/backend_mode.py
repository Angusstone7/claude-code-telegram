"""Backend mode value object.

Defines the available Claude Code backend modes.
"""

from enum import Enum


class BackendMode(str, Enum):
    """Claude Code backend execution mode.

    SDK  — claude-agent-sdk (streaming, HITL, plugins, skills).
    CLI  — claude CLI subprocess (basic fallback).
    """

    SDK = "sdk"
    CLI = "cli"

    @property
    def label_key(self) -> str:
        """Return i18n translation key for this mode's label."""
        return f"settings.backend_{self.value}"

    @property
    def description_key(self) -> str:
        """Return i18n translation key for this mode's description."""
        return f"settings.backend_{self.value}_desc"
