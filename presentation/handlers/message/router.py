"""
Message Router - Registration Functions

This module provides router registration for message handlers.
Maintains backward compatibility with old API while using new refactored architecture.
"""

import logging
from aiogram import Router
from aiogram import F
from aiogram.filters import StateFilter

from .facade import MessageHandlersFacade
from .coordinator import MessageCoordinator

logger = logging.getLogger(__name__)


def register_handlers(router: Router, handlers) -> None:
    """
    Register message handlers with the router.

    Args:
        router: Aiogram router
        handlers: Either MessageHandlersFacade or MessageCoordinator instance

    This function works with both old facade and new coordinator for flexibility.
    """
    # Support both facade and coordinator
    if isinstance(handlers, MessageHandlersFacade):
        # Legacy facade - use its methods
        router.message.register(handlers.handle_document, F.document, StateFilter(None))
        router.message.register(handlers.handle_photo, F.photo, StateFilter(None))
        router.message.register(handlers.handle_text, F.text, StateFilter(None))
        logger.info("✓ Message handlers registered (via MessageHandlersFacade)")
    elif isinstance(handlers, MessageCoordinator):
        # New coordinator - use handle_message for all
        async def handle_any_message(message):
            await handlers.handle_message(message)

        router.message.register(handle_any_message, F.document, StateFilter(None))
        router.message.register(handle_any_message, F.photo, StateFilter(None))
        router.message.register(handle_any_message, F.text, StateFilter(None))
        logger.info("✓ Message handlers registered (via MessageCoordinator)")
    else:
        logger.error(f"❌ Unknown handlers type: {type(handlers)}")
        raise TypeError(f"handlers must be MessageHandlersFacade or MessageCoordinator, got {type(handlers)}")
