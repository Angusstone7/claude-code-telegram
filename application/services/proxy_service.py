"""Proxy settings service"""

import logging
import uuid
from typing import Optional
import aiohttp

from domain.entities.proxy_settings import ProxySettings
from domain.repositories.proxy_repository import ProxyRepository
from domain.value_objects.proxy_config import ProxyConfig, ProxyType
from domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)

# NO_PROXY addresses - local networks that should bypass proxy
NO_PROXY_VALUE = "localhost,127.0.0.1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12,host.docker.internal,.local"


class ProxyService:
    """
    Application service for managing proxy settings.

    Handles business logic for proxy configuration, including:
    - Getting/setting global and user-specific proxies
    - Testing proxy connections
    - Providing proxy configuration for HTTP clients
    """

    def __init__(self, proxy_repository: ProxyRepository):
        self.proxy_repository = proxy_repository

    async def get_effective_proxy(self, user_id: UserId) -> Optional[ProxyConfig]:
        """
        Get effective proxy for user (user-specific or fallback to global).

        Args:
            user_id: User identifier

        Returns:
            ProxyConfig if configured, None otherwise
        """
        # Try user-specific first
        user_settings = await self.proxy_repository.get_user_settings(user_id)
        if user_settings and user_settings.has_proxy():
            logger.debug(f"Using user-specific proxy for user {user_id.value}")
            return user_settings.proxy_config

        # Fallback to global
        global_settings = await self.proxy_repository.get_global_settings()
        if global_settings and global_settings.has_proxy():
            logger.debug(f"Using global proxy for user {user_id.value}")
            return global_settings.proxy_config

        logger.debug(f"No proxy configured for user {user_id.value}")
        return None

    async def get_global_proxy(self) -> Optional[ProxyConfig]:
        """Get global proxy configuration"""
        settings = await self.proxy_repository.get_global_settings()
        if settings and settings.has_proxy():
            return settings.proxy_config
        return None

    async def set_global_proxy(self, proxy_url: str) -> ProxySettings:
        """
        Set global proxy from URL string.

        Args:
            proxy_url: Proxy URL in format: protocol://[user:pass@]host:port

        Returns:
            Created ProxySettings

        Raises:
            ValueError: If URL is invalid
        """
        proxy_config = ProxyConfig.from_url(proxy_url, enabled=True)

        settings = ProxySettings(
            id=str(uuid.uuid4()),
            user_id=None,  # Global
            proxy_config=proxy_config
        )

        await self.proxy_repository.save_global_settings(settings)
        logger.info(f"Global proxy set to {proxy_config.mask_credentials()}")

        return settings

    async def set_user_proxy(self, user_id: UserId, proxy_url: str) -> ProxySettings:
        """
        Set user-specific proxy from URL string.

        Args:
            user_id: User identifier
            proxy_url: Proxy URL in format: protocol://[user:pass@]host:port

        Returns:
            Created ProxySettings

        Raises:
            ValueError: If URL is invalid
        """
        proxy_config = ProxyConfig.from_url(proxy_url, enabled=True)

        settings = ProxySettings(
            id=str(uuid.uuid4()),
            user_id=user_id,
            proxy_config=proxy_config
        )

        await self.proxy_repository.save_user_settings(settings)
        logger.info(f"User {user_id.value} proxy set to {proxy_config.mask_credentials()}")

        return settings

    async def set_custom_proxy(
        self,
        proxy_type: ProxyType,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
        user_id: Optional[UserId] = None
    ) -> ProxySettings:
        """
        Set proxy with individual parameters.

        Args:
            proxy_type: Type of proxy (HTTP, HTTPS, SOCKS5)
            host: Proxy host
            port: Proxy port
            username: Optional username
            password: Optional password
            user_id: If None, sets global; otherwise user-specific

        Returns:
            Created ProxySettings
        """
        proxy_config = ProxyConfig(
            proxy_type=proxy_type,
            host=host,
            port=port,
            username=username,
            password=password,
            enabled=True
        )

        settings = ProxySettings(
            id=str(uuid.uuid4()),
            user_id=user_id,
            proxy_config=proxy_config
        )

        if user_id:
            await self.proxy_repository.save_user_settings(settings)
            logger.info(f"User {user_id.value} proxy set to {proxy_config.mask_credentials()}")
        else:
            await self.proxy_repository.save_global_settings(settings)
            logger.info(f"Global proxy set to {proxy_config.mask_credentials()}")

        return settings

    async def disable_global_proxy(self) -> None:
        """Disable global proxy"""
        await self.proxy_repository.delete_global_settings()
        logger.info("Global proxy disabled")

    async def disable_user_proxy(self, user_id: UserId) -> None:
        """Disable user-specific proxy"""
        await self.proxy_repository.delete_user_settings(user_id)
        logger.info(f"User {user_id.value} proxy disabled")

    async def test_proxy(self, proxy_config: ProxyConfig, test_url: str = "https://httpbin.org/ip") -> tuple[bool, str]:
        """
        Test proxy connection.

        Args:
            proxy_config: Proxy configuration to test
            test_url: URL to test against

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not proxy_config.enabled:
            return False, "Proxy is disabled"

        try:
            proxy_dict = proxy_config.to_dict()
            proxy_url = proxy_dict.get("https") or proxy_dict.get("http")

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(test_url, proxy=proxy_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        origin_ip = data.get("origin", "unknown")
                        return True, f"Подключение успешно! IP: {origin_ip}"
                    else:
                        return False, f"Ошибка HTTP {response.status}"

        except aiohttp.ClientProxyConnectionError as e:
            return False, f"Ошибка подключения к прокси: {str(e)}"
        except aiohttp.ClientError as e:
            return False, f"Ошибка сети: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error testing proxy: {e}")
            return False, f"Неожиданная ошибка: {str(e)}"

    def get_env_dict(self, proxy_config: Optional[ProxyConfig]) -> dict:
        """
        Get environment variables dict for proxy.

        Args:
            proxy_config: Proxy configuration

        Returns:
            Dict with HTTP_PROXY, HTTPS_PROXY, NO_PROXY etc.
        """
        if not proxy_config or not proxy_config.enabled:
            return {"NO_PROXY": NO_PROXY_VALUE}

        env_dict = proxy_config.to_env_dict()
        env_dict["NO_PROXY"] = NO_PROXY_VALUE
        env_dict["no_proxy"] = NO_PROXY_VALUE

        return env_dict
