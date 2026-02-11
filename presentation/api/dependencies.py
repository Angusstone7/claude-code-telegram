"""FastAPI dependency injection — bridges DI container to FastAPI's Depends()."""

import logging
from typing import Optional

from shared.container import Container

logger = logging.getLogger(__name__)

# Module-level container reference, set during app creation
_container: Optional[Container] = None


def set_container(container: Container) -> None:
    """Set the DI container for FastAPI dependencies."""
    global _container
    _container = container
    logger.info("REST API: DI container connected")


def get_container() -> Container:
    """Get the DI container."""
    if _container is None:
        raise RuntimeError("DI container not initialized. Call set_container() first.")
    return _container


def get_project_service():
    """Get ProjectService from container."""
    return get_container().project_service()


def get_bot_service():
    """Get BotService from container."""
    return get_container().bot_service()


def get_claude_sdk():
    """Get ClaudeAgentSDKService from container (may be None)."""
    return get_container().claude_sdk()


def get_claude_proxy():
    """Get ClaudeCodeProxyService from container."""
    return get_container().claude_proxy()


def get_system_monitor():
    """Get SystemMonitor from container."""
    return get_container().system_monitor()


def get_context_service():
    """Get ContextService from container."""
    return get_container().context_service()


def get_runtime_config():
    """Get RuntimeConfigService from container."""
    return get_container().runtime_config()


def get_account_service():
    """Get AccountService from container."""
    return get_container().account_service()
