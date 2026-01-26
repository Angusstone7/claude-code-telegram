"""
State Management Module

Manages user state for MessageHandlers, split by responsibility:
- UserStateManager: Core user state (sessions, working dirs)
- HITLManager: Human-in-the-Loop (permissions, questions)
- VariableInputManager: Variable input flow state machine
- PlanApprovalManager: Plan approval state (ExitPlanMode)
- FileContextManager: File upload context caching
"""

from presentation.handlers.state.user_state import UserStateManager, UserSession
from presentation.handlers.state.hitl_manager import HITLManager, HITLState
from presentation.handlers.state.variable_input import VariableInputManager, VariableInputStep
from presentation.handlers.state.plan_manager import PlanApprovalManager
from presentation.handlers.state.file_context import FileContextManager

__all__ = [
    "UserStateManager",
    "UserSession",
    "HITLManager",
    "HITLState",
    "VariableInputManager",
    "VariableInputStep",
    "PlanApprovalManager",
    "FileContextManager",
]
