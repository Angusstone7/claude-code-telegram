"""Base handler with common functionality"""

import logging
from typing import TYPE_CHECKING

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


class BaseMessageHandler:
    """Base class for all message handlers"""

    def __init__(
        self,
        bot_service: "BotService",
        user_state: "UserStateManager",
        hitl_manager: "HITLManager",
        file_context_manager: "FileContextManager",
        variable_manager: "VariableInputManager",
        plan_manager: "PlanApprovalManager",
    ):
        self.bot_service = bot_service
        self.user_state = user_state
        self.hitl_manager = hitl_manager
        self.file_context_manager = file_context_manager
        self.variable_manager = variable_manager
        self.plan_manager = plan_manager

    # Common utilities will be added here if needed
