"""SQLite implementation of proxy repository"""

import json
import logging
from datetime import datetime
from typing import Optional
import aiosqlite

from domain.entities.proxy_settings import ProxySettings
from domain.repositories.proxy_repository import ProxyRepository
from domain.value_objects.proxy_config import ProxyConfig, ProxyType
from domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class SQLiteProxyRepository(ProxyRepository):
    """SQLite implementation of proxy settings repository"""

    def __init__(self, db_path: str = "data/bot.db"):
        self.db_path = db_path

    async def _ensure_table(self):
        """Create proxy_settings table if it doesn't exist"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS proxy_settings (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    proxy_type TEXT,
                    host TEXT,
                    port INTEGER,
                    username TEXT,
                    password TEXT,
                    enabled INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            # Create index for faster lookups
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_proxy_user_id
                ON proxy_settings(user_id)
            """)
            await db.commit()

    async def get_global_settings(self) -> Optional[ProxySettings]:
        """Get global proxy settings (user_id IS NULL)"""
        await self._ensure_table()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM proxy_settings WHERE user_id IS NULL LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_entity(row)
        return None

    async def get_user_settings(self, user_id: UserId) -> Optional[ProxySettings]:
        """Get user-specific proxy settings"""
        await self._ensure_table()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM proxy_settings WHERE user_id = ? LIMIT 1",
                (user_id.value,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_entity(row)
        return None

    async def save_global_settings(self, settings: ProxySettings) -> None:
        """Save global proxy settings"""
        await self._ensure_table()

        async with aiosqlite.connect(self.db_path) as db:
            # Delete existing global settings
            await db.execute("DELETE FROM proxy_settings WHERE user_id IS NULL")

            # Insert new settings
            if settings.proxy_config:
                await db.execute("""
                    INSERT INTO proxy_settings
                    (id, user_id, proxy_type, host, port, username, password, enabled, created_at, updated_at)
                    VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    settings.id,
                    settings.proxy_config.proxy_type.value,
                    settings.proxy_config.host,
                    settings.proxy_config.port,
                    settings.proxy_config.username,
                    settings.proxy_config.password,
                    1 if settings.proxy_config.enabled else 0,
                    settings.created_at.isoformat(),
                    settings.updated_at.isoformat()
                ))
            await db.commit()
            logger.info("Global proxy settings saved")

    async def save_user_settings(self, settings: ProxySettings) -> None:
        """Save user-specific proxy settings"""
        await self._ensure_table()

        if not settings.user_id:
            raise ValueError("User ID is required for user-specific settings")

        async with aiosqlite.connect(self.db_path) as db:
            # Delete existing user settings
            await db.execute(
                "DELETE FROM proxy_settings WHERE user_id = ?",
                (settings.user_id.value,)
            )

            # Insert new settings
            if settings.proxy_config:
                await db.execute("""
                    INSERT INTO proxy_settings
                    (id, user_id, proxy_type, host, port, username, password, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    settings.id,
                    settings.user_id.value,
                    settings.proxy_config.proxy_type.value,
                    settings.proxy_config.host,
                    settings.proxy_config.port,
                    settings.proxy_config.username,
                    settings.proxy_config.password,
                    1 if settings.proxy_config.enabled else 0,
                    settings.created_at.isoformat(),
                    settings.updated_at.isoformat()
                ))
            await db.commit()
            logger.info(f"User {settings.user_id.value} proxy settings saved")

    async def delete_global_settings(self) -> None:
        """Delete global proxy settings"""
        await self._ensure_table()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM proxy_settings WHERE user_id IS NULL")
            await db.commit()
            logger.info("Global proxy settings deleted")

    async def delete_user_settings(self, user_id: UserId) -> None:
        """Delete user-specific proxy settings"""
        await self._ensure_table()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM proxy_settings WHERE user_id = ?",
                (user_id.value,)
            )
            await db.commit()
            logger.info(f"User {user_id.value} proxy settings deleted")

    def _row_to_entity(self, row: aiosqlite.Row) -> ProxySettings:
        """Convert database row to ProxySettings entity"""
        # Parse proxy config
        proxy_config = None
        if row["host"] and row["proxy_type"]:
            proxy_config = ProxyConfig(
                proxy_type=ProxyType(row["proxy_type"]),
                host=row["host"],
                port=row["port"],
                username=row["username"],
                password=row["password"],
                enabled=bool(row["enabled"])
            )

        # Parse user_id
        user_id = None
        if row["user_id"] is not None:
            user_id = UserId(row["user_id"])

        return ProxySettings(
            id=row["id"],
            user_id=user_id,
            proxy_config=proxy_config,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"])
        )
