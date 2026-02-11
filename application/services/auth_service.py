"""AuthService — JWT authentication, user management, rate limiting."""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from domain.entities.web_user import WebUser
from domain.value_objects.web_auth import Credentials, JWTClaims, TokenPair
from infrastructure.persistence.sqlite_web_user_repository import (
    SQLiteWebUserRepository,
)

logger = logging.getLogger(__name__)

ph = PasswordHasher()

# Defaults (overridden by env)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7"))
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_MINUTES = 15


class AuthService:
    """Application service for JWT authentication and user management."""

    def __init__(self, repository: SQLiteWebUserRepository) -> None:
        self._repo = repository

    async def init(self) -> None:
        """Initialize tables and create initial admin if configured."""
        await self._repo.init_db()
        await self._create_initial_admin()

    async def _create_initial_admin(self) -> None:
        admin_username = os.getenv("ADMIN_INITIAL_USERNAME")
        admin_password = os.getenv("ADMIN_INITIAL_PASSWORD")
        if not admin_username or not admin_password:
            return

        existing = await self._repo.find_by_username(admin_username)
        if existing:
            return

        user = WebUser.create(
            username=admin_username,
            password_hash=ph.hash(admin_password),
            display_name="Administrator",
            role="admin",
        )
        await self._repo.save(user)
        logger.info("Initial admin user '%s' created", admin_username)

    # --- Authentication ---

    async def login(
        self,
        credentials: Credentials,
        ip_address: str = "unknown",
        user_agent: Optional[str] = None,
    ) -> Optional[TokenPair]:
        # Rate limiting check
        if await self._is_rate_limited(credentials.username, ip_address):
            logger.warning(
                "Login rate limited: user='%s' ip='%s'",
                credentials.username,
                ip_address,
            )
            return None

        user = await self._repo.find_by_username(credentials.username)
        if not user or not user.is_active:
            await self._repo.record(credentials.username, ip_address, False)
            return None

        try:
            ph.verify(user.password_hash, credentials.password)
        except VerifyMismatchError:
            await self._repo.record(credentials.username, ip_address, False)
            return None

        # Rehash if needed (argon2 parameter upgrade)
        if ph.check_needs_rehash(user.password_hash):
            user.change_password(ph.hash(credentials.password))
            await self._repo.update(user)

        await self._repo.record(credentials.username, ip_address, True)

        token_pair = self._create_token_pair(user)

        # Store refresh token
        refresh_hash = hashlib.sha256(token_pair.refresh_token.encode()).hexdigest()
        await self._repo.save_refresh_token(
            token_id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
        )

        logger.info("User '%s' logged in successfully", user.username)
        return token_pair

    async def refresh(self, refresh_token: str) -> Optional[TokenPair]:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        token_data = await self._repo.find_by_token_hash(token_hash)

        if not token_data:
            return None

        if token_data["expires_at"] < datetime.utcnow():
            await self._repo.revoke(token_data["id"])
            return None

        user = await self._repo.find_by_id(token_data["user_id"])
        if not user or not user.is_active:
            await self._repo.revoke(token_data["id"])
            return None

        # Revoke old refresh token
        await self._repo.revoke(token_data["id"])

        # Create new pair
        new_pair = self._create_token_pair(user)

        # Store new refresh token
        new_refresh_hash = hashlib.sha256(new_pair.refresh_token.encode()).hexdigest()
        await self._repo.save_refresh_token(
            token_id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=new_refresh_hash,
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )

        return new_pair

    async def logout(self, refresh_token: str) -> bool:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        token_data = await self._repo.find_by_token_hash(token_hash)
        if token_data:
            await self._repo.revoke(token_data["id"])
            return True
        return False

    # --- Token operations ---

    def verify_access_token(self, token: str) -> Optional[JWTClaims]:
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return JWTClaims(
                sub=payload["sub"],
                username=payload["username"],
                role=payload["role"],
                exp=datetime.utcfromtimestamp(payload["exp"]),
                iat=datetime.utcfromtimestamp(payload["iat"]),
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    # --- User management ---

    async def create_user(
        self,
        username: str,
        password: str,
        display_name: str,
        telegram_id: Optional[int] = None,
        created_by: Optional[str] = None,
    ) -> WebUser:
        # Check uniqueness
        if await self._repo.find_by_username(username):
            raise ValueError(f"Username '{username}' already exists")
        if telegram_id and await self._repo.find_by_telegram_id(telegram_id):
            raise ValueError(f"Telegram ID {telegram_id} already linked to another account")

        user = WebUser.create(
            username=username,
            password_hash=ph.hash(password),
            display_name=display_name,
            telegram_id=telegram_id,
            created_by=created_by,
        )
        await self._repo.save(user)
        logger.info("User '%s' created by '%s'", username, created_by)
        return user

    async def update_profile(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        telegram_id: Optional[int] = None,
    ) -> Optional[WebUser]:
        user = await self._repo.find_by_id(user_id)
        if not user:
            return None

        if telegram_id is not None:
            existing = await self._repo.find_by_telegram_id(telegram_id)
            if existing and existing.id != user_id:
                raise ValueError(f"Telegram ID {telegram_id} already linked to another account")

        user.update_profile(display_name=display_name, telegram_id=telegram_id)
        await self._repo.update(user)
        return user

    async def change_password(self, user_id: str, new_password: str) -> bool:
        user = await self._repo.find_by_id(user_id)
        if not user:
            return False

        user.change_password(ph.hash(new_password))
        await self._repo.update(user)
        logger.info("Password changed for user '%s'", user.username)
        return True

    async def get_user(self, user_id: str) -> Optional[WebUser]:
        return await self._repo.find_by_id(user_id)

    async def get_all_users(self) -> list[WebUser]:
        return await self._repo.find_all()

    # --- Rate limiting ---

    async def _is_rate_limited(self, username: str, ip_address: str) -> bool:
        since = datetime.utcnow() - timedelta(minutes=LOGIN_WINDOW_MINUTES)
        count = await self._repo.count_failed_recent(username, ip_address, since)
        return count >= MAX_LOGIN_ATTEMPTS

    async def is_rate_limited(self, username: str, ip_address: str) -> bool:
        return await self._is_rate_limited(username, ip_address)

    # --- Private helpers ---

    def _create_token_pair(self, user: WebUser) -> TokenPair:
        now = datetime.utcnow()
        access_exp = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        access_payload = {
            "sub": user.id,
            "username": user.username,
            "role": user.role,
            "iat": now,
            "exp": access_exp,
        }
        access_token = jwt.encode(access_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        refresh_token = secrets.token_urlsafe(64)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
