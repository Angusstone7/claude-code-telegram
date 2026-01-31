"""Variable input handler - state machine for variable creation/editing"""

import logging
from typing import TYPE_CHECKING, Optional

from aiogram.types import Message

from presentation.keyboards.keyboards import Keyboards
from .base import BaseMessageHandler

if TYPE_CHECKING:
    from application.services.bot_service import BotService
    from presentation.handlers.state.user_state import UserStateManager
    from presentation.handlers.state.hitl_manager import HITLManager
    from presentation.handlers.state.variable_manager import VariableInputManager
    from presentation.handlers.state.plan_manager import PlanApprovalManager
    from presentation.handlers.state.file_context import FileContextManager

logger = logging.getLogger(__name__)


class VariableInputHandler(BaseMessageHandler):
    """Handles variable input state machine"""

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

    # Copied from legacy messages.py:223-225
    def is_expecting_var_input(self, user_id: int) -> bool:
        """Check if we're expecting any variable input"""
        return self.variable_manager.is_active(user_id)

    # Copied from legacy messages.py:227-232
    def set_expecting_var_name(self, user_id: int, expecting: bool, menu_msg: Message = None):
        """Set whether we're expecting a variable name"""
        if expecting:
            self.variable_manager.start_add_flow(user_id, menu_msg)
        else:
            self.variable_manager.cancel(user_id)

    # Copied from legacy messages.py:234-236
    def set_expecting_var_value(self, user_id: int, var_name: str, menu_msg: Message = None):
        """Set that we're expecting a value for the given variable name"""
        self.variable_manager.move_to_value_step(user_id, var_name)

    # Copied from legacy messages.py:238-240
    def set_expecting_var_desc(self, user_id: int, var_name: str, var_value: str, menu_msg: Message = None):
        """Set that we're expecting a description for the variable"""
        self.variable_manager.move_to_description_step(user_id, var_value)

    # Copied from legacy messages.py:242-244
    def clear_var_state(self, user_id: int):
        """Clear all variable input state"""
        self.variable_manager.cancel(user_id)

    # Copied from legacy messages.py:246-248
    def get_pending_var_message(self, user_id: int) -> Optional[Message]:
        """Get the pending menu message to update"""
        return self.variable_manager.get_menu_message(user_id)

    # Copied from legacy messages.py:250-252
    def start_var_input(self, user_id: int, menu_msg: Message = None):
        """Start variable input flow"""
        self.variable_manager.start_add_flow(user_id, menu_msg)

    # Copied from legacy messages.py:254-256
    def start_var_edit(self, user_id: int, var_name: str, menu_msg: Message = None):
        """Start variable edit flow"""
        self.variable_manager.start_edit_flow(user_id, var_name, menu_msg)

    # Copied from legacy messages.py:258-260
    def cancel_var_input(self, user_id: int):
        """Cancel variable input and clear state"""
        self.variable_manager.cancel(user_id)

    # Copied from legacy messages.py:1544-1552
    async def save_variable_skip_desc(self, user_id: int, message: Message):
        """Save variable without description (called from callback)"""
        var_name, var_value = self.variable_manager.get_var_data(user_id)

        if not var_name or not var_value:
            self.variable_manager.cancel(user_id)
            return

        # This will be implemented in text_handler which has access to project_service and context_service
        # For now, just clear state
        self.variable_manager.complete(user_id)
