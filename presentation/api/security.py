"""Hybrid authentication: JWT Bearer + API Key for REST API."""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
BEARER_SCHEME = HTTPBearer(auto_error=False)


def get_api_key() -> Optional[str]:
    """Get configured API key from environment."""
    return os.getenv("API_KEY")


def _get_auth_service():
    """Lazy import to avoid circular dependencies."""
    from presentation.api.dependencies import get_container

    container = get_container()
    return container.auth_service()


async def verify_api_key(api_key: Optional[str] = Security(API_KEY_HEADER)) -> str:
    """Verify API key from X-API-Key header. Dev mode if API_KEY not set."""
    expected_key = get_api_key()

    if not expected_key:
        return "dev-mode"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
        )

    if api_key != expected_key:
        logger.warning("Invalid API key attempt: %s...", api_key[:8])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return api_key


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(BEARER_SCHEME),
) -> dict:
    """Extract and verify JWT Bearer token. Returns user claims dict."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = _get_auth_service()
    claims = auth_service.verify_access_token(credentials.credentials)

    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": claims.sub,
        "username": claims.username,
        "role": claims.role,
    }


async def get_current_admin(
    user: dict = Depends(get_current_user),
) -> dict:
    """Require admin role."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return user


async def hybrid_auth(
    api_key: Optional[str] = Security(API_KEY_HEADER),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(BEARER_SCHEME),
) -> dict:
    """Accept either JWT Bearer or API Key. Returns user context dict."""
    # Try JWT first
    if credentials:
        auth_service = _get_auth_service()
        claims = auth_service.verify_access_token(credentials.credentials)
        if claims:
            return {
                "user_id": claims.sub,
                "username": claims.username,
                "role": claims.role,
                "auth_method": "jwt",
            }

    # Try API Key
    expected_key = get_api_key()
    if expected_key and api_key and api_key == expected_key:
        return {
            "user_id": "api-key-user",
            "username": "api",
            "role": "admin",
            "auth_method": "api_key",
        }

    # Dev mode fallback
    if not expected_key:
        return {
            "user_id": "dev-mode",
            "username": "dev",
            "role": "admin",
            "auth_method": "none",
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid JWT Bearer token or API Key required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_refresh_token_from_cookie(
    refresh_token: Optional[str] = Cookie(None),
) -> Optional[str]:
    """Extract refresh token from HTTP-only cookie."""
    return refresh_token
