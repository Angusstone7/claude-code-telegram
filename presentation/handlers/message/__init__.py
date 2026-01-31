"""
Message handlers package - modular architecture

This package provides a modular, maintainable alternative to the monolithic
messages.py (1615 LOC) file. Each handler has a single, well-defined responsibility.

Architecture:
- facade.py: Backward compatibility facade (MessageHandlers class)
- coordinator.py: Message routing and orchestration
- ai_request_handler.py: SDK/CLI integration (task execution, callbacks)
- text_handler.py: Text message processing and input handlers
- file_handler.py: File and photo upload processing
- hitl_handler.py: Human-in-the-Loop state management
- variable_handler.py: Variable input state machine
- plan_handler.py: Plan approval flow
- base.py: Base handler with common functionality
"""

from .coordinator import MessageCoordinator
from .facade import MessageHandlersFacade, MessageHandlers
from .ai_request_handler import AIRequestHandler
from .text_handler import TextMessageHandler
from .file_handler import FileMessageHandler
from .hitl_handler import HITLHandler
from .variable_handler import VariableInputHandler
from .plan_handler import PlanApprovalHandler
from .base import BaseMessageHandler

# Router function for backward compatibility
from .coordinator import register_handlers

__all__ = [
    # Main exports
    "MessageHandlers",
    "MessageHandlersFacade",
    "MessageCoordinator",
    "register_handlers",

    # Individual handlers (for testing or advanced usage)
    "AIRequestHandler",
    "TextMessageHandler",
    "FileMessageHandler",
    "HITLHandler",
    "VariableInputHandler",
    "PlanApprovalHandler",
    "BaseMessageHandler",
]
