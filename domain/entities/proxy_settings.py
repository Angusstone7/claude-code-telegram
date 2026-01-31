"""Proxy settings domain entity"""

from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from domain.value_objects.proxy_config import ProxyConfig
from domain.value_objects.user_id import UserId


@dataclass
class ProxySettings:
    """
    Domain entity representing user's proxy settings.

    Manages proxy configuration per user or globally.
    """

    id: str
    user_id: Optional[UserId]  # None = global settings
    proxy_config: Optional[ProxyConfig]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def update_proxy(self, proxy_config: ProxyConfig) -> None:
        """Update proxy configuration"""
        self.proxy_config = proxy_config
        self.updated_at = datetime.now()

    def disable_proxy(self) -> None:
        """Disable proxy"""
        if self.proxy_config:
            # Create disabled version
            self.proxy_config = ProxyConfig.disabled()
            self.updated_at = datetime.now()

    def is_global(self) -> bool:
        """Check if this is global settings"""
        return self.user_id is None

    def has_proxy(self) -> bool:
        """Check if proxy is configured and enabled"""
        return self.proxy_config is not None and self.proxy_config.enabled

    def get_proxy_url(self) -> Optional[str]:
        """Get proxy URL if configured"""
        if self.has_proxy():
            return self.proxy_config.to_url()
        return None

    def get_proxy_dict(self) -> dict:
        """Get proxy configuration as dict for HTTP clients"""
        if self.has_proxy():
            return self.proxy_config.to_dict()
        return {}
