"""Proxy settings repository interface"""

from abc import ABC, abstractmethod
from typing import Optional

from domain.entities.proxy_settings import ProxySettings
from domain.value_objects.user_id import UserId


class ProxyRepository(ABC):
    """Repository interface for proxy settings persistence"""

    @abstractmethod
    async def get_global_settings(self) -> Optional[ProxySettings]:
        """
        Get global proxy settings.

        Returns:
            Global ProxySettings or None if not configured
        """
        pass

    @abstractmethod
    async def get_user_settings(self, user_id: UserId) -> Optional[ProxySettings]:
        """
        Get user-specific proxy settings.

        Args:
            user_id: User identifier

        Returns:
            User ProxySettings or None if not configured
        """
        pass

    @abstractmethod
    async def save_global_settings(self, settings: ProxySettings) -> None:
        """
        Save global proxy settings.

        Args:
            settings: ProxySettings to save
        """
        pass

    @abstractmethod
    async def save_user_settings(self, settings: ProxySettings) -> None:
        """
        Save user-specific proxy settings.

        Args:
            settings: ProxySettings to save
        """
        pass

    @abstractmethod
    async def delete_global_settings(self) -> None:
        """Delete global proxy settings"""
        pass

    @abstractmethod
    async def delete_user_settings(self, user_id: UserId) -> None:
        """
        Delete user-specific proxy settings.

        Args:
            user_id: User identifier
        """
        pass
