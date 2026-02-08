"""
Runtime Configuration Repository Interface

Provides a key-value store for configuration that can be changed
at runtime without restarting the application.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class IConfigRepository(ABC):
    """Interface for runtime configuration persistence."""

    @abstractmethod
    async def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a configuration key. Returns True if existed."""
        pass

    @abstractmethod
    async def get_all(self) -> Dict[str, Any]:
        """Get all configuration key-value pairs."""
        pass

    @abstractmethod
    async def get_by_prefix(self, prefix: str) -> Dict[str, Any]:
        """Get all config values matching a key prefix."""
        pass
