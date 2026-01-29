"""
Message Handlers - Refactored from God Object

This package contains specialized message handlers split from the original
1615-line MessageHandlers class:

- BaseMessageHandler: Base class with shared dependencies
- TextMessageHandler: Handles text messages
- FileMessageHandler: Handles documents and photos
- HITLHandler: Handles Human-in-the-Loop interactions
- VariableInputHandler: Handles variable input workflow (3-step)
- PlanApprovalHandler: Handles plan approval workflow
- MessageCoordinator: Coordinates all handlers
- MessageHandlersFacade: Backward compatibility facade (DEPRECATED)

✅ All 6 handlers are now implemented!
✅ Backward compatibility layer added!
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
    "MessageHandlersFacade",  # For backward compatibility
    "MessageHandlers",  # Legacy alias for MessageHandlersFacade
    "register_handlers",  # Router registration function
]
