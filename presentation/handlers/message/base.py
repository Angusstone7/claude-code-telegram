"""
Base Message Handler

Provides shared dependencies and utilities for all message handlers.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from application.services.bot_service import BotService
    from presentation.handlers.state.user_state import UserStateManager
    from presentation.handlers.state.hitl_manager import HITLManager
    from presentation.handlers.state.file_context_manager import FileContextManager
    from presentation.handlers.state.variable_manager import VariableManager
    from presentation.handlers.state.plan_manager import PlanManager

logger = logging.getLogger(__name__)


class BaseMessageHandler:
    """
    Base class for all message handlers.

    Provides shared dependencies and common utilities.
    All specialized handlers inherit from this class.
    """

    def __init__(
        self,
        bot_service: "BotService",
        user_state: "UserStateManager",
        hitl_manager: "HITLManager",
        file_context_manager: "FileContextManager",
        variable_manager: "VariableManager",
        plan_manager: "PlanManager",
    ):
        """
        Initialize base handler with shared dependencies.

        Args:
            bot_service: Bot service for AI interactions
            user_state: User state manager
            hitl_manager: Human-in-the-loop manager
            file_context_manager: File context manager
            variable_manager: Variable manager
            plan_manager: Plan manager
        """
        self.bot_service = bot_service
        self.user_state = user_state
        self.hitl_manager = hitl_manager
        self.file_context = file_context_manager
        self.variables = variable_manager
        self.plans = plan_manager
        self._logger = logger

    def log_debug(self, user_id: int, message: str) -> None:
        """Log debug message with user context"""
        self._logger.debug(f"[{user_id}] {message}")

    def log_info(self, user_id: int, message: str) -> None:
        """Log info message with user context"""
        self._logger.info(f"[{user_id}] {message}")

    def log_warning(self, user_id: int, message: str) -> None:
        """Log warning message with user context"""
        self._logger.warning(f"[{user_id}] {message}")

    def log_error(self, user_id: int, message: str, exc_info: bool = False) -> None:
        """Log error message with user context"""
        self._logger.error(f"[{user_id}] {message}", exc_info=exc_info)

    def get_working_dir(self, user_id: int) -> str:
        """Get user's current working directory"""
        return self.user_state.get_working_dir(user_id)

    def is_yolo_mode(self, user_id: int) -> bool:
        """Check if YOLO mode (auto-approve) is enabled"""
        return self.user_state.is_yolo_mode(user_id)
