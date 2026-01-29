"""
Dependency Injection Container

Centralizes all dependency creation and wiring.
Follows Dependency Inversion Principle - high-level modules don't
depend on low-level modules, both depend on abstractions.

Usage:
    container = Container()
    await container.init()
    app = container.application()
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Application configuration from environment variables"""

    # Telegram
    telegram_token: str = ""

    # Claude Code
    claude_path: str = "claude"
    claude_working_dir: str = "/root"
    claude_max_turns: int = 50
    claude_timeout: int = 600
    claude_permission_mode: str = "default"
    claude_plugins_dir: str = "/plugins"
    claude_plugins: str = "commit-commands,code-review,feature-dev,frontend-design,ralph-loop"

    # Database
    database_url: str = "sqlite:///data/bot.db"

    # Admin
    admin_ids: list[int] = None  # List of admin user IDs

    # Logging
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables"""
        admin_ids_str = os.getenv("ADMIN_IDS", "664382290")
        admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

        return cls(
            telegram_token=os.getenv("TELEGRAM_TOKEN", ""),
            claude_path=os.getenv("CLAUDE_PATH", "claude"),
            claude_working_dir=os.getenv("CLAUDE_WORKING_DIR", "/root"),
            claude_max_turns=int(os.getenv("CLAUDE_MAX_TURNS", "50")),
            claude_timeout=int(os.getenv("CLAUDE_TIMEOUT", "600")),
            claude_permission_mode=os.getenv("CLAUDE_PERMISSION_MODE", "default"),
            claude_plugins_dir=os.getenv("CLAUDE_PLUGINS_DIR", "/plugins"),
            claude_plugins=os.getenv(
                "CLAUDE_PLUGINS",
                "commit-commands,code-review,feature-dev,frontend-design,ralph-loop"
            ),
            database_url=os.getenv("DATABASE_URL", "sqlite:///data/bot.db"),
            admin_ids=admin_ids,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


class Container:
    """
    Dependency Injection Container.

    Manages the lifecycle of all application services and their dependencies.
    Each service is created lazily and cached (singleton pattern).

    Benefits:
    - Easy to test (swap implementations)
    - Easy to change implementations (e.g., SQLite -> PostgreSQL)
    - Clear dependency graph
    - Single source of truth for configuration
    """

    def __init__(self, config: Config = None):
        self.config = config or Config.from_env()
        self._cache = {}

    # === Repository Layer ===

    def user_repository(self):
        """Get or create UserRepository"""
        if "user_repository" not in self._cache:
            from infrastructure.persistence.sqlite_repository import SQLiteUserRepository
            db_path = self.config.database_url.replace("sqlite:///", "")
            self._cache["user_repository"] = SQLiteUserRepository(db_path)
        return self._cache["user_repository"]

    def session_repository(self):
        """Get or create SessionRepository"""
        if "session_repository" not in self._cache:
            from infrastructure.persistence.sqlite_repository import SQLiteSessionRepository
            db_path = self.config.database_url.replace("sqlite:///", "")
            self._cache["session_repository"] = SQLiteSessionRepository(db_path)
        return self._cache["session_repository"]

    def command_repository(self):
        """Get or create CommandRepository"""
        if "command_repository" not in self._cache:
            from infrastructure.persistence.sqlite_repository import SQLiteCommandRepository
            db_path = self.config.database_url.replace("sqlite:///", "")
            self._cache["command_repository"] = SQLiteCommandRepository(db_path)
        return self._cache["command_repository"]

    def project_repository(self):
        """Get or create ProjectRepository"""
        if "project_repository" not in self._cache:
            from infrastructure.persistence.project_repository import SQLiteProjectRepository
            self._cache["project_repository"] = SQLiteProjectRepository()
        return self._cache["project_repository"]

    def context_repository(self):
        """Get or create ProjectContextRepository"""
        if "context_repository" not in self._cache:
            from infrastructure.persistence.project_context_repository import SQLiteProjectContextRepository
            self._cache["context_repository"] = SQLiteProjectContextRepository()
        return self._cache["context_repository"]

    def account_repository(self):
        """Get or create AccountRepository"""
        if "account_repository" not in self._cache:
            from infrastructure.persistence.sqlite_account_repository import SQLiteAccountRepository
            self._cache["account_repository"] = SQLiteAccountRepository()
        return self._cache["account_repository"]

    # === Service Layer ===

    def bot_service(self):
        """Get or create BotService"""
        if "bot_service" not in self._cache:
            from application.services.bot_service import BotService
            self._cache["bot_service"] = BotService(
                user_repository=self.user_repository(),
                session_repository=self.session_repository(),
                command_repository=self.command_repository(),
            )
        return self._cache["bot_service"]

    def account_service(self):
        """Get or create AccountService"""
        if "account_service" not in self._cache:
            from application.services.account_service import AccountService
            self._cache["account_service"] = AccountService(self.account_repository())
        return self._cache["account_service"]

    def project_service(self):
        """Get or create ProjectService"""
        if "project_service" not in self._cache:
            from application.services.project_service import ProjectService
            self._cache["project_service"] = ProjectService(
                self.project_repository(),
                self.context_repository()
            )
        return self._cache["project_service"]

    def context_service(self):
        """Get or create ContextService"""
        if "context_service" not in self._cache:
            from application.services.context_service import ContextService
            self._cache["context_service"] = ContextService(self.context_repository())
        return self._cache["context_service"]

    def file_browser_service(self):
        """Get or create FileBrowserService"""
        if "file_browser_service" not in self._cache:
            from application.services.file_browser_service import FileBrowserService
            self._cache["file_browser_service"] = FileBrowserService(
                root_path="/root/projects"
            )
        return self._cache["file_browser_service"]

    def file_processor_service(self):
        """Get or create FileProcessorService"""
        if "file_processor_service" not in self._cache:
            from application.services.file_processor_service import FileProcessorService
            self._cache["file_processor_service"] = FileProcessorService()
        return self._cache["file_processor_service"]

    # === Infrastructure Layer ===

    def claude_proxy(self):
        """Get or create ClaudeCodeProxyService (CLI backend)"""
        if "claude_proxy" not in self._cache:
            from infrastructure.claude_code.proxy_service import ClaudeCodeProxyService
            self._cache["claude_proxy"] = ClaudeCodeProxyService(
                claude_path=self.config.claude_path,
                default_working_dir=self.config.claude_working_dir,
                max_turns=self.config.claude_max_turns,
                timeout_seconds=self.config.claude_timeout,
            )
        return self._cache["claude_proxy"]

    def claude_sdk(self) -> Optional["ClaudeAgentSDKService"]:
        """Get or create ClaudeAgentSDKService (SDK backend)"""
        if "claude_sdk" not in self._cache:
            try:
                from infrastructure.claude_code.sdk_service import ClaudeAgentSDKService

                enabled_plugins = [
                    p.strip() for p in self.config.claude_plugins.split(",")
                    if p.strip()
                ]

                self._cache["claude_sdk"] = ClaudeAgentSDKService(
                    default_working_dir=self.config.claude_working_dir,
                    max_turns=self.config.claude_max_turns,
                    permission_mode=self.config.claude_permission_mode,
                    plugins_dir=self.config.claude_plugins_dir,
                    enabled_plugins=enabled_plugins,
                    account_service=self.account_service(),
                )
            except ImportError:
                logger.warning("Claude Agent SDK not available")
                self._cache["claude_sdk"] = None
        return self._cache["claude_sdk"]

    # === Initialization ===

    async def init(self) -> None:
        """Initialize all services that need async setup"""
        from infrastructure.persistence.sqlite_repository import init_database

        # Initialize database
        db_path = self.config.database_url.replace("sqlite:///", "")
        await init_database(db_path)

        # Initialize repositories that need async setup
        await self.account_repository().initialize()
        await self.project_repository().initialize()
        await self.context_repository().initialize()

        logger.info("Container initialized successfully")

    async def close(self) -> None:
        """Close all services that need cleanup"""
        # Add cleanup logic here if needed
        pass

    # === State Managers ===

    def user_state_manager(self):
        """Get or create UserStateManager"""
        if "user_state_manager" not in self._cache:
            from presentation.handlers.state.user_state import UserStateManager
            self._cache["user_state_manager"] = UserStateManager()
        return self._cache["user_state_manager"]

    def hitl_manager(self):
        """Get or create HITLManager"""
        if "hitl_manager" not in self._cache:
            from presentation.handlers.state.hitl_manager import HITLManager
            self._cache["hitl_manager"] = HITLManager()
        return self._cache["hitl_manager"]

    def file_context_manager(self):
        """Get or create FileContextManager"""
        if "file_context_manager" not in self._cache:
            from presentation.handlers.state.file_context import FileContextManager
            self._cache["file_context_manager"] = FileContextManager()
        return self._cache["file_context_manager"]

    def variable_manager(self):
        """Get or create VariableInputManager"""
        if "variable_manager" not in self._cache:
            from presentation.handlers.state.variable_input import VariableInputManager
            self._cache["variable_manager"] = VariableInputManager()
        return self._cache["variable_manager"]

    def plan_manager(self):
        """Get or create PlanApprovalManager"""
        if "plan_manager" not in self._cache:
            from presentation.handlers.state.plan_manager import PlanApprovalManager
            self._cache["plan_manager"] = PlanApprovalManager()
        return self._cache["plan_manager"]

    def message_batcher(self):
        """Get or create MessageBatcher"""
        if "message_batcher" not in self._cache:
            from presentation.middleware.message_batcher import MessageBatcher
            self._cache["message_batcher"] = MessageBatcher(batch_delay=0.5)
        return self._cache["message_batcher"]

    # === Factory Methods for Handlers ===

    def message_handlers(self):
        """Create MessageHandlers with all dependencies"""
        if "message_handlers" not in self._cache:
            # REFACTORED VERSION - using MessageHandlersFacade (backward compatible)
            from presentation.handlers.message import MessageHandlers
            self._cache["message_handlers"] = MessageHandlers(
                bot_service=self.bot_service(),
                user_state=self.user_state_manager(),
                hitl_manager=self.hitl_manager(),
                file_context_manager=self.file_context_manager(),
                variable_manager=self.variable_manager(),
                plan_manager=self.plan_manager(),
                file_processor_service=self.file_processor_service(),
                context_service=self.context_service(),
                project_service=self.project_service(),
                # Legacy parameters (for backward compatibility)
                claude_proxy=self.claude_proxy(),
                sdk_service=self.claude_sdk(),
            )
        return self._cache["message_handlers"]

    def command_handlers(self):
        """Create CommandHandlers with all dependencies"""
        if "command_handlers" not in self._cache:
            from presentation.handlers.commands import CommandHandlers
            handlers = CommandHandlers(
                bot_service=self.bot_service(),
                claude_proxy=self.claude_proxy(),
                project_service=self.project_service(),
                context_service=self.context_service(),
                file_browser_service=self.file_browser_service(),
            )
            handlers.message_handlers = self.message_handlers()
            self._cache["command_handlers"] = handlers
        return self._cache["command_handlers"]

    def callback_handlers(self):
        """Create CallbackHandlers with all dependencies"""
        if "callback_handlers" not in self._cache:
            from presentation.handlers.callbacks import CallbackHandlers
            msg_handlers = self.message_handlers()
            self._cache["callback_handlers"] = CallbackHandlers(
                bot_service=self.bot_service(),
                message_handlers=msg_handlers,
                claude_proxy=self.claude_proxy(),
                sdk_service=self.claude_sdk(),
                project_service=self.project_service(),
                context_service=self.context_service(),
                file_browser_service=self.file_browser_service(),
            )
            # Establish bidirectional link for gvar input handling
            msg_handlers.callback_handlers = self._cache["callback_handlers"]
        return self._cache["callback_handlers"]

    def account_handlers(self):
        """Create AccountHandlers with all dependencies"""
        if "account_handlers" not in self._cache:
            from presentation.handlers.account_handlers import AccountHandlers
            handlers = AccountHandlers(
                account_service=self.account_service(),
                context_service=self.context_service(),
                project_service=self.project_service(),
            )
            handlers.message_handlers = self.message_handlers()
            self._cache["account_handlers"] = handlers
        return self._cache["account_handlers"]

    def menu_handlers(self):
        """Create MenuHandlers with all dependencies"""
        if "menu_handlers" not in self._cache:
            from presentation.handlers.menu_handlers import MenuHandlers
            self._cache["menu_handlers"] = MenuHandlers(
                bot_service=self.bot_service(),
                claude_proxy=self.claude_proxy(),
                sdk_service=self.claude_sdk(),
                project_service=self.project_service(),
                context_service=self.context_service(),
                file_browser_service=self.file_browser_service(),
                account_service=self.account_service(),
                message_handlers=self.message_handlers(),
            )
        return self._cache["menu_handlers"]
