"""Plan approval handler - ExitPlanMode flow"""

import logging
from typing import TYPE_CHECKING

from .base import BaseMessageHandler

if TYPE_CHECKING:
    from application.services.bot_service import BotService
    from presentation.handlers.state.user_state import UserStateManager
    from presentation.handlers.state.hitl_manager import HITLManager
    from presentation.handlers.state.variable_manager import VariableInputManager
    from presentation.handlers.state.plan_manager import PlanApprovalManager
    from presentation.handlers.state.file_context import FileContextManager

logger = logging.getLogger(__name__)


class PlanApprovalHandler(BaseMessageHandler):
    """Handles plan approval flow (ExitPlanMode)"""

    def __init__(
        self,
        bot_service: "BotService",
        user_state: "UserStateManager",
        hitl_manager: "HITLManager",
        file_context_manager: "FileContextManager",
        variable_manager: "VariableInputManager",
        plan_manager: "PlanApprovalManager",
    ):
        super().__init__(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
        )

    # Copied from legacy messages.py:264-272
    async def handle_plan_response(self, user_id: int, response: str) -> bool:
        """Handle plan approval response from callback. Returns True if response was accepted."""
        # This method needs access to sdk_service which is in parent
        # For now, return False - will be implemented in coordinator with full access
        logger.warning(f"[{user_id}] Plan response not implemented in plan_handler: {response}")
        return False

    # Copied from legacy messages.py:274-276
    def set_expecting_plan_clarification(self, user_id: int, expecting: bool):
        """Set whether we're expecting plan clarification text"""
        self.plan_manager.set_expecting_clarification(user_id, expecting)
