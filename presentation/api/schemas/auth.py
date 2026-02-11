"""Auth request/response schemas per contracts/auth.md."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class UserProfile(BaseModel):
    id: str
    username: str
    display_name: str
    telegram_id: Optional[int] = None
    role: str
    created_at: Optional[datetime] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    telegram_id: Optional[int] = Field(None, gt=0)


class CreateUserRequest(BaseModel):
    username: str = Field(
        ..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    password: str = Field(..., min_length=8)
    display_name: str = Field(..., min_length=1, max_length=100)
    telegram_id: Optional[int] = Field(None, gt=0)


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)


class MessageResponse(BaseModel):
    message: str
