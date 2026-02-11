"""Repository interface for WebUser entity."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from domain.entities.web_user import WebUser


class WebUserRepository(ABC):

    @abstractmethod
    async def save(self, user: WebUser) -> None:
        ...

    @abstractmethod
    async def find_by_id(self, user_id: str) -> Optional[WebUser]:
        ...

    @abstractmethod
    async def find_by_username(self, username: str) -> Optional[WebUser]:
        ...

    @abstractmethod
    async def find_by_telegram_id(self, telegram_id: int) -> Optional[WebUser]:
        ...

    @abstractmethod
    async def find_all(self) -> list[WebUser]:
        ...

    @abstractmethod
    async def delete(self, user_id: str) -> bool:
        ...

    @abstractmethod
    async def update(self, user: WebUser) -> None:
        ...


class RefreshTokenRepository(ABC):

    @abstractmethod
    async def save(
        self,
        token_id: str,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
        user_agent: Optional[str] = None,
    ) -> None:
        ...

    @abstractmethod
    async def find_by_token_hash(self, token_hash: str) -> Optional[dict]:
        ...

    @abstractmethod
    async def revoke(self, token_id: str) -> None:
        ...

    @abstractmethod
    async def revoke_all_for_user(self, user_id: str) -> int:
        ...

    @abstractmethod
    async def cleanup_expired(self) -> int:
        ...


class LoginAttemptRepository(ABC):

    @abstractmethod
    async def record(
        self, username: str, ip_address: str, success: bool
    ) -> None:
        ...

    @abstractmethod
    async def count_failed_recent(
        self, username: str, ip_address: str, since: datetime
    ) -> int:
        ...

    @abstractmethod
    async def cleanup_old(self, before: datetime) -> int:
        ...
