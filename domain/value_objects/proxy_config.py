"""Proxy configuration value object"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urlparse


class ProxyType(Enum):
    """Supported proxy types"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"


@dataclass(frozen=True)
class ProxyConfig:
    """
    Value object representing proxy configuration.

    Immutable representation of proxy settings including type, host, port,
    and optional authentication credentials.
    """

    proxy_type: ProxyType
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    enabled: bool = True

    def __post_init__(self):
        """Validate proxy configuration"""
        if not self.host:
            raise ValueError("Proxy host cannot be empty")

        if not isinstance(self.port, int) or not (1 <= self.port <= 65535):
            raise ValueError(f"Invalid port: {self.port}. Must be between 1 and 65535")

        if not isinstance(self.proxy_type, ProxyType):
            raise ValueError(f"Invalid proxy type: {self.proxy_type}")

    def to_url(self) -> str:
        """
        Convert to proxy URL string.

        Returns:
            Proxy URL in format: protocol://[user:pass@]host:port
        """
        if self.username and self.password:
            return f"{self.proxy_type.value}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.proxy_type.value}://{self.host}:{self.port}"

    def to_dict(self) -> dict:
        """Convert to dictionary for aiohttp/httpx"""
        if not self.enabled:
            return {}

        url = self.to_url()
        return {
            "http": url,
            "https": url
        }

    def to_env_dict(self) -> dict:
        """Convert to environment variables dict"""
        if not self.enabled:
            return {}

        url = self.to_url()
        return {
            "HTTP_PROXY": url,
            "HTTPS_PROXY": url,
            "http_proxy": url,
            "https_proxy": url
        }

    def mask_credentials(self) -> str:
        """Return masked URL for logging"""
        if self.username:
            return f"{self.proxy_type.value}://{self.username}:***@{self.host}:{self.port}"
        return f"{self.proxy_type.value}://{self.host}:{self.port}"

    @classmethod
    def from_url(cls, url: str, enabled: bool = True) -> "ProxyConfig":
        """
        Create ProxyConfig from URL string.

        Args:
            url: Proxy URL in format: protocol://[user:pass@]host:port
            enabled: Whether proxy is enabled

        Returns:
            ProxyConfig instance

        Raises:
            ValueError: If URL is invalid
        """
        try:
            parsed = urlparse(url)

            # Determine proxy type
            scheme = parsed.scheme.lower()
            if scheme in ("http", "https"):
                proxy_type = ProxyType.HTTP if scheme == "http" else ProxyType.HTTPS
            elif scheme == "socks5":
                proxy_type = ProxyType.SOCKS5
            else:
                raise ValueError(f"Unsupported proxy scheme: {scheme}")

            # Extract host and port
            if not parsed.hostname:
                raise ValueError("Missing hostname in proxy URL")

            host = parsed.hostname
            port = parsed.port or (1080 if scheme == "socks5" else 8080)

            # Extract credentials
            username = parsed.username
            password = parsed.password

            return cls(
                proxy_type=proxy_type,
                host=host,
                port=port,
                username=username,
                password=password,
                enabled=enabled
            )
        except Exception as e:
            raise ValueError(f"Invalid proxy URL: {url}. Error: {e}")

    @classmethod
    def disabled(cls) -> "ProxyConfig":
        """Create a disabled proxy config (no proxy)"""
        return cls(
            proxy_type=ProxyType.HTTP,
            host="disabled",
            port=8080,
            enabled=False
        )
