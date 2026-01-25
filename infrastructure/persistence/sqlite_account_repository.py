"""
SQLite Account Repository

Persists user account settings for auth mode switching.
"""

import aiosqlite
import logging
from datetime import datetime
from typing import Optional

from shared.config.settings import settings

logger = logging.getLogger(__name__)


class SQLiteAccountRepository:
    """SQLite implementation for AccountSettings persistence"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.database.url.replace("sqlite:///", "")

    async def initialize(self):
        """Initialize the account_settings table"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS account_settings (
                    user_id INTEGER PRIMARY KEY,
                    auth_mode TEXT NOT NULL DEFAULT 'zai_api',
                    proxy_url TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            await db.commit()
            logger.info("Account settings table initialized")

    async def find_by_user_id(self, user_id: int) -> Optional["AccountSettings"]:
        """Find account settings by user ID"""
        from application.services.account_service import AccountSettings, AuthMode

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM account_settings WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_settings(row)
        return None

    async def save(self, settings: "AccountSettings") -> None:
        """Save account settings"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO account_settings
                (user_id, auth_mode, proxy_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                settings.user_id,
                settings.auth_mode.value,
                settings.proxy_url,
                settings.created_at.isoformat() if settings.created_at else None,
                settings.updated_at.isoformat() if settings.updated_at else None,
            ))
            await db.commit()

    async def delete(self, user_id: int) -> None:
        """Delete account settings for user"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM account_settings WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()

    def _row_to_settings(self, row) -> "AccountSettings":
        """Convert database row to AccountSettings"""
        from application.services.account_service import AccountSettings, AuthMode

        return AccountSettings(
            user_id=row["user_id"],
            auth_mode=AuthMode(row["auth_mode"]),
            proxy_url=row["proxy_url"],
            created_at=(
                datetime.fromisoformat(row["created_at"])
                if row["created_at"] else None
            ),
            updated_at=(
                datetime.fromisoformat(row["updated_at"])
                if row["updated_at"] else None
            ),
        )
