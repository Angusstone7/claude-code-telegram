"""Auth routes per contracts/auth.md.

Endpoints:
  POST /auth/login       — public
  POST /auth/refresh     — public (cookie)
  POST /auth/logout      — authenticated (cookie)
  GET  /auth/me          — JWT
  PATCH /auth/me         — JWT
  POST /auth/users       — admin
  GET  /auth/users       — admin
  PATCH /auth/users/{user_id}/password — admin
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from presentation.api.dependencies import get_container
from presentation.api.schemas.auth import (
    CreateUserRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RefreshResponse,
    ResetPasswordRequest,
    UpdateProfileRequest,
    UserProfile,
)
from presentation.api.security import (
    get_current_admin,
    get_current_user,
    get_refresh_token_from_cookie,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Cookie security settings — driven by environment for prod/dev flexibility
_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
_COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")  # "strict", "lax", or "none"
_COOKIE_PATH = "/api/v1/auth"
_COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 days


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Set refresh token as HTTP-only cookie with security attributes."""
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        path=_COOKIE_PATH,
        max_age=_COOKIE_MAX_AGE,
    )


def _get_auth_service():
    return get_container().auth_service()


def _user_to_profile(user) -> UserProfile:
    """Convert WebUser entity to UserProfile response."""
    return UserProfile(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        telegram_id=user.telegram_id,
        role=user.role,
        created_at=user.created_at,
    )


# ── Public endpoints ──────────────────────────────────────────────────────


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response):
    auth = _get_auth_service()

    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")

    # Check rate limiting first
    if await auth.is_rate_limited(body.username, ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )

    from domain.value_objects.web_auth import Credentials

    creds = Credentials(username=body.username, password=body.password)
    token_pair = await auth.login(creds, ip_address=ip, user_agent=user_agent)

    if not token_pair:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    claims = auth.verify_access_token(token_pair.access_token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login succeeded but token verification failed.",
        )
    user = await auth.get_user(claims.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login succeeded but user lookup failed.",
        )

    # Set refresh token as HTTP-only cookie
    _set_refresh_cookie(response, token_pair.refresh_token)

    return LoginResponse(
        access_token=token_pair.access_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
        user=_user_to_profile(user),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    response: Response,
    refresh_token: Optional[str] = Depends(get_refresh_token_from_cookie),
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found.",
        )

    auth = _get_auth_service()
    token_pair = await auth.refresh(refresh_token)

    if not token_pair:
        # Clear invalid cookie
        response.delete_cookie(
            key="refresh_token", path=_COOKIE_PATH
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    _set_refresh_cookie(response, token_pair.refresh_token)

    return RefreshResponse(
        access_token=token_pair.access_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    refresh_token: Optional[str] = Depends(get_refresh_token_from_cookie),
):
    if refresh_token:
        auth = _get_auth_service()
        await auth.logout(refresh_token)

    response.delete_cookie(key="refresh_token", path=_COOKIE_PATH)
    return MessageResponse(message="Logged out successfully")


# ── Authenticated endpoints ───────────────────────────────────────────────


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: dict = Depends(get_current_user)):
    auth = _get_auth_service()
    user = await auth.get_user(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _user_to_profile(user)


@router.patch("/me", response_model=UserProfile)
async def update_me(
    body: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
):
    auth = _get_auth_service()
    try:
        user = await auth.update_profile(
            user_id=current_user["user_id"],
            display_name=body.display_name,
            telegram_id=body.telegram_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _user_to_profile(user)


# ── Admin endpoints ───────────────────────────────────────────────────────


@router.get("/users", response_model=list[UserProfile])
async def list_users(admin: dict = Depends(get_current_admin)):
    auth = _get_auth_service()
    users = await auth.get_all_users()
    return [_user_to_profile(u) for u in users]


@router.post(
    "/users", response_model=UserProfile, status_code=status.HTTP_201_CREATED
)
async def create_user(
    body: CreateUserRequest,
    admin: dict = Depends(get_current_admin),
):
    auth = _get_auth_service()
    try:
        user = await auth.create_user(
            username=body.username,
            password=body.password,
            display_name=body.display_name,
            telegram_id=body.telegram_id,
            created_by=admin["user_id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return _user_to_profile(user)


@router.patch("/users/{user_id}/password", response_model=MessageResponse)
async def reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    admin: dict = Depends(get_current_admin),
):
    auth = _get_auth_service()
    ok = await auth.change_password(user_id, body.new_password)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found.")
    return MessageResponse(message="Password reset successfully")
