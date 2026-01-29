"""
Message Router - Registration Functions

This module provides router registration for message handlers.
Maintains backward compatibility with old API while using new refactored architecture.
"""

import logging
from aiogram import Router
from aiogram import F
from aiogram.filters import StateFilter

logger = logging.getLogger(__name__)


def register_handlers(router: Router, handlers) -> None:
    """
    Register message handlers with the router.

    Args:
        router: Aiogram router
        handlers: MessageHandlers instance (refactored or legacy)

    This function works with any handler that has handle_text, handle_document, handle_photo methods.
    """
    # Check if handlers has the required methods
    if not (hasattr(handlers, 'handle_text') and
            hasattr(handlers, 'handle_document') and
            hasattr(handlers, 'handle_photo')):
        logger.error(f"❌ Handlers missing required methods: {type(handlers)}")
        raise TypeError(
            f"handlers must have handle_text, handle_document, and handle_photo methods, "
            f"got {type(handlers)}"
        )

    # Register handlers using their methods
    router.message.register(handlers.handle_document, F.document, StateFilter(None))
    router.message.register(handlers.handle_photo, F.photo, StateFilter(None))
    router.message.register(handlers.handle_text, F.text, StateFilter(None))

    handler_type = type(handlers).__name__
    logger.info(f"✓ Message handlers registered (via {handler_type})")
