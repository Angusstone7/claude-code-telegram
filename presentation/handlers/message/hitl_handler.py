"""HITL (Human-in-the-Loop) handler - permissions and questions"""

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


class HITLHandler(BaseMessageHandler):
    """Handles HITL (Human-in-the-Loop) callbacks"""

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

    # Copied from legacy messages.py:189-191
    def set_expecting_answer(self, user_id: int, expecting: bool):
        """Set whether we're expecting a text answer from user"""
        self.hitl_manager.set_expecting_answer(user_id, expecting)

    # Copied from legacy messages.py:193-195
    def set_expecting_path(self, user_id: int, expecting: bool):
        """Set whether we're expecting a path from user"""
        self.hitl_manager.set_expecting_path(user_id, expecting)

    # Copied from legacy messages.py:197-199
    def get_pending_question_option(self, user_id: int, index: int) -> str:
        """Get option text by index from pending question"""
        return self.hitl_manager.get_option_by_index(user_id, index)

    # Copied from legacy messages.py:201-210
    async def handle_permission_response(self, user_id: int, approved: bool, clarification_text: str = None) -> bool:
        """Handle permission response from callback. Returns True if response was accepted."""
        # Check if SDK backend is available and handle
        # Note: sdk_service is accessed through parent's reference if needed
        # For now, delegate to HITL manager
        result = await self.hitl_manager.respond_to_permission(user_id, approved, clarification_text)
        return result if result is not None else False

    # Copied from legacy messages.py:212-219
    async def handle_question_response(self, user_id: int, answer: str):
        """Handle question response from callback"""
        await self.hitl_manager.respond_to_question(user_id, answer)
