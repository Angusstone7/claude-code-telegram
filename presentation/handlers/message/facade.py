"""Backward compatibility facade - delegates to MessageCoordinator"""

import logging
from typing import TYPE_CHECKING, Optional

from aiogram.types import Message

from .coordinator import MessageCoordinator

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


class MessageHandlersFacade:
    """
    Backward compatibility facade for old MessageHandlers class.

    This facade maintains the EXACT same interface as legacy MessageHandlers,
    but delegates all calls to the new modular MessageCoordinator.
    """

    def __init__(
        self,
        bot_service,
        claude_proxy: "ClaudeCodeProxyService",
        sdk_service: Optional["ClaudeAgentSDKService"] = None,
        default_working_dir: str = "/root",
        project_service=None,
        context_service=None,
        file_processor_service: Optional["FileProcessorService"] = None,
        user_state: Optional["UserStateManager"] = None,
        hitl_manager: Optional["HITLManager"] = None,
        file_context_manager: Optional["FileContextManager"] = None,
        variable_manager: Optional["VariableInputManager"] = None,
        plan_manager: Optional["PlanApprovalManager"] = None,
        runtime_config=None,
        **kwargs  # Catch any other legacy parameters
    ):
        """
        Initialize facade with SAME signature as legacy MessageHandlers.

        Accepts both old-style (no managers) and new-style (with managers) parameters.
        """
        # Import managers if not provided (backward compat)
        if user_state is None:
            from presentation.handlers.state.user_state import UserStateManager
            user_state = UserStateManager(default_working_dir)

        if hitl_manager is None:
            from presentation.handlers.state.hitl_manager import HITLManager
            hitl_manager = HITLManager()

        if file_context_manager is None:
            from presentation.handlers.state.file_context import FileContextManager
            file_context_manager = FileContextManager()

        if variable_manager is None:
            from presentation.handlers.state.variable_input import VariableInputManager
            variable_manager = VariableInputManager()

        if plan_manager is None:
            from presentation.handlers.state.plan_manager import PlanApprovalManager
            plan_manager = PlanApprovalManager()

        # Try to import and create message batcher
        try:
            from presentation.middleware.message_batcher import MessageBatcher
            message_batcher = MessageBatcher(batch_delay=0.5)
        except ImportError:
            message_batcher = None

        # Initialize coordinator with ALL parameters
        self._coordinator = MessageCoordinator(
            bot_service=bot_service,
            user_state=user_state,
            hitl_manager=hitl_manager,
            file_context_manager=file_context_manager,
            variable_manager=variable_manager,
            plan_manager=plan_manager,
            file_processor_service=file_processor_service,
            context_service=context_service,
            project_service=project_service,
            sdk_service=sdk_service,
            claude_proxy=claude_proxy,
            default_working_dir=default_working_dir,
            message_batcher=message_batcher,
            callback_handlers=None,  # Will be set by container
            runtime_config=runtime_config,
        )

        # Store references for compatibility (legacy code might access these)
        self.bot_service = bot_service
        self.claude_proxy = claude_proxy
        self.sdk_service = sdk_service
        self.project_service = project_service
        self.context_service = context_service
        self.default_working_dir = default_working_dir

        # Determine which backend to use
        self.use_sdk = sdk_service is not None

        # Store managers for compatibility
        self._state = user_state
        self._hitl = hitl_manager
        self._variables = variable_manager
        self._plans = plan_manager
        self._files = file_context_manager

        # Callback handlers (bidirectional link from container)
        self._callback_handlers = None

    @property
    def callback_handlers(self):
        """Get callback handlers"""
        return self._callback_handlers

    @callback_handlers.setter
    def callback_handlers(self, value):
        """Set callback handlers and propagate to coordinator and text_handler"""
        self._callback_handlers = value
        # Propagate to coordinator
        if hasattr(self._coordinator, '_callback_handlers'):
            self._coordinator._callback_handlers = value
        # Propagate to text_handler inside coordinator
        if hasattr(self._coordinator, '_text_handler') and self._coordinator._text_handler:
            self._coordinator._text_handler.callback_handlers = value
        logger.debug(f"callback_handlers set and propagated: {value is not None}")

    # === Delegate ALL methods from legacy MessageHandlers ===

    async def handle_text(self, message: Message, **kwargs) -> None:
        """Handle text message - delegates to coordinator"""
        return await self._coordinator.handle_text(message, **kwargs)

    async def handle_document(self, message: Message, **kwargs) -> None:
        """Handle document - delegates to coordinator"""
        return await self._coordinator.handle_document(message, **kwargs)

    async def handle_photo(self, message: Message, **kwargs) -> None:
        """Handle photo - delegates to coordinator"""
        return await self._coordinator.handle_photo(message, **kwargs)

    def is_yolo_mode(self, user_id: int) -> bool:
        """Check YOLO mode - delegates to coordinator"""
        return self._coordinator.is_yolo_mode(user_id)

    async def load_yolo_mode(self, user_id: int) -> bool:
        """Load YOLO mode from DB if not already loaded - delegates to coordinator"""
        return await self._coordinator.load_yolo_mode(user_id)

    def set_yolo_mode(self, user_id: int, enabled: bool):
        """Set YOLO mode - delegates to coordinator"""
        return self._coordinator.set_yolo_mode(user_id, enabled)

    def is_step_streaming_mode(self, user_id: int) -> bool:
        """Check step streaming mode - delegates to coordinator"""
        return self._coordinator.is_step_streaming_mode(user_id)

    def set_step_streaming_mode(self, user_id: int, enabled: bool):
        """Set step streaming mode - delegates to coordinator"""
        return self._coordinator.set_step_streaming_mode(user_id, enabled)

    def get_working_dir(self, user_id: int) -> str:
        """Get working dir - delegates to coordinator"""
        return self._coordinator.get_working_dir(user_id)

    async def get_project_working_dir(self, user_id: int) -> str:
        """Get project working dir - delegates to coordinator"""
        return await self._coordinator.get_project_working_dir(user_id)

    def set_working_dir(self, user_id: int, path: str):
        """Set working dir - delegates to coordinator"""
        return self._coordinator.set_working_dir(user_id, path)

    def clear_session_cache(self, user_id: int) -> None:
        """Clear session cache - delegates to coordinator"""
        return self._coordinator.clear_session_cache(user_id)

    def set_continue_session(self, user_id: int, session_id: str):
        """Set continue session - delegates to coordinator"""
        return self._coordinator.set_continue_session(user_id, session_id)

    def set_expecting_answer(self, user_id: int, expecting: bool):
        """Set expecting answer - delegates to coordinator"""
        return self._coordinator.set_expecting_answer(user_id, expecting)

    def set_expecting_path(self, user_id: int, expecting: bool):
        """Set expecting path - delegates to coordinator"""
        return self._coordinator.set_expecting_path(user_id, expecting)

    def get_pending_question_option(self, user_id: int, index: int) -> str:
        """Get pending question option - delegates to coordinator"""
        return self._coordinator.get_pending_question_option(user_id, index)

    async def handle_permission_response(self, user_id: int, approved: bool, clarification_text: str = None) -> bool:
        """Handle permission response - delegates to coordinator"""
        return await self._coordinator.handle_permission_response(user_id, approved, clarification_text)

    async def handle_question_response(self, user_id: int, answer: str):
        """Handle question response - delegates to coordinator"""
        return await self._coordinator.handle_question_response(user_id, answer)

    def is_expecting_var_input(self, user_id: int) -> bool:
        """Check expecting var input - delegates to coordinator"""
        return self._coordinator.is_expecting_var_input(user_id)

    def set_expecting_var_name(self, user_id: int, expecting: bool, menu_msg=None):
        """Set expecting var name - delegates to coordinator"""
        return self._coordinator.set_expecting_var_name(user_id, expecting, menu_msg)

    def set_expecting_var_value(self, user_id: int, var_name: str, menu_msg=None):
        """Set expecting var value - delegates to coordinator"""
        return self._coordinator.set_expecting_var_value(user_id, var_name, menu_msg)

    def set_expecting_var_desc(self, user_id: int, var_name: str, var_value: str, menu_msg=None):
        """Set expecting var desc - delegates to coordinator"""
        return self._coordinator.set_expecting_var_desc(user_id, var_name, var_value, menu_msg)

    def clear_var_state(self, user_id: int):
        """Clear var state - delegates to coordinator"""
        return self._coordinator.clear_var_state(user_id)

    def get_pending_var_message(self, user_id: int):
        """Get pending var message - delegates to coordinator"""
        return self._coordinator.get_pending_var_message(user_id)

    def start_var_input(self, user_id: int, menu_msg=None):
        """Start var input - delegates to coordinator"""
        return self._coordinator.start_var_input(user_id, menu_msg)

    def start_var_edit(self, user_id: int, var_name: str, menu_msg=None):
        """Start var edit - delegates to coordinator"""
        return self._coordinator.start_var_edit(user_id, var_name, menu_msg)

    def cancel_var_input(self, user_id: int):
        """Cancel var input - delegates to coordinator"""
        return self._coordinator.cancel_var_input(user_id)

    async def save_variable_skip_desc(self, user_id: int, message):
        """Save variable skip desc - delegates to coordinator"""
        return await self._coordinator.save_variable_skip_desc(user_id, message)

    async def handle_plan_response(self, user_id: int, response: str) -> bool:
        """Handle plan response - delegates to coordinator"""
        return await self._coordinator.handle_plan_response(user_id, response)

    def set_expecting_plan_clarification(self, user_id: int, expecting: bool):
        """Set expecting plan clarification - delegates to coordinator"""
        return self._coordinator.set_expecting_plan_clarification(user_id, expecting)


# Backward compatibility alias
MessageHandlers = MessageHandlersFacade
