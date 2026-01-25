"""
Account Service

Manages switching between z.ai API and Claude Account authorization modes.

Two authorization modes:
1. zai_api - Uses ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN for z.ai API
2. claude_account - Uses OAuth credentials from .credentials.json with proxy
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# Proxy for accessing claude.ai from Russia
CLAUDE_PROXY = "http://proxyuser:!QAZ1qaz7@148.253.208.124:3128"

# Path where credentials file should be stored
CREDENTIALS_PATH = "/root/.claude/.credentials.json"


class AuthMode(str, Enum):
    """Authorization mode"""
    ZAI_API = "zai_api"
    CLAUDE_ACCOUNT = "claude_account"


@dataclass
class AccountSettings:
    """User account settings"""
    user_id: int
    auth_mode: AuthMode = AuthMode.ZAI_API
    proxy_url: str = CLAUDE_PROXY
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CredentialsInfo:
    """Info about Claude credentials"""
    exists: bool
    subscription_type: Optional[str] = None
    rate_limit_tier: Optional[str] = None
    expires_at: Optional[datetime] = None
    scopes: list[str] = None

    @classmethod
    def from_file(cls, path: str = CREDENTIALS_PATH) -> "CredentialsInfo":
        """Read credentials info from file"""
        if not os.path.exists(path):
            return cls(exists=False)

        try:
            with open(path, "r") as f:
                data = json.load(f)

            oauth = data.get("claudeAiOauth", {})
            expires_at = None
            if oauth.get("expiresAt"):
                # expiresAt is in milliseconds
                expires_at = datetime.fromtimestamp(oauth["expiresAt"] / 1000)

            return cls(
                exists=True,
                subscription_type=oauth.get("subscriptionType"),
                rate_limit_tier=oauth.get("rateLimitTier"),
                expires_at=expires_at,
                scopes=oauth.get("scopes", []),
            )
        except Exception as e:
            logger.error(f"Error reading credentials: {e}")
            return cls(exists=False)


class AccountService:
    """
    Service for managing user account settings and authorization modes.

    Handles:
    - Switching between z.ai API and Claude Account modes
    - Saving uploaded credentials files
    - Building environment variables for each mode
    """

    def __init__(self, repository: "SQLiteAccountRepository"):
        self.repository = repository
        self._upload_sessions: dict[int, asyncio.Event] = {}

    async def get_settings(self, user_id: int) -> AccountSettings:
        """Get account settings for user, creating default if not exists"""
        settings = await self.repository.find_by_user_id(user_id)
        if not settings:
            settings = AccountSettings(
                user_id=user_id,
                auth_mode=AuthMode.ZAI_API,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            await self.repository.save(settings)
        return settings

    async def get_auth_mode(self, user_id: int) -> AuthMode:
        """Get current auth mode for user"""
        settings = await self.get_settings(user_id)
        return settings.auth_mode

    async def set_auth_mode(self, user_id: int, mode: AuthMode) -> AccountSettings:
        """Set auth mode for user"""
        settings = await self.get_settings(user_id)
        settings.auth_mode = mode
        settings.updated_at = datetime.now()
        await self.repository.save(settings)
        logger.info(f"[{user_id}] Auth mode set to: {mode.value}")
        return settings

    def get_credentials_info(self) -> CredentialsInfo:
        """Get info about current Claude credentials"""
        return CredentialsInfo.from_file(CREDENTIALS_PATH)

    def has_valid_credentials(self) -> bool:
        """Check if valid credentials exist"""
        info = self.get_credentials_info()
        if not info.exists:
            return False

        # Check if expired
        if info.expires_at and info.expires_at < datetime.now():
            return False

        return True

    def save_credentials(self, credentials_json: str) -> tuple[bool, str]:
        """
        Save credentials JSON to file.

        Args:
            credentials_json: JSON string with credentials

        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate JSON
            data = json.loads(credentials_json)

            # Check required fields
            if "claudeAiOauth" not in data:
                return False, "Invalid credentials format: missing claudeAiOauth"

            oauth = data["claudeAiOauth"]
            required_fields = ["accessToken", "refreshToken"]
            for field in required_fields:
                if field not in oauth:
                    return False, f"Invalid credentials format: missing {field}"

            # Ensure directory exists
            os.makedirs(os.path.dirname(CREDENTIALS_PATH), exist_ok=True)

            # Write credentials
            with open(CREDENTIALS_PATH, "w") as f:
                json.dump(data, f, indent=2)

            # Verify it was saved
            info = CredentialsInfo.from_file(CREDENTIALS_PATH)
            if not info.exists:
                return False, "Failed to save credentials"

            subscription = info.subscription_type or "unknown"
            tier = info.rate_limit_tier or "default"

            logger.info(f"Credentials saved: subscription={subscription}, tier={tier}")
            return True, f"Credentials saved (subscription: {subscription})"

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
            return False, f"Error: {e}"

    def get_env_for_mode(self, mode: AuthMode) -> dict[str, str]:
        """
        Build environment variables for the specified auth mode.

        Args:
            mode: Authorization mode

        Returns:
            Dict of environment variables to set
        """
        env = {}

        if mode == AuthMode.ZAI_API:
            # z.ai API mode - use env vars from settings
            base_url = os.environ.get("ANTHROPIC_BASE_URL")
            auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")

            if base_url:
                env["ANTHROPIC_BASE_URL"] = base_url
            if auth_token:
                env["ANTHROPIC_API_KEY"] = auth_token

            logger.debug(f"z.ai mode env: base_url={base_url is not None}")

        elif mode == AuthMode.CLAUDE_ACCOUNT:
            # Claude Account mode - use credentials file with proxy
            # IMPORTANT: Do NOT set ANTHROPIC_API_KEY or ANTHROPIC_BASE_URL
            # Claude CLI will use the credentials file

            # Set proxy for accessing claude.ai
            env["HTTP_PROXY"] = CLAUDE_PROXY
            env["HTTPS_PROXY"] = CLAUDE_PROXY
            env["http_proxy"] = CLAUDE_PROXY
            env["https_proxy"] = CLAUDE_PROXY

            # Ensure API key is NOT set (remove from env if present)
            # The caller should use env.update() and then pop these keys
            env["_REMOVE_ANTHROPIC_API_KEY"] = "1"
            env["_REMOVE_ANTHROPIC_BASE_URL"] = "1"

            logger.debug(f"Claude Account mode env: proxy={CLAUDE_PROXY[:30]}...")

        return env

    def apply_env_for_mode(self, mode: AuthMode, base_env: dict = None) -> dict[str, str]:
        """
        Apply environment variables for the specified auth mode.

        This creates a copy of the environment and modifies it appropriately.

        Args:
            mode: Authorization mode
            base_env: Base environment (defaults to os.environ)

        Returns:
            New environment dict ready for subprocess/SDK
        """
        if base_env is None:
            base_env = dict(os.environ)
        else:
            base_env = dict(base_env)

        mode_env = self.get_env_for_mode(mode)

        # Handle removal markers
        if mode_env.pop("_REMOVE_ANTHROPIC_API_KEY", None):
            base_env.pop("ANTHROPIC_API_KEY", None)
            base_env.pop("ANTHROPIC_AUTH_TOKEN", None)

        if mode_env.pop("_REMOVE_ANTHROPIC_BASE_URL", None):
            base_env.pop("ANTHROPIC_BASE_URL", None)

        # Apply remaining env vars
        base_env.update(mode_env)

        return base_env


# Import repository here to avoid circular imports
from infrastructure.persistence.sqlite_account_repository import SQLiteAccountRepository
