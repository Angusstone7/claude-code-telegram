"""Text message handler"""

import logging
from typing import TYPE_CHECKING

from aiogram.types import Message

from .base import BaseMessageHandler

if TYPE_CHECKING:
    from application.services.bot_service import BotService
    from presentation.handlers.state.user_state import UserStateManager
    from presentation.handlers.state.hitl_manager import HITLManager
    from presentation.handlers.state.variable_manager import VariableInputManager
    from presentation.handlers.state.plan_manager import PlanApprovalManager
    from presentation.handlers.state.file_context import FileContextManager
    from presentation.keyboards.keyboards import Keyboards

logger = logging.getLogger(__name__)


class TextMessageHandler(BaseMessageHandler):
    """Handles text message processing"""

    def __init__(
        self,
        bot_service: "BotService",
        user_state: "UserStateManager",
        hitl_manager: "HITLManager",
        file_context_manager: "FileContextManager",
        variable_manager: "VariableInputManager",
        plan_manager: "PlanApprovalManager",
        ai_request_handler=None,  # AIRequestHandler
        callback_handlers=None,
    ):
        super().__init__(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
        )
        self.ai_request_handler = ai_request_handler
        self.callback_handlers = callback_handlers

    # TODO: Copy from legacy messages.py:557-870
    async def handle_text(
        self,
        message: Message,
        prompt_override: str = None,
        force_new_session: bool = False,
        _from_batcher: bool = False
    ) -> None:
        """Handle text messages - main entry point"""
        pass

    # TODO: Copy from legacy messages.py:1393-1401
    async def _handle_answer_input(self, message: Message):
        """Handle text input for question answer"""
        pass

    # TODO: Copy from legacy messages.py:1403-1428
    async def _handle_clarification_input(self, message: Message):
        """Handle text input for permission clarification"""
        pass

    # TODO: Copy from legacy messages.py:1430-1448
    async def _handle_plan_clarification(self, message: Message):
        """Handle text input for plan clarification"""
        pass

    # TODO: Copy from legacy messages.py:1450-1458
    async def _handle_path_input(self, message: Message):
        """Handle text input for path"""
        pass

    # TODO: Copy from legacy messages.py:1460-1482
    async def _handle_var_name_input(self, message: Message):
        """Handle variable name input during add flow"""
        pass

    # TODO: Copy from legacy messages.py:1484-1530
    async def _handle_var_value_input(self, message: Message):
        """Handle variable value input during add/edit flow"""
        pass

    # TODO: Copy from legacy messages.py:1532-1542
    async def _handle_var_desc_input(self, message: Message):
        """Handle variable description input and save the variable"""
        pass

    # TODO: Copy from legacy messages.py:1554-1603
    async def _save_variable(self, message: Message, var_name: str, var_value: str, var_desc: str):
        """Save variable to context and show updated menu"""
        pass
