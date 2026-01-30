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

# Local addresses that should bypass proxy
NO_PROXY_VALUE = "localhost,127.0.0.1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12,host.docker.internal,.local"

# Path where credentials file should be stored
CREDENTIALS_PATH = "/root/.claude/.credentials.json"


class AuthMode(str, Enum):
    """Authorization mode"""
    ZAI_API = "zai_api"
    CLAUDE_ACCOUNT = "claude_account"
    LOCAL_MODEL = "local_model"


class ClaudeModel(str, Enum):
    """Available Claude models"""
    OPUS = "claude-opus-4-5"
    SONNET = "claude-sonnet-4-5"
    HAIKU = "claude-haiku-4"

    @classmethod
    def get_display_name(cls, model: str) -> str:
        """Get user-friendly display name for model"""
        mapping = {
            cls.OPUS: "Opus 4.5",
            cls.SONNET: "Sonnet 4.5",
            cls.HAIKU: "Haiku 4",
        }
        return mapping.get(model, model)

    @classmethod
    def get_description(cls, model: str) -> str:
        """Get model description"""
        descriptions = {
            cls.OPUS: "Самая мощная модель, лучшая для сложных задач",
            cls.SONNET: "Баланс между скоростью и качеством (рекомендуется)",
            cls.HAIKU: "Быстрая модель для простых задач",
        }
        return descriptions.get(model, "")


@dataclass
class LocalModelConfig:
    """Configuration for a local model endpoint (LMStudio, Ollama, etc.)"""
    name: str           # User-defined name (e.g., "My LMStudio")
    base_url: str       # e.g., "http://localhost:1234" (trailing /v1 is auto-stripped)
    model_name: str     # e.g., "llama-3.2-8b"
    api_key: Optional[str] = None  # Optional API key (some local servers need it)

    def __post_init__(self):
        """Normalize base_url - remove trailing /v1 to avoid double /v1/v1 path."""
        # SDK adds /v1/messages, so base_url should NOT include /v1
        self.base_url = self.base_url.rstrip("/")
        if self.base_url.endswith("/v1"):
            self.base_url = self.base_url[:-3]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "base_url": self.base_url,
            "model_name": self.model_name,
            "api_key": self.api_key,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LocalModelConfig":
        return cls(
            name=data.get("name", "Local Model"),
            base_url=data["base_url"],
            model_name=data["model_name"],
            api_key=data.get("api_key"),
        )


@dataclass
class AccountSettings:
    """User account settings"""
    user_id: int
    auth_mode: AuthMode = AuthMode.ZAI_API
    model: Optional[str] = None  # Preferred model (e.g., "claude-sonnet-4-5" or "glm-4.7")
    proxy_url: Optional[str] = None  # Managed via ProxyService
    local_model_config: Optional[LocalModelConfig] = None  # Config for LOCAL_MODEL mode
    yolo_mode: bool = False  # Auto-approve all operations
    zai_api_key: Optional[str] = None  # User-provided z.ai API key
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

    def __init__(self, repository: "SQLiteAccountRepository", proxy_service: "ProxyService" = None):
        self.repository = repository
        self.proxy_service = proxy_service
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

    async def set_auth_mode(self, user_id: int, mode: AuthMode) -> tuple[bool, AccountSettings, Optional[str]]:
        """
        Set auth mode for user.

        Args:
            user_id: User ID
            mode: Authorization mode to switch to

        Returns:
            Tuple of (success, settings, error_message)
            - success: Whether the mode was changed successfully
            - settings: Updated account settings
            - error_message: Error message if failed, None if successful
        """
        # Validate Claude Account mode has valid credentials
        if mode == AuthMode.CLAUDE_ACCOUNT:
            if not self.has_valid_credentials():
                logger.warning(f"[{user_id}] Attempted to switch to Claude Account without valid credentials")
                settings = await self.get_settings(user_id)
                return False, settings, "❌ Нет файла с учётными данными или токен истёк. Загрузите credentials.json или войдите через OAuth."

        settings = await self.get_settings(user_id)
        settings.auth_mode = mode
        settings.updated_at = datetime.now()
        await self.repository.save(settings)
        logger.info(f"[{user_id}] Auth mode set to: {mode.value}")
        return True, settings, None

    async def get_model(self, user_id: int) -> Optional[str]:
        """
        Get preferred model for user, respecting auth mode.

        Each auth mode only accepts compatible models:
        - Claude Account: only official Claude models (opus, sonnet, haiku)
        - z.ai API: only z.ai models (glm-4.7, etc.) or env default
        - Local Model: use the configured local model

        Returns:
            - Model string if compatible with current mode
            - None to use provider's default (SDK default or ANTHROPIC_MODEL env)
        """
        settings = await self.get_settings(user_id)

        if settings.auth_mode == AuthMode.CLAUDE_ACCOUNT:
            # For Claude Account, only return model if it's an official Claude model
            # This prevents z.ai models like glm-4.7 from being sent to official API
            if settings.model and self._is_official_claude_model(settings.model):
                # Normalize legacy "ClaudeModel.OPUS" → "claude-opus-4-5"
                return self._normalize_model(settings.model)
            # No model or non-Claude model: SDK will use its default
            return None

        elif settings.auth_mode == AuthMode.LOCAL_MODEL:
            # For local model, use the configured model from local_model_config
            if settings.local_model_config:
                return settings.local_model_config.model_name
            return None

        # z.ai API mode
        if settings.model and self._is_official_claude_model(settings.model):
            # User selected Claude model but using z.ai → use env default (ANTHROPIC_MODEL)
            logger.debug(f"[{user_id}] Claude model selected but using z.ai API, falling back to env default")
            return None

        # z.ai API with z.ai-compatible model (glm-4.7, etc.)
        return settings.model

    def _is_official_claude_model(self, model: str) -> bool:
        """Check if model is an official Claude model."""
        official_models = {
            # Actual model IDs
            ClaudeModel.OPUS.value,
            ClaudeModel.SONNET.value,
            ClaudeModel.HAIKU.value,
            # Legacy: str(Enum) returns "ClaudeModel.OPUS" not value
            "ClaudeModel.OPUS",
            "ClaudeModel.SONNET",
            "ClaudeModel.HAIKU",
        }
        return model in official_models

    def _normalize_model(self, model: str) -> str:
        """Convert legacy model strings to actual model IDs."""
        legacy_mapping = {
            "ClaudeModel.OPUS": ClaudeModel.OPUS.value,
            "ClaudeModel.SONNET": ClaudeModel.SONNET.value,
            "ClaudeModel.HAIKU": ClaudeModel.HAIKU.value,
        }
        return legacy_mapping.get(model, model)

    async def set_model(self, user_id: int, model: Optional[str]) -> AccountSettings:
        """
        Set preferred model for user.

        Args:
            user_id: User ID
            model: Model ID (e.g., "claude-sonnet-4-5") or None for default

        Returns:
            Updated settings
        """
        settings = await self.get_settings(user_id)
        settings.model = model
        settings.updated_at = datetime.now()
        await self.repository.save(settings)
        logger.info(f"[{user_id}] Model set to: {model or 'default'}")
        return settings

    async def get_available_models(self, user_id: int) -> list[dict]:
        """
        Get available models based on current auth mode.

        Returns:
            List of model dicts with: id, name, desc, is_selected
        """
        settings = await self.get_settings(user_id)

        if settings.auth_mode == AuthMode.CLAUDE_ACCOUNT:
            models = [
                {"id": ClaudeModel.OPUS.value, "name": "Opus 4.5", "desc": "Самая мощная модель"},
                {"id": ClaudeModel.SONNET.value, "name": "Sonnet 4.5", "desc": "Баланс скорости и качества (рекомендуется)"},
                {"id": ClaudeModel.HAIKU.value, "name": "Haiku 4", "desc": "Быстрая модель"},
            ]
            for m in models:
                m["is_selected"] = settings.model == m["id"]
            return models

        elif settings.auth_mode == AuthMode.ZAI_API:
            models = self._get_zai_models_from_env()
            for m in models:
                m["is_selected"] = settings.model == m["id"]
            return models

        elif settings.auth_mode == AuthMode.LOCAL_MODEL:
            if settings.local_model_config:
                return [{
                    "id": settings.local_model_config.model_name,
                    "name": settings.local_model_config.name,
                    "desc": settings.local_model_config.base_url,
                    "is_selected": True,
                }]
            return []

        return []

    def _get_zai_models_from_env(self) -> list[dict]:
        """Get z.ai models from environment variables or use defaults."""
        models = []

        # Check for env-configured models
        haiku = os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL")
        sonnet = os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
        opus = os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL")
        default = os.environ.get("ANTHROPIC_MODEL")

        if haiku:
            models.append({"id": haiku, "name": self._format_model_name(haiku), "desc": "Быстрая модель"})
        if sonnet and sonnet != haiku:
            models.append({"id": sonnet, "name": self._format_model_name(sonnet), "desc": "Сбалансированная модель"})
        if opus and opus not in (haiku, sonnet):
            models.append({"id": opus, "name": self._format_model_name(opus), "desc": "Мощная модель"})
        if default and default not in (haiku, sonnet, opus):
            models.append({"id": default, "name": self._format_model_name(default), "desc": "Модель по умолчанию"})

        # Fallback to hardcoded z.ai defaults
        if not models:
            models = [
                {"id": "glm-4.5-air", "name": "GLM 4.5 Air", "desc": "Быстрая модель"},
                {"id": "glm-4.7", "name": "GLM 4.7", "desc": "Мощная модель"},
            ]

        return models

    def _format_model_name(self, model_id: str) -> str:
        """Format model ID to display name (glm-4.7 → GLM 4.7)."""
        return model_id.replace("-", " ").replace("_", " ").title()

    async def set_local_model_config(
        self, user_id: int, config: LocalModelConfig
    ) -> AccountSettings:
        """
        Set local model configuration and switch to LOCAL_MODEL mode.

        Args:
            user_id: User ID
            config: Local model configuration

        Returns:
            Updated settings
        """
        settings = await self.get_settings(user_id)
        settings.auth_mode = AuthMode.LOCAL_MODEL
        settings.local_model_config = config
        settings.model = config.model_name
        settings.updated_at = datetime.now()
        await self.repository.save(settings)
        logger.info(f"[{user_id}] Set local model: {config.name} ({config.base_url})")
        return settings

    async def set_zai_api_key(
        self, user_id: int, api_key: str
    ) -> tuple[bool, str, Optional[AccountSettings]]:
        """
        Set z.ai API key for user after validating it.

        Args:
            user_id: User ID
            api_key: The z.ai API key to save

        Returns:
            Tuple of (success, message, settings)
        """
        # Validate the API key by making a test request
        is_valid, error_msg = await self._validate_zai_api_key(api_key)

        if not is_valid:
            return False, error_msg, None

        # Save the key
        settings = await self.get_settings(user_id)
        settings.zai_api_key = api_key
        settings.updated_at = datetime.now()
        await self.repository.save(settings)

        logger.info(f"[{user_id}] z.ai API key saved successfully")
        return True, "✅ API ключ z.ai сохранён и проверен!", settings

    async def delete_zai_api_key(self, user_id: int) -> tuple[bool, str]:
        """
        Delete z.ai API key for user.

        Args:
            user_id: User ID

        Returns:
            Tuple of (success, message)
        """
        settings = await self.get_settings(user_id)
        if not settings.zai_api_key:
            return False, "❌ API ключ не найден"

        settings.zai_api_key = None
        settings.updated_at = datetime.now()
        await self.repository.save(settings)

        logger.info(f"[{user_id}] z.ai API key deleted")
        return True, "✅ API ключ удалён"

    async def has_zai_api_key(self, user_id: int) -> bool:
        """Check if user has a z.ai API key configured."""
        settings = await self.get_settings(user_id)
        return bool(settings.zai_api_key)

    async def _validate_zai_api_key(self, api_key: str) -> tuple[bool, str]:
        """
        Validate z.ai API key by making a test request.

        Args:
            api_key: The API key to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        import httpx

        # z.ai API endpoint
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://open.bigmodel.cn/api/anthropic")

        # Make a minimal request to check the key
        # Using the messages endpoint with a minimal request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        # Minimal request body - this will count against the user's quota
        # but is the only reliable way to validate the key
        data = {
            "model": "glm-4.5-air",  # Use cheapest model for validation
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "Hi"}]
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{base_url}/v1/messages",
                    headers=headers,
                    json=data
                )

                if response.status_code == 200:
                    return True, ""
                elif response.status_code == 401:
                    return False, "❌ Неверный API ключ (401 Unauthorized)"
                elif response.status_code == 403:
                    return False, "❌ Доступ запрещён (403 Forbidden). Проверьте права ключа."
                elif response.status_code == 429:
                    # Rate limited but key is valid
                    return True, ""
                else:
                    error_text = response.text[:200]
                    return False, f"❌ Ошибка API: {response.status_code}\n{error_text}"

        except httpx.TimeoutException:
            return False, "❌ Таймаут при проверке ключа. Попробуйте позже."
        except httpx.ConnectError:
            return False, "❌ Не удалось подключиться к z.ai API. Проверьте интернет."
        except Exception as e:
            logger.error(f"Error validating z.ai API key: {e}")
            return False, f"❌ Ошибка проверки: {str(e)}"

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

    def get_access_token_from_credentials(self) -> Optional[str]:
        """
        Extract access token from credentials file.

        Returns:
            Access token if available, None otherwise
        """
        try:
            if not os.path.exists(CREDENTIALS_PATH):
                return None

            with open(CREDENTIALS_PATH, "r") as f:
                data = json.load(f)

            return data.get("claudeAiOauth", {}).get("accessToken")
        except Exception as e:
            logger.error(f"Error reading access token from credentials: {e}")
            return None

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

    def get_env_for_mode(
        self, mode: AuthMode, local_config: Optional[LocalModelConfig] = None,
        zai_api_key: Optional[str] = None,
        proxy_config: Optional["ProxyConfig"] = None
    ) -> dict[str, str]:
        """
        Build environment variables for the specified auth mode.

        Args:
            mode: Authorization mode
            local_config: Local model configuration (required for LOCAL_MODEL mode)
            zai_api_key: User-provided z.ai API key (overrides env var)
            proxy_config: Pre-fetched proxy configuration (from async ProxyService)

        Returns:
            Dict of environment variables to set
        """
        env = {}

        if mode == AuthMode.ZAI_API:
            # z.ai API mode - use user's key if provided, otherwise env vars
            base_url = os.environ.get("ANTHROPIC_BASE_URL")
            model = os.environ.get("ANTHROPIC_MODEL")

            # User-provided key takes priority over env var
            if zai_api_key:
                auth_token = zai_api_key
            else:
                auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")

            if base_url:
                env["ANTHROPIC_BASE_URL"] = base_url
            if auth_token:
                env["ANTHROPIC_API_KEY"] = auth_token
            if model:
                env["ANTHROPIC_MODEL"] = model  # Keep z.ai default model in env

            logger.debug(f"z.ai mode env: base_url={base_url is not None}, model={model}, user_key={zai_api_key is not None}")

        elif mode == AuthMode.CLAUDE_ACCOUNT:
            # Claude Account mode - use credentials file with proxy

            # CRITICAL: Remove ALL API configuration to prevent mixing with z.ai API
            env["_REMOVE_ANTHROPIC_API_KEY"] = "1"
            env["_REMOVE_ANTHROPIC_AUTH_TOKEN"] = "1"
            env["_REMOVE_ANTHROPIC_BASE_URL"] = "1"

            # DO NOT extract or set ANTHROPIC_API_KEY for OAuth tokens!
            # SDK/CLI will read credentials.json directly from /root/.claude/.credentials.json
            # OAuth tokens (sk-ant-oat01-...) ONLY work when read by SDK/CLI natively, NOT via env var
            # Setting OAuth token as ANTHROPIC_API_KEY causes "Invalid API key" error
            logger.debug("Claude Account mode: SDK will read OAuth credentials from ~/.claude/.credentials.json")

            # Set proxy for accessing claude.ai (from pre-fetched proxy_config)
            if proxy_config and proxy_config.enabled:
                proxy_env = proxy_config.to_env_dict()
                env.update(proxy_env)
                # Add NO_PROXY for local networks
                env["NO_PROXY"] = NO_PROXY_VALUE
                env["no_proxy"] = NO_PROXY_VALUE
                logger.debug(f"Claude Account mode: using proxy {proxy_config.mask_credentials()}")
            else:
                # Bypass proxy for local network addresses
                env["NO_PROXY"] = NO_PROXY_VALUE
                env["no_proxy"] = NO_PROXY_VALUE
                logger.debug("Claude Account mode: no proxy configured")

            # Remove ZhipuAI/model configuration (use official Claude API with SDK defaults)
            env["_REMOVE_ANTHROPIC_MODEL"] = "1"
            env["_REMOVE_ANTHROPIC_DEFAULT_HAIKU_MODEL"] = "1"
            env["_REMOVE_ANTHROPIC_DEFAULT_SONNET_MODEL"] = "1"
            env["_REMOVE_ANTHROPIC_DEFAULT_OPUS_MODEL"] = "1"

        elif mode == AuthMode.LOCAL_MODEL and local_config:
            # Local model mode - use user-provided URL and model
            env["ANTHROPIC_BASE_URL"] = local_config.base_url
            if local_config.api_key:
                env["ANTHROPIC_API_KEY"] = local_config.api_key
            else:
                # Some local servers accept any key or none
                env["ANTHROPIC_API_KEY"] = "local-no-key"
            env["ANTHROPIC_MODEL"] = local_config.model_name

            # Remove proxy settings (local server is on local network)
            env["_REMOVE_HTTP_PROXY"] = "1"
            env["_REMOVE_HTTPS_PROXY"] = "1"
            env["_REMOVE_http_proxy"] = "1"
            env["_REMOVE_https_proxy"] = "1"

            logger.debug(f"Local model mode: url={local_config.base_url}, model={local_config.model_name}")

        return env

    def apply_env_for_mode(
        self,
        mode: AuthMode,
        base_env: dict = None,
        local_config: Optional[LocalModelConfig] = None,
        zai_api_key: Optional[str] = None,
        proxy_config: Optional["ProxyConfig"] = None
    ) -> dict[str, str]:
        """
        Apply environment variables for the specified auth mode.

        This creates a copy of the environment and modifies it appropriately.

        Args:
            mode: Authorization mode
            base_env: Base environment (defaults to os.environ)
            local_config: Local model configuration (required for LOCAL_MODEL mode)
            zai_api_key: User-provided z.ai API key (overrides env var)
            proxy_config: Pre-fetched proxy configuration (from async ProxyService)

        Returns:
            New environment dict ready for subprocess/SDK
        """
        if base_env is None:
            base_env = dict(os.environ)
        else:
            base_env = dict(base_env)

        mode_env = self.get_env_for_mode(mode, local_config=local_config, zai_api_key=zai_api_key, proxy_config=proxy_config)

        # Handle removal markers
        if mode_env.pop("_REMOVE_ANTHROPIC_API_KEY", None):
            base_env.pop("ANTHROPIC_API_KEY", None)
            base_env.pop("ANTHROPIC_AUTH_TOKEN", None)

        if mode_env.pop("_REMOVE_ANTHROPIC_BASE_URL", None):
            base_env.pop("ANTHROPIC_BASE_URL", None)

        # Remove model environment variables (let SDK use defaults)
        if mode_env.pop("_REMOVE_ANTHROPIC_MODEL", None):
            base_env.pop("ANTHROPIC_MODEL", None)
        if mode_env.pop("_REMOVE_ANTHROPIC_DEFAULT_HAIKU_MODEL", None):
            base_env.pop("ANTHROPIC_DEFAULT_HAIKU_MODEL", None)
        if mode_env.pop("_REMOVE_ANTHROPIC_DEFAULT_SONNET_MODEL", None):
            base_env.pop("ANTHROPIC_DEFAULT_SONNET_MODEL", None)
        if mode_env.pop("_REMOVE_ANTHROPIC_DEFAULT_OPUS_MODEL", None):
            base_env.pop("ANTHROPIC_DEFAULT_OPUS_MODEL", None)

        # Remove proxy environment variables (for local model mode)
        if mode_env.pop("_REMOVE_HTTP_PROXY", None):
            base_env.pop("HTTP_PROXY", None)
        if mode_env.pop("_REMOVE_HTTPS_PROXY", None):
            base_env.pop("HTTPS_PROXY", None)
        if mode_env.pop("_REMOVE_http_proxy", None):
            base_env.pop("http_proxy", None)
        if mode_env.pop("_REMOVE_https_proxy", None):
            base_env.pop("https_proxy", None)

        # Additional safety: For Claude Account mode, ensure API keys are removed
        # This is a double-check to prevent using old/stale API keys
        if mode == AuthMode.CLAUDE_ACCOUNT:
            # Only remove if ANTHROPIC_API_KEY is not explicitly set in mode_env
            if "ANTHROPIC_API_KEY" not in mode_env:
                base_env.pop("ANTHROPIC_API_KEY", None)
                base_env.pop("ANTHROPIC_AUTH_TOKEN", None)
                logger.debug("Claude Account mode: ensuring no API keys in environment")

        # Apply remaining env vars
        base_env.update(mode_env)

        return base_env

    def delete_credentials(self) -> tuple[bool, str]:
        """
        Delete the credentials file.

        Useful for re-authentication or switching accounts.

        Returns:
            Tuple of (success, message)
        """
        try:
            if os.path.exists(CREDENTIALS_PATH):
                os.remove(CREDENTIALS_PATH)
                logger.info(f"Deleted credentials file: {CREDENTIALS_PATH}")
                return True, "✅ Файл credentials.json удалён"
            else:
                return False, "❌ Файл credentials.json не найден"
        except Exception as e:
            logger.error(f"Error deleting credentials: {e}")
            return False, f"❌ Ошибка удаления: {str(e)}"


# Import repository here to avoid circular imports
from infrastructure.persistence.sqlite_account_repository import SQLiteAccountRepository
