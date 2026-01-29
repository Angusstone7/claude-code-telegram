"""
Message Handlers Package (Refactored)

This package contains the refactored message handlers split by responsibility.
Exports backward-compatible MessageHandlers (alias for MessageHandlersFacade).
"""

from .base import BaseMessageHandler
from .text_handler import TextMessageHandler
from .file_handler import FileMessageHandler
from .hitl_handler import HITLHandler
from .variable_handler import VariableInputHandler
from .plan_handler import PlanApprovalHandler
from .coordinator import MessageCoordinator
from .facade import MessageHandlersFacade
from .router import register_handlers
from .ai_request_handler import AIRequestHandler

# Backward compatibility alias (old name → new implementation)
MessageHandlers = MessageHandlersFacade

__all__ = [
    "BaseMessageHandler",
    "TextMessageHandler",
    "FileMessageHandler",
    "HITLHandler",
    "VariableInputHandler",
    "PlanApprovalHandler",
    "MessageCoordinator",
    "MessageHandlersFacade",
    "MessageHandlers",  # Legacy alias for MessageHandlersFacade
    "register_handlers",
    "AIRequestHandler",
]
