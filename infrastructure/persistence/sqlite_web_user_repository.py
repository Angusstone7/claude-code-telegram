"""SQLite implementation of WebUser, RefreshToken, and LoginAttempt repositories."""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from typing import Optional

import aiosqlite

from domain.entities.web_user import WebUser
from domain.repositories.web_user_repository import (
    LoginAttemptRepository,
    RefreshTokenRepository,
    WebUserRepository,
)
from shared.config.settings import settings

logger = logging.getLogger(__name__)


class SQLiteWebUserRepository(WebUserRepository, RefreshTokenRepository, LoginAttemptRepository):
    """Combined SQLite implementation for all web auth repositories."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.database.url.replace("sqlite:///", "")
        os.makedirs(
            os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".",
            exist_ok=True,
        )

    async def init_db(self) -> None:
        """Create tables for web auth: web_users, refresh_tokens, login_attempts."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS web_users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    telegram_id INTEGER UNIQUE,
                    role TEXT NOT NULL DEFAULT 'admin',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_by TEXT
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES web_users(id),
                    token_hash TEXT UNIQUE NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    revoked_at TEXT,
                    user_agent TEXT
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_login_attempts_user_ip ON login_attempts(username, ip_address)"
            )
            await db.commit()
            logger.info("Web auth tables initialized")

    # --- WebUserRepository ---

    async def save(self, user: WebUser) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO web_users
                (id, username, password_hash, display_name, telegram_id,
                 role, is_active, created_at, updated_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    user.username,
                    user.password_hash,
                    user.display_name,
                    user.telegram_id,
                    user.role,
                    1 if user.is_active else 0,
                    user.created_at.isoformat(),
                    user.updated_at.isoformat(),
                    user.created_by,
                ),
            )
            await db.commit()

    async def find_by_id(self, user_id: str) -> Optional[WebUser]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM web_users WHERE id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return self._row_to_web_user(row) if row else None

    async def find_by_username(self, username: str) -> Optional[WebUser]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM web_users WHERE username = ?", (username,)
            ) as cursor:
                row = await cursor.fetchone()
                return self._row_to_web_user(row) if row else None

    async def find_by_telegram_id(self, telegram_id: int) -> Optional[WebUser]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM web_users WHERE telegram_id = ?", (telegram_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return self._row_to_web_user(row) if row else None

    async def find_all(self) -> list[WebUser]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM web_users ORDER BY created_at") as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_web_user(row) for row in rows]

    async def delete(self, user_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM web_users WHERE id = ?", (user_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update(self, user: WebUser) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE web_users SET
                    username = ?, password_hash = ?, display_name = ?,
                    telegram_id = ?, role = ?, is_active = ?,
                    updated_at = ?, created_by = ?
                WHERE id = ?
                """,
                (
                    user.username,
                    user.password_hash,
                    user.display_name,
                    user.telegram_id,
                    user.role,
                    1 if user.is_active else 0,
                    user.updated_at.isoformat(),
                    user.created_by,
                    user.id,
                ),
            )
            await db.commit()

    # --- RefreshTokenRepository ---

    async def save_refresh_token(
        self,
        token_id: str,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
        user_agent: Optional[str] = None,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO refresh_tokens
                (id, user_id, token_hash, expires_at, created_at, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    token_id,
                    user_id,
                    token_hash,
                    expires_at.isoformat(),
                    datetime.utcnow().isoformat(),
                    user_agent,
                ),
            )
            await db.commit()

    # Alias for interface compliance
    async def save_token(
        self,
        token_id: str,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
        user_agent: Optional[str] = None,
    ) -> None:
        await self.save_refresh_token(token_id, user_id, token_hash, expires_at, user_agent)

    async def find_by_token_hash(self, token_hash: str) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM refresh_tokens
                WHERE token_hash = ? AND revoked_at IS NULL
                """,
                (token_hash,),
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "token_hash": row["token_hash"],
                    "expires_at": datetime.fromisoformat(row["expires_at"]),
                    "created_at": datetime.fromisoformat(row["created_at"]),
                    "revoked_at": None,
                    "user_agent": row["user_agent"],
                }

    async def revoke(self, token_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE refresh_tokens SET revoked_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), token_id),
            )
            await db.commit()

    async def revoke_all_for_user(self, user_id: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (datetime.utcnow().isoformat(), user_id),
            )
            await db.commit()
            return cursor.rowcount

    async def cleanup_expired(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM refresh_tokens WHERE expires_at < ?",
                (datetime.utcnow().isoformat(),),
            )
            await db.commit()
            return cursor.rowcount

    # --- LoginAttemptRepository ---

    async def record(self, username: str, ip_address: str, success: bool) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO login_attempts (username, ip_address, success, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, ip_address, 1 if success else 0, datetime.utcnow().isoformat()),
            )
            await db.commit()

    async def count_failed_recent(
        self, username: str, ip_address: str, since: datetime
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT COUNT(*) FROM login_attempts
                WHERE username = ? AND ip_address = ? AND success = 0 AND created_at > ?
                """,
                (username, ip_address, since.isoformat()),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def cleanup_old(self, before: datetime) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM login_attempts WHERE created_at < ?",
                (before.isoformat(),),
            )
            await db.commit()
            return cursor.rowcount

    # --- Helpers ---

    @staticmethod
    def _row_to_web_user(row: aiosqlite.Row) -> WebUser:
        return WebUser(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            display_name=row["display_name"],
            telegram_id=row["telegram_id"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            created_by=row["created_by"],
        )

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
