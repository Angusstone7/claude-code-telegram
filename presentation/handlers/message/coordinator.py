"""
Message Coordinator

Coordinates all message handlers and routes messages to appropriate handlers.
Replaces the original MessageHandlers God Object.
"""

import logging
from typing import TYPE_CHECKING, Optional
from aiogram.types import Message

from .base import BaseMessageHandler
from .text_handler import TextMessageHandler
from .file_handler import FileMessageHandler
from .hitl_handler import HITLHandler
from .variable_handler import VariableInputHandler
from .plan_handler import PlanApprovalHandler
from .ai_request_handler import AIRequestHandler

if TYPE_CHECKING:
    from application.services.bot_service import BotService
    from presentation.handlers.state.user_state import UserStateManager
    from presentation.handlers.state.hitl_manager import HITLManager
    from presentation.handlers.state.file_context_manager import FileContextManager
    from presentation.handlers.state.variable_manager import VariableManager
    from presentation.handlers.state.plan_manager import PlanManager

logger = logging.getLogger(__name__)


class MessageCoordinator:
    """
    Coordinates message routing to specialized handlers.

    This class replaces the God Object MessageHandlers (1615 lines)
    with a clean coordinator pattern that delegates to specialized handlers.

    Architecture:
    - TextMessageHandler: Handles text messages
    - FileMessageHandler: Handles documents/photos
    - HITLHandler: Handles Human-in-the-Loop
    - VariableInputHandler: Handles variable workflow
    - PlanApprovalHandler: Handles plan approval
    """

    def __init__(
        self,
        bot_service: "BotService",
        user_state: "UserStateManager",
        hitl_manager: "HITLManager",
        file_context_manager: "FileContextManager",
        variable_manager: "VariableManager",
        plan_manager: "PlanManager",
        file_processor_service=None,
        context_service=None,
        project_service=None,
        sdk_service=None,
        claude_proxy=None,
        message_batcher=None,
        callback_handlers=None,
    ):
        """
        Initialize coordinator with shared dependencies.

        Args:
            bot_service: Bot service for AI interactions
            user_state: User state manager
            hitl_manager: Human-in-the-loop manager
            file_context_manager: File context manager
            variable_manager: Variable manager
            plan_manager: Plan manager
            file_processor_service: File processor service (optional)
            context_service: Context service for variables (optional)
            project_service: Project service (optional)
            sdk_service: Claude SDK service (optional)
            claude_proxy: Claude CLI proxy service (optional)
            message_batcher: Message batcher (optional)
            callback_handlers: Callback handlers (optional)
        """
        # Store dependencies
        self._bot_service = bot_service
        self._user_state = user_state
        self._hitl_manager = hitl_manager
        self._file_context = file_context_manager
        self._variables = variable_manager
        self._plans = plan_manager
        self._file_processor = file_processor_service
        self._sdk_service = sdk_service
        self._claude_proxy = claude_proxy
        self._message_batcher = message_batcher
        self._callback_handlers = callback_handlers
        self._project_service = project_service
        self._context_service = context_service

        # Initialize AI request handler (handles SDK/CLI integration)
        self._ai_request_handler = AIRequestHandler(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
            sdk_service=sdk_service,
            claude_proxy=claude_proxy,
            project_service=project_service,
            context_service=context_service,
        )

        # Initialize specialized handlers
        self._text_handler = TextMessageHandler(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
            ai_request_handler=self._ai_request_handler,
            message_batcher=message_batcher,
            callback_handlers=callback_handlers,
        )

        self._file_handler = FileMessageHandler(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
            file_processor_service=file_processor_service,
        )

        self._hitl_handler = HITLHandler(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
        )

        self._variable_handler = VariableInputHandler(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
            context_service=context_service,
            project_service=project_service,
        )

        self._plan_handler = PlanApprovalHandler(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
        )

        logger.info("✅ MessageCoordinator initialized with ALL 6 specialized handlers")

    async def handle_message(self, message: Message) -> None:
        """
        Main entry point for message handling.

        Routes message to appropriate specialized handler.

        Args:
            message: Telegram message
        """
        user_id = message.from_user.id

        # Determine which handler should process this message
        if message.document:
            await self._handle_document(message)
        elif message.photo:
            await self._handle_photo(message)
        elif message.text:
            await self._text_handler.handle_text_message(message)
        else:
            logger.warning(f"[{user_id}] Unknown message type")
            await message.answer("Неподдерживаемый тип сообщения")

    async def _handle_document(self, message: Message) -> None:
        """Handle document message - delegates to FileMessageHandler"""
        await self._file_handler.handle_document(message)

    async def _handle_photo(self, message: Message) -> None:
        """Handle photo message - delegates to FileMessageHandler"""
        await self._file_handler.handle_photo(message)

    # === Delegation methods for backward compatibility ===

    def is_yolo_mode(self, user_id: int) -> bool:
        """Check if YOLO mode is enabled"""
        return self._user_state.is_yolo_mode(user_id)

    def set_yolo_mode(self, user_id: int, enabled: bool) -> None:
        """Set YOLO mode"""
        self._user_state.set_yolo_mode(user_id, enabled)

    def is_step_streaming_mode(self, user_id: int) -> bool:
        """Check if step streaming mode is enabled"""
        return self._user_state.is_step_streaming_mode(user_id)

    def set_step_streaming_mode(self, user_id: int, enabled: bool) -> None:
        """Set step streaming mode"""
        self._user_state.set_step_streaming_mode(user_id, enabled)

    def get_working_dir(self, user_id: int) -> str:
        """Get user's working directory"""
        return self._user_state.get_working_dir(user_id)

    def set_working_dir(self, user_id: int, path: str) -> None:
        """Set user's working directory"""
        self._user_state.set_working_dir(user_id, path)

    async def get_project_working_dir(self, user_id: int) -> str:
        """Get working directory from current project (async, more accurate)"""
        if hasattr(self, '_project_service') and self._project_service:
            try:
                from domain.value_objects.user_id import UserId
                uid = UserId.from_int(user_id)
                project = await self._project_service.get_current(uid)
                if project and project.working_dir:
                    return project.working_dir
            except Exception as e:
                logger.warning(f"Error getting project working_dir: {e}")
        # Fallback to state
        return self._user_state.get_working_dir(user_id)

    def cleanup(self, user_id: int) -> None:
        """Clean up all state for user"""
        self._user_state.cleanup(user_id)
        self._hitl_manager.cleanup(user_id)
        logger.debug(f"[{user_id}] State cleaned up")

    # === HITL Response Handlers (called by callback handlers) ===

    async def handle_permission_response(self, user_id: int, approved: bool, clarification_text: str = None) -> bool:
        """Handle permission response from callback. Returns True if response was accepted."""
        if self._sdk_service:
            success = await self._sdk_service.respond_to_permission(user_id, approved, clarification_text)
            if success:
                return True

        # Fall back to HITL manager handling
        result = await self._hitl_manager.respond_to_permission(user_id, approved, clarification_text)
        return result if result is not None else False

    async def handle_question_response(self, user_id: int, answer: str):
        """Handle question response from callback"""
        if self._sdk_service:
            success = await self._sdk_service.respond_to_question(user_id, answer)
            if success:
                return

        await self._hitl_manager.respond_to_question(user_id, answer)

    async def handle_plan_response(self, user_id: int, response: str) -> bool:
        """Handle plan approval response from callback. Returns True if response was accepted."""
        if self._sdk_service:
            success = await self._sdk_service.respond_to_plan(user_id, response)
            if success:
                self._plans.cleanup(user_id)
                return True
        logger.warning(f"[{user_id}] Failed to respond to plan: {response}")
        return False

    # === Variable Input State (delegated to VariableInputManager) ===

    def clear_var_state(self, user_id: int):
        """Clear variable input state"""
        self._variables.clear_state(user_id)

    def get_pending_var_message(self, user_id: int):
        """Get pending variable message"""
        return self._variables.get_pending_message(user_id)

    def set_expecting_var_name(self, user_id: int, expecting: bool, menu_msg=None):
        """Set expecting variable name input"""
        self._variables.set_expecting_name(user_id, expecting, menu_msg)

    def set_expecting_var_value(self, user_id: int, var_name: str, menu_msg=None):
        """Set expecting variable value input"""
        self._variables.set_expecting_value(user_id, var_name, menu_msg)

    def set_expecting_var_desc(self, user_id: int, var_name: str, var_value: str, menu_msg=None):
        """Set expecting variable description input"""
        self._variables.set_expecting_description(user_id, var_name, var_value, menu_msg)

    async def save_variable_skip_desc(self, user_id: int, message):
        """Save variable without description"""
        var_name = self._variables.get_var_name(user_id)
        var_value = self._variables.get_var_value(user_id)
        if var_name and var_value:
            await self._variables_handler._save_variable(message, var_name, var_value, "")

    # === Question State ===

    def get_pending_question_option(self, user_id: int, index: int) -> str:
        """Get pending question option by index"""
        return self._hitl_manager.get_pending_question_option(user_id, index)

    # === Session State ===

    def set_continue_session(self, user_id: int, session_id: str):
        """Set continue session ID"""
        self._user_state.set_continue_session_id(user_id, session_id)

    def clear_session_cache(self, user_id: int) -> None:
        """Clear session cache"""
        self._user_state.clear_session_cache(user_id)
