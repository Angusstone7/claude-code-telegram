"""
Message Handlers Package

This package re-exports the original MessageHandlers from messages.py
which contains the full SDK integration logic.

The refactored handlers (base, text_handler, etc.) are incomplete and
should not be used until the SDK integration is properly migrated.
"""

# Import the WORKING MessageHandlers from messages.py (not the broken refactored version)
from presentation.handlers.messages import MessageHandlers, register_handlers

__all__ = [
    "MessageHandlers",
    "register_handlers",
]
