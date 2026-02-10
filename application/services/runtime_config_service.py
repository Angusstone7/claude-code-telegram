"""
Runtime Configuration Service.

Provides typed, cached access to runtime configuration values.
Supports hot-reload: changes take effect without restart.

Usage:
    config = container.runtime_config()
    log_level = await config.get_log_level()
    await config.set_log_level("DEBUG")

    # Feature flags
    is_enabled = await config.is_feature_enabled("streaming")
    await config.set_feature_enabled("streaming", True)

    # Monitoring thresholds
    cpu = await config.get_float("monitoring.cpu_threshold", 80.0)
"""

import logging
from typing import Any, Dict, List, Optional

from domain.repositories.config_repository import IConfigRepository

logger = logging.getLogger(__name__)


class RuntimeConfigService:
    """Service for managing runtime configuration with typed accessors."""

    def __init__(self, repository: IConfigRepository):
        self._repo = repository
        self._cache: Dict[str, Any] = {}
        self._cache_loaded = False

    async def _ensure_cache(self) -> None:
        """Load all config into cache on first access."""
        if not self._cache_loaded:
            self._cache = await self._repo.get_all()
            self._cache_loaded = True

    def invalidate_cache(self) -> None:
        """Force cache reload on next access."""
        self._cache_loaded = False
        self._cache.clear()

    # === Generic Accessors ===

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a config value (cached)."""
        await self._ensure_cache()
        return self._cache.get(key, default)

    async def get_str(self, key: str, default: str = "") -> str:
        """Get string config value."""
        val = await self.get(key, default)
        return str(val) if val is not None else default

    async def get_int(self, key: str, default: int = 0) -> int:
        """Get integer config value."""
        val = await self.get(key, default)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    async def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float config value."""
        val = await self.get(key, default)
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean config value."""
        val = await self.get(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes", "on")
        return bool(val)

    async def set(self, key: str, value: Any) -> None:
        """Set a config value (updates cache and DB)."""
        await self._repo.set(key, value)
        self._cache[key] = value
        logger.info(f"Runtime config updated: {key} = {value}")

    async def delete(self, key: str) -> bool:
        """Delete a config key."""
        result = await self._repo.delete(key)
        self._cache.pop(key, None)
        return result

    async def get_all(self) -> Dict[str, Any]:
        """Get all config values."""
        await self._ensure_cache()
        return dict(self._cache)

    # === Typed Accessors for Common Settings ===

    async def get_log_level(self) -> str:
        """Get runtime log level."""
        return await self.get_str("system.log_level", "INFO")

    async def set_log_level(self, level: str) -> None:
        """Set runtime log level (also applies to root logger)."""
        level = level.upper()
        await self.set("system.log_level", level)
        logging.getLogger().setLevel(getattr(logging, level, logging.INFO))

    async def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature flag is enabled."""
        return await self.get_bool(f"feature.{feature}", default=True)

    async def set_feature_enabled(self, feature: str, enabled: bool) -> None:
        """Set a feature flag."""
        await self.set(f"feature.{feature}", enabled)

    async def get_monitoring_thresholds(self) -> Dict[str, float]:
        """Get monitoring alert thresholds."""
        return {
            "cpu": await self.get_float("monitoring.cpu_threshold", 80.0),
            "memory": await self.get_float("monitoring.memory_threshold", 85.0),
            "disk": await self.get_float("monitoring.disk_threshold", 90.0),
        }

    async def set_monitoring_threshold(self, metric: str, value: float) -> None:
        """Set a monitoring threshold."""
        await self.set(f"monitoring.{metric}_threshold", value)

    # === Backend Mode (SDK / CLI) ===

    async def get_user_backend(self, user_id: int) -> "BackendMode":
        """Get user's preferred Claude Code backend mode."""
        from domain.value_objects.backend_mode import BackendMode

        raw = await self.get_str(f"user.{user_id}.backend", BackendMode.SDK.value)
        try:
            return BackendMode(raw)
        except ValueError:
            return BackendMode.SDK

    async def set_user_backend(self, user_id: int, mode: "BackendMode") -> None:
        """Set user's preferred backend mode.

        Args:
            user_id: Telegram user ID.
            mode: BackendMode enum value.
        """
        from domain.value_objects.backend_mode import BackendMode

        if not isinstance(mode, BackendMode):
            mode = BackendMode(mode)  # raises ValueError if invalid
        await self.set(f"user.{user_id}.backend", mode.value)
        logger.info(f"User {user_id} switched backend to: {mode.value}")

    # === Telegram API Server ===

    _TG_API_KEY = "telegram.api_server_url"

    async def get_telegram_api_url(self) -> Optional[str]:
        """Get custom Telegram API server URL.

        Returns:
            URL string if configured, None for direct connection.
        """
        url = await self.get_str(self._TG_API_KEY, "")
        return url if url else None

    async def set_telegram_api_url(self, url: str) -> None:
        """Set custom Telegram API server URL.

        Validates the URL via TelegramApiConfig before saving.

        Args:
            url: Full URL, e.g. http://85.192.63.133:8089/telegram

        Raises:
            ValueError: If URL is invalid.
        """
        from domain.value_objects.telegram_api_config import TelegramApiConfig

        config = TelegramApiConfig.from_url(url)  # validates
        await self.set(self._TG_API_KEY, config.server_url)
        logger.info(f"Telegram API server set to: {config.server_url}")

    async def clear_telegram_api_url(self) -> None:
        """Remove custom Telegram API server (revert to direct connection)."""
        await self.delete(self._TG_API_KEY)
        logger.info("Telegram API server cleared (using direct connection)")
