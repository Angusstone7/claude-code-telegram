"""
MessageHandlers Facade - Backward Compatibility Layer

This facade provides backward compatibility with the old MessageHandlers class.
It delegates all calls to the new MessageCoordinator and specialized handlers.

Usage:
    # Old code (still works):
    from presentation.handlers.messages import MessageHandlers
    handlers = MessageHandlers(...)
    await handlers.handle_text(message)

    # New code (recommended):
    from presentation.handlers.message import MessageCoordinator
    coordinator = MessageCoordinator(...)
    await coordinator.handle_message(message)
"""

import logging
from typing import TYPE_CHECKING, Optional
from aiogram.types import Message

from .coordinator import MessageCoordinator

if TYPE_CHECKING:
    from application.services.bot_service import BotService
    from presentation.handlers.state.user_state import UserStateManager
    from presentation.handlers.state.hitl_manager import HITLManager
    from presentation.handlers.state.file_context_manager import FileContextManager
    from presentation.handlers.state.variable_manager import VariableManager
    from presentation.handlers.state.plan_manager import PlanManager

logger = logging.getLogger(__name__)


class MessageHandlersFacade:
    """
    Backward compatibility facade for old MessageHandlers class.

    This class provides the same interface as the old God Object,
    but delegates all calls to the new MessageCoordinator.

    DEPRECATED: Use MessageCoordinator directly for new code.
    """

    def __init__(
        self,
        bot_service: "BotService",
        user_state: Optional["UserStateManager"] = None,
        hitl_manager: Optional["HITLManager"] = None,
        file_context_manager: Optional["FileContextManager"] = None,
        variable_manager: Optional["VariableManager"] = None,
        plan_manager: Optional["PlanManager"] = None,
        file_processor_service=None,
        context_service=None,
        project_service=None,
        # Legacy parameters (ignored)
        use_sdk: bool = True,
        sdk_service=None,
        claude_proxy=None,
        **kwargs  # Catch any other legacy parameters
    ):
        """
        Initialize facade with same signature as old MessageHandlers.

        Args:
            bot_service: Bot service
            user_state: User state manager
            hitl_manager: HITL manager
            file_context_manager: File context manager
            variable_manager: Variable manager
            plan_manager: Plan manager
            file_processor_service: File processor service
            context_service: Context service
            project_service: Project service
            use_sdk: DEPRECATED - ignored
            sdk_service: DEPRECATED - ignored
            claude_proxy: DEPRECATED - ignored
            **kwargs: Other legacy parameters (ignored)
        """
        logger.warning(
            "⚠️  MessageHandlersFacade is DEPRECATED. "
            "Use MessageCoordinator directly for new code."
        )

        # Create managers if not provided (for backward compatibility)
        if user_state is None:
            from presentation.handlers.state.user_state import UserStateManager
            user_state = UserStateManager()

        if hitl_manager is None:
            from presentation.handlers.state.hitl_manager import HITLManager
            hitl_manager = HITLManager()

        if file_context_manager is None:
            from presentation.handlers.state.file_context_manager import FileContextManager
            file_context_manager = FileContextManager()

        if variable_manager is None:
            from presentation.handlers.state.variable_manager import VariableManager
            variable_manager = VariableManager()

        if plan_manager is None:
            from presentation.handlers.state.plan_manager import PlanManager
            plan_manager = PlanManager()

        # Initialize new coordinator
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
        )

        # Store references for compatibility
        self.bot_service = bot_service
        self.use_sdk = use_sdk
        self.sdk_service = sdk_service
        self.claude_proxy = claude_proxy

        logger.info("MessageHandlersFacade initialized (delegating to MessageCoordinator)")

    # === Main message handlers (delegate to coordinator) ===

    async def handle_text(self, message: Message, **kwargs) -> None:
        """Handle text message - delegates to coordinator"""
        await self._coordinator.handle_message(message)

    async def handle_document(self, message: Message) -> None:
        """Handle document - delegates to coordinator"""
        await self._coordinator.handle_message(message)

    async def handle_photo(self, message: Message) -> None:
        """Handle photo - delegates to coordinator"""
        await self._coordinator.handle_message(message)

    # === State getters/setters (delegate to coordinator) ===

    def is_yolo_mode(self, user_id: int) -> bool:
        """Check YOLO mode"""
        return self._coordinator.is_yolo_mode(user_id)

    def set_yolo_mode(self, user_id: int, enabled: bool) -> None:
        """Set YOLO mode"""
        self._coordinator.set_yolo_mode(user_id, enabled)

    def is_step_streaming_mode(self, user_id: int) -> bool:
        """Check step streaming mode"""
        return self._coordinator.is_step_streaming_mode(user_id)

    def set_step_streaming_mode(self, user_id: int, enabled: bool) -> None:
        """Set step streaming mode"""
        self._coordinator.set_step_streaming_mode(user_id, enabled)

    def get_working_dir(self, user_id: int) -> str:
        """Get working directory"""
        return self._coordinator.get_working_dir(user_id)

    def set_working_dir(self, user_id: int, path: str) -> None:
        """Set working directory"""
        self._coordinator.set_working_dir(user_id, path)

    def cleanup(self, user_id: int) -> None:
        """Clean up state"""
        self._coordinator.cleanup(user_id)

    # === Variable methods (delegate to variable handler) ===

    def is_expecting_var_input(self, user_id: int) -> bool:
        """Check if expecting variable input"""
        return self._coordinator._variable_handler.is_expecting_input(user_id)

    def start_var_input(self, user_id: int, menu_msg: Optional[Message] = None) -> None:
        """Start variable input"""
        self._coordinator._variable_handler.start_var_input(user_id, menu_msg)

    def start_var_edit(self, user_id: int, var_name: str, menu_msg: Optional[Message] = None) -> None:
        """Start variable edit"""
        self._coordinator._variable_handler.start_var_edit(user_id, var_name, menu_msg)

    def cancel_var_input(self, user_id: int) -> None:
        """Cancel variable input"""
        self._coordinator._variable_handler.cancel_var_input(user_id)

    # === Plan methods (delegate to plan handler) ===

    def set_expecting_plan_clarification(self, user_id: int, expecting: bool) -> None:
        """Set plan clarification expectation"""
        self._coordinator._plan_handler.set_expecting_clarification(user_id, expecting)

    # === HITL methods (delegate to HITL handler) ===

    def set_expecting_answer(self, user_id: int, expecting: bool) -> None:
        """Set expecting answer"""
        self._coordinator._hitl_manager.set_expecting_answer(user_id, expecting)

    def set_expecting_path(self, user_id: int, expecting: bool) -> None:
        """Set expecting path"""
        self._coordinator._hitl_manager.set_expecting_path(user_id, expecting)

    # === Backward compatibility methods that may not work ===

    def _is_task_running(self, user_id: int) -> bool:
        """
        Check if task is running.

        NOTE: This requires integration with SDK service or claude_proxy.
        Returns False for now (TODO: implement).
        """
        # TODO: Implement proper task status check
        return False

    async def get_project_working_dir(self, user_id: int) -> str:
        """
        Get project working directory.

        NOTE: This is a legacy method that may not work correctly.
        Use get_working_dir() instead.
        """
        logger.warning("get_project_working_dir is deprecated, use get_working_dir instead")
        return self.get_working_dir(user_id)
