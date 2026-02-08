"""
SQLite-based Runtime Configuration Repository.

Stores key-value configuration in the same SQLite database used by the bot.
Values are stored as JSON strings for type preservation.
"""

import json
import logging
from typing import Any, Dict, Optional

import aiosqlite

from domain.repositories.config_repository import IConfigRepository

logger = logging.getLogger(__name__)


class SQLiteConfigRepository(IConfigRepository):
    """SQLite implementation of runtime configuration store."""

    def __init__(self, db_path: str = "data/bot.db"):
        self.db_path = db_path
        self._initialized = False

    async def _ensure_table(self) -> None:
        """Create the config table if it doesn't exist."""
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS runtime_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
        self._initialized = True

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key."""
        await self._ensure_table()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT value FROM runtime_config WHERE key = ?", (key,)
            )
            row = await cursor.fetchone()
            if row is None:
                return default
            try:
                return json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                return row[0]

    async def set(self, key: str, value: Any) -> None:
        """Set a configuration value (upsert)."""
        await self._ensure_table()
        json_value = json.dumps(value)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO runtime_config (key, value, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(key) DO UPDATE SET
                     value = excluded.value,
                     updated_at = CURRENT_TIMESTAMP""",
                (key, json_value),
            )
            await db.commit()
        logger.debug(f"Config set: {key} = {value}")

    async def delete(self, key: str) -> bool:
        """Delete a configuration key."""
        await self._ensure_table()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM runtime_config WHERE key = ?", (key,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_all(self) -> Dict[str, Any]:
        """Get all configuration key-value pairs."""
        await self._ensure_table()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT key, value FROM runtime_config")
            rows = await cursor.fetchall()
            result = {}
            for key, value in rows:
                try:
                    result[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    result[key] = value
            return result

    async def get_by_prefix(self, prefix: str) -> Dict[str, Any]:
        """Get all config values matching a key prefix."""
        await self._ensure_table()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT key, value FROM runtime_config WHERE key LIKE ?",
                (f"{prefix}%",),
            )
            rows = await cursor.fetchall()
            result = {}
            for key, value in rows:
                try:
                    result[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    result[key] = value
            return result
