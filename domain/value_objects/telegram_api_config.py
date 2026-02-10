"""Telegram API server configuration value object.

Defines a custom Telegram Bot API server URL for routing bot traffic
through a proxy/mirror instead of api.telegram.org.
"""

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class TelegramApiConfig:
    """Custom Telegram Bot API server configuration.

    When enabled, all bot traffic (messages, updates, file downloads)
    is routed through the specified server URL instead of api.telegram.org.

    Example URL: http://85.192.63.133:8089/telegram
    """

    server_url: Optional[str] = None
    enabled: bool = False

    @classmethod
    def from_url(cls, url: str) -> "TelegramApiConfig":
        """Create config from URL string with validation.

        Args:
            url: Full URL to custom Telegram API server.
                 Example: http://85.192.63.133:8089/telegram

        Raises:
            ValueError: If URL is invalid or uses unsupported scheme.
        """
        cleaned = url.strip().rstrip("/")
        if not cleaned:
            raise ValueError("URL cannot be empty")

        parsed = urlparse(cleaned)
        if not parsed.scheme or not parsed.hostname:
            raise ValueError(f"Invalid URL: {url}")
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"Unsupported scheme: {parsed.scheme}. Use http or https."
            )
        return cls(server_url=cleaned, enabled=True)

    @classmethod
    def disabled(cls) -> "TelegramApiConfig":
        """Create a disabled config (direct connection to api.telegram.org)."""
        return cls(server_url=None, enabled=False)

    @property
    def display_url(self) -> str:
        """Short display string for UI."""
        if not self.server_url:
            return "api.telegram.org"
        parsed = urlparse(self.server_url)
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.hostname}{port}{parsed.path}"
