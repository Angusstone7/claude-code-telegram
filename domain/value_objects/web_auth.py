"""Value objects for JWT authentication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class JWTClaims:
    sub: str  # user ID (UUID)
    username: str
    role: str
    exp: datetime
    iat: datetime

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.exp


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str

    def __post_init__(self) -> None:
        if len(self.username) < 3 or len(self.username) > 50:
            raise ValueError("username must be 3-50 characters")
        if len(self.password) < 8:
            raise ValueError("password must be at least 8 characters")


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int  # seconds
    token_type: str = "bearer"
