"""
Message Handlers Package (Refactored)

This package contains the refactored message handlers that properly
integrate SDK service, message batching, and all other features.
"""

import logging
from typing import Optional

from .coordinator import MessageCoordinator
from .router import register_handlers

logger = logging.getLogger(__name__)


class MessageHandlers:
    """
    Refactored MessageHandlers using MessageCoordinator.

    This class provides the same interface as the original MessageHandlers
    but uses the refactored coordinator pattern internally.
    """

    def __init__(
        self,
        bot_service,
        claude_proxy,
        sdk_service=None,
        default_working_dir: str = "/root",
        project_service=None,
        context_service=None,
        file_processor_service=None,
        callback_handlers=None,
        # CRITICAL FIX: Accept shared state manager instances
        user_state_manager=None,
        hitl_manager=None,
        file_context_manager=None,
        variable_manager=None,
        plan_manager=None,
        message_batcher=None,
    ):
        """
        Initialize with original MessageHandlers signature.

        Args:
            bot_service: Bot service
            claude_proxy: Claude CLI proxy service
            sdk_service: Claude SDK service (optional)
            default_working_dir: Default working directory
            project_service: Project service (optional)
            context_service: Context service (optional)
            file_processor_service: File processor service (optional)
            callback_handlers: Callback handlers (optional)
            user_state_manager: Shared UserStateManager instance (optional)
            hitl_manager: Shared HITLManager instance (optional)
            file_context_manager: Shared FileContextManager instance (optional)
            variable_manager: Shared VariableInputManager instance (optional)
            plan_manager: Shared PlanApprovalManager instance (optional)
            message_batcher: Shared MessageBatcher instance (optional)
        """
        # Use SHARED instances if provided, otherwise create new
        if user_state_manager:
            self._state = user_state_manager
        else:
            from presentation.handlers.state.user_state import UserStateManager
            self._state = UserStateManager(default_working_dir)

        if hitl_manager:
            self._hitl = hitl_manager
        else:
            from presentation.handlers.state.hitl_manager import HITLManager
            self._hitl = HITLManager()

        if file_context_manager:
            self._file_context = file_context_manager
        else:
            from presentation.handlers.state.file_context import FileContextManager
            self._file_context = FileContextManager()

        if variable_manager:
            self._variables = variable_manager
        else:
            from presentation.handlers.state.variable_input import VariableInputManager
            self._variables = VariableInputManager()

        if plan_manager:
            self._plans = plan_manager
        else:
            from presentation.handlers.state.plan_manager import PlanApprovalManager
            self._plans = PlanApprovalManager()

        if message_batcher:
            self._batcher = message_batcher
        else:
            from presentation.middleware.message_batcher import MessageBatcher
            self._batcher = MessageBatcher()

        # Log whether using shared or new instances (for debugging)
        logger.info(
            f"MessageHandlers: using {'SHARED' if user_state_manager else 'NEW'} state managers "
            f"(state={id(self._state)}, hitl={id(self._hitl)})"
        )

        # Store references
        self.bot_service = bot_service
        self.claude_proxy = claude_proxy
        self.sdk_service = sdk_service
        self.project_service = project_service
        self.context_service = context_service
        self.file_processor_service = file_processor_service
        self.callback_handlers = callback_handlers

        # Determine backend
        self.use_sdk = sdk_service is not None
        logger.info(f"MessageHandlers (refactored) initialized with SDK: {self.use_sdk}")

        # Create coordinator with all dependencies
        self._coordinator = MessageCoordinator(
            bot_service=bot_service,
            user_state=self._state,
            hitl_manager=self._hitl,
            file_context_manager=self._file_context,
            variable_manager=self._variables,
            plan_manager=self._plans,
            file_processor_service=file_processor_service,
            context_service=context_service,
            project_service=project_service,
            sdk_service=sdk_service,
            claude_proxy=claude_proxy,
            message_batcher=self._batcher,
            callback_handlers=callback_handlers,
        )

    async def handle_text(
        self,
        message,
        prompt_override: Optional[str] = None,
        force_new_session: bool = False,
        _from_batcher: bool = False,
    ):
        """
        Handle text message - delegates to coordinator.

        This method provides backward compatibility with the original
        MessageHandlers.handle_text signature.
        """
        # Use the text handler directly to preserve the exact interface
        await self._coordinator._text_handler.handle_text_message(
            message,
            prompt_override=prompt_override,
            force_new_session=force_new_session,
            _from_batcher=_from_batcher,
        )

    async def handle_document(self, message):
        """Handle document message"""
        await self._coordinator._handle_document(message)

    async def handle_photo(self, message):
        """Handle photo message"""
        await self._coordinator._handle_photo(message)

    # === Delegation methods for compatibility ===

    def is_yolo_mode(self, user_id: int) -> bool:
        """Check if YOLO mode is enabled"""
        return self._coordinator.is_yolo_mode(user_id)

    def set_yolo_mode(self, user_id: int, enabled: bool) -> None:
        """Set YOLO mode"""
        self._coordinator.set_yolo_mode(user_id, enabled)

    def is_step_streaming_mode(self, user_id: int) -> bool:
        """Check if step streaming mode is enabled"""
        return self._coordinator.is_step_streaming_mode(user_id)

    def set_step_streaming_mode(self, user_id: int, enabled: bool) -> None:
        """Set step streaming mode"""
        self._coordinator.set_step_streaming_mode(user_id, enabled)

    def get_working_dir(self, user_id: int) -> str:
        """Get user's working directory"""
        return self._coordinator.get_working_dir(user_id)

    def set_working_dir(self, user_id: int, path: str) -> None:
        """Set user's working directory"""
        self._coordinator.set_working_dir(user_id, path)

    def cleanup(self, user_id: int) -> None:
        """Clean up all state for user"""
        self._coordinator.cleanup(user_id)


__all__ = [
    "MessageHandlers",
    "register_handlers",
]
