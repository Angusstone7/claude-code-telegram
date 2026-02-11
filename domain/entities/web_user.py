"""WebUser entity — пользователь веб-панели администратора."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,50}$")


@dataclass
class WebUser:
    id: str
    username: str
    password_hash: str
    display_name: str
    role: str = "admin"
    telegram_id: Optional[int] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None

    @classmethod
    def create(
        cls,
        username: str,
        password_hash: str,
        display_name: str,
        telegram_id: Optional[int] = None,
        role: str = "admin",
        created_by: Optional[str] = None,
    ) -> WebUser:
        cls._validate_username(username)
        if display_name and len(display_name) > 100:
            raise ValueError("display_name must be 100 characters or less")
        if telegram_id is not None and telegram_id <= 0:
            raise ValueError("telegram_id must be positive")

        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            username=username,
            password_hash=password_hash,
            display_name=display_name,
            role=role,
            telegram_id=telegram_id,
            is_active=True,
            created_at=now,
            updated_at=now,
            created_by=created_by,
        )

    @staticmethod
    def _validate_username(username: str) -> None:
        if not USERNAME_PATTERN.match(username):
            raise ValueError(
                "username must be 3-50 characters, only [a-zA-Z0-9_-]"
            )

    def update_profile(
        self,
        display_name: Optional[str] = None,
        telegram_id: Optional[int] = None,
    ) -> None:
        if display_name is not None:
            if len(display_name) < 1 or len(display_name) > 100:
                raise ValueError("display_name must be 1-100 characters")
            self.display_name = display_name
        if telegram_id is not None:
            if telegram_id <= 0:
                raise ValueError("telegram_id must be positive")
            self.telegram_id = telegram_id
        self.updated_at = datetime.utcnow()

    def change_password(self, new_password_hash: str) -> None:
        self.password_hash = new_password_hash
        self.updated_at = datetime.utcnow()

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = datetime.utcnow()

    def activate(self) -> None:
        self.is_active = True
        self.updated_at = datetime.utcnow()

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
