"""Message coordinator - routes messages to appropriate handlers"""

import logging
from typing import TYPE_CHECKING, Optional

from aiogram.types import Message
from aiogram import Router

from .ai_request_handler import AIRequestHandler
from .text_handler import TextMessageHandler
from .file_handler import FileMessageHandler
from .hitl_handler import HITLHandler
from .variable_handler import VariableInputHandler
from .plan_handler import PlanApprovalHandler

if TYPE_CHECKING:
    from application.services.bot_service import BotService
    from application.services.project_service import ProjectService
    from application.services.context_service import ContextService
    from application.services.file_processor_service import FileProcessorService
    from infrastructure.claude_code.proxy_service import ClaudeCodeProxyService
    from infrastructure.claude_code.sdk_service import ClaudeAgentSDKService
    from presentation.handlers.state.user_state import UserStateManager
    from presentation.handlers.state.hitl_manager import HITLManager
    from presentation.handlers.state.variable_manager import VariableInputManager
    from presentation.handlers.state.plan_manager import PlanApprovalManager
    from presentation.handlers.state.file_context import FileContextManager

logger = logging.getLogger(__name__)


class MessageCoordinator:
    """Coordinates message routing to specialized handlers"""

    def __init__(
        self,
        bot_service: "BotService",
        user_state: "UserStateManager",
        hitl_manager: "HITLManager",
        file_context_manager: "FileContextManager",
        variable_manager: "VariableInputManager",
        plan_manager: "PlanApprovalManager",
        file_processor_service=None,
        context_service=None,
        project_service=None,
        sdk_service=None,
        claude_proxy=None,
        default_working_dir: str = "/root",
        message_batcher=None,
        callback_handlers=None,
    ):
        # Store all dependencies
        self._bot_service = bot_service
        self._user_state = user_state
        self._hitl_manager = hitl_manager
        self._file_context_manager = file_context_manager
        self._variable_manager = variable_manager
        self._plan_manager = plan_manager
        self._file_processor_service = file_processor_service
        self._context_service = context_service
        self._project_service = project_service
        self._callback_handlers = callback_handlers
        self._default_working_dir = default_working_dir

        # Create AI request handler
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
            default_working_dir=default_working_dir,
        )

        # Create text handler
        self._text_handler = TextMessageHandler(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
            ai_request_handler=self._ai_request_handler,
            callback_handlers=callback_handlers,
            project_service=project_service,
            context_service=context_service,
            file_processor_service=file_processor_service,
            message_batcher=message_batcher,
            use_sdk=True,  # Will be determined from sdk_service availability
            sdk_service=sdk_service,
            claude_proxy=claude_proxy,
        )

        # Create file handler
        self._file_handler = FileMessageHandler(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
            file_processor_service=file_processor_service,
            ai_request_handler=self._ai_request_handler,
        )

        # Create HITL handler
        self._hitl_handler = HITLHandler(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
        )

        # Create variable handler
        self._variable_handler = VariableInputHandler(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
        )

        # Create plan handler
        self._plan_handler = PlanApprovalHandler(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
        )

        # Store for backward compatibility
        self.bot_service = bot_service

    # === Message Routing ===

    async def handle_message(self, message: Message):
        """Route message to appropriate handler"""
        if message.document:
            await self.handle_document(message)
        elif message.photo:
            await self.handle_photo(message)
        elif message.text:
            await self.handle_text(message)

    # === Public API (delegated to appropriate handlers) ===

    # YOLO Mode - delegate to user_state
    def is_yolo_mode(self, user_id: int) -> bool:
        """Check if YOLO mode is enabled for user"""
        return self._user_state.is_yolo_mode(user_id)

    def set_yolo_mode(self, user_id: int, enabled: bool):
        """Set YOLO mode for user"""
        self._user_state.set_yolo_mode(user_id, enabled)

    # Step Streaming Mode - delegate to user_state
    def is_step_streaming_mode(self, user_id: int) -> bool:
        """Check if step streaming mode is enabled"""
        return self._user_state.is_step_streaming_mode(user_id)

    def set_step_streaming_mode(self, user_id: int, enabled: bool):
        """Set step streaming mode"""
        self._user_state.set_step_streaming_mode(user_id, enabled)

    # Working Directory - delegate to user_state
    def get_working_dir(self, user_id: int) -> str:
        """Get user's working directory"""
        return self._user_state.get_working_dir(user_id)

    async def get_project_working_dir(self, user_id: int) -> str:
        """Get working directory from current project (async)"""
        # This will be implemented in text_handler since it needs project_service
        return self._user_state.get_working_dir(user_id)

    def set_working_dir(self, user_id: int, path: str):
        """Set user's working directory"""
        self._user_state.set_working_dir(user_id, path)

    # Session Management - delegate to user_state
    def clear_session_cache(self, user_id: int) -> None:
        """Clear in-memory session cache"""
        self._user_state.clear_session_cache(user_id)

    def set_continue_session(self, user_id: int, session_id: str):
        """Set session to continue on next message"""
        self._user_state.set_continue_session_id(user_id, session_id)

    # HITL State - delegate to HITL handler
    def set_expecting_answer(self, user_id: int, expecting: bool):
        """Set whether expecting text answer"""
        return self._hitl_handler.set_expecting_answer(user_id, expecting)

    def set_expecting_path(self, user_id: int, expecting: bool):
        """Set whether expecting path"""
        return self._hitl_handler.set_expecting_path(user_id, expecting)

    def get_pending_question_option(self, user_id: int, index: int) -> str:
        """Get option text from pending question"""
        return self._hitl_handler.get_pending_question_option(user_id, index)

    async def handle_permission_response(self, user_id: int, approved: bool, clarification_text: str = None) -> bool:
        """Handle permission response"""
        return await self._hitl_handler.handle_permission_response(user_id, approved, clarification_text)

    async def handle_question_response(self, user_id: int, answer: str):
        """Handle question response"""
        return await self._hitl_handler.handle_question_response(user_id, answer)

    # Variable Input State - delegate to variable handler
    def is_expecting_var_input(self, user_id: int) -> bool:
        """Check if expecting variable input"""
        return self._variable_handler.is_expecting_var_input(user_id)

    def set_expecting_var_name(self, user_id: int, expecting: bool, menu_msg=None):
        """Set expecting variable name"""
        return self._variable_handler.set_expecting_var_name(user_id, expecting, menu_msg)

    def set_expecting_var_value(self, user_id: int, var_name: str, menu_msg=None):
        """Set expecting variable value"""
        return self._variable_handler.set_expecting_var_value(user_id, var_name, menu_msg)

    def set_expecting_var_desc(self, user_id: int, var_name: str, var_value: str, menu_msg=None):
        """Set expecting variable description"""
        return self._variable_handler.set_expecting_var_desc(user_id, var_name, var_value, menu_msg)

    def clear_var_state(self, user_id: int):
        """Clear variable input state"""
        return self._variable_handler.clear_var_state(user_id)

    def get_pending_var_message(self, user_id: int):
        """Get pending variable message"""
        return self._variable_handler.get_pending_var_message(user_id)

    def start_var_input(self, user_id: int, menu_msg=None):
        """Start variable input flow"""
        return self._variable_handler.start_var_input(user_id, menu_msg)

    def start_var_edit(self, user_id: int, var_name: str, menu_msg=None):
        """Start variable edit flow"""
        return self._variable_handler.start_var_edit(user_id, var_name, menu_msg)

    def cancel_var_input(self, user_id: int):
        """Cancel variable input"""
        return self._variable_handler.cancel_var_input(user_id)

    async def save_variable_skip_desc(self, user_id: int, message):
        """Save variable without description"""
        return await self._variable_handler.save_variable_skip_desc(user_id, message)

    # Plan Approval State - delegate to plan handler
    async def handle_plan_response(self, user_id: int, response: str) -> bool:
        """Handle plan approval response"""
        return await self._plan_handler.handle_plan_response(user_id, response)

    def set_expecting_plan_clarification(self, user_id: int, expecting: bool):
        """Set expecting plan clarification"""
        return self._plan_handler.set_expecting_plan_clarification(user_id, expecting)

    # Message Handlers - delegate to appropriate handlers
    async def handle_document(self, message: Message, **kwargs) -> None:
        """Handle document messages"""
        return await self._file_handler.handle_document(message, **kwargs)

    async def handle_photo(self, message: Message, **kwargs) -> None:
        """Handle photo messages"""
        return await self._file_handler.handle_photo(message, **kwargs)

    async def handle_text(self, message: Message, **kwargs) -> None:
        """Handle text messages"""
        return await self._text_handler.handle_text(message, **kwargs)


def register_handlers(router: Router, handlers: MessageCoordinator) -> None:
    """Register message handlers with dispatcher"""
    from aiogram import F
    from aiogram.filters import StateFilter

    router.message.register(handlers.handle_document, F.document, StateFilter(None))
    router.message.register(handlers.handle_photo, F.photo, StateFilter(None))
    router.message.register(handlers.handle_text, F.text, StateFilter(None))
