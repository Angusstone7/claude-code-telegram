#!/usr/bin/env python3
"""
Claude Code Telegram Proxy - Control Claude Code via Telegram

This bot acts as a proxy to Claude Code CLI, forwarding:
- User prompts to Claude Code
- Claude Code output back to Telegram
- HITL (Human-in-the-Loop) requests for approval/questions

Architecture:
- Domain: Business entities and logic
- Application: Use cases and orchestration
- Infrastructure: External dependencies (Claude Code CLI, DB)
- Presentation: Telegram bot interface
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand

from shared.config.settings import settings
from infrastructure.persistence.sqlite_repository import (
    init_database,
    SQLiteUserRepository,
    SQLiteSessionRepository,
    SQLiteCommandRepository
)
from infrastructure.persistence.project_repository import SQLiteProjectRepository
from infrastructure.persistence.project_context_repository import SQLiteProjectContextRepository
from infrastructure.persistence.sqlite_account_repository import SQLiteAccountRepository
from application.services.project_service import ProjectService
from application.services.context_service import ContextService
from application.services.file_browser_service import FileBrowserService
from application.services.account_service import AccountService
from infrastructure.claude_code.proxy_service import ClaudeCodeProxyService
from infrastructure.claude_code.diagnostics import run_and_log_diagnostics

# Try to import SDK service (optional, preferred when available)
try:
    from infrastructure.claude_code.sdk_service import ClaudeAgentSDKService
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    ClaudeAgentSDKService = None
from application.services.bot_service import BotService
from presentation.handlers.commands import CommandHandlers, register_handlers as register_cmd_handlers
from presentation.handlers.messages import MessageHandlers, register_handlers as register_msg_handlers
from presentation.handlers.callbacks import CallbackHandlers, register_handlers as register_callback_handlers
from presentation.handlers.account_handlers import AccountHandlers, register_account_handlers
from presentation.handlers.menu_handlers import MenuHandlers, register_menu_handlers
from presentation.middleware.auth import AuthMiddleware, CallbackAuthMiddleware

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot.log")
    ]
)

logger = logging.getLogger(__name__)


class Application:
    """Main application class"""

    def __init__(self):
        self.bot: Bot = None
        self.dp: Dispatcher = None
        self.bot_service: BotService = None
        self.claude_proxy: ClaudeCodeProxyService = None
        self.claude_sdk: "ClaudeAgentSDKService" = None  # SDK service (preferred)
        self.project_service: ProjectService = None
        self.context_service: ContextService = None
        self.file_browser_service: FileBrowserService = None
        self.account_service: AccountService = None  # Account mode switching
        self._shutdown_event = asyncio.Event()

    async def setup(self):
        """Initialize application components"""
        logger.info("Initializing Claude Code Telegram Proxy...")

        # Ensure directories exist
        Path("logs").mkdir(exist_ok=True)
        Path("data").mkdir(exist_ok=True)

        # Initialize database
        logger.info("Initializing database...")
        await init_database()

        # Initialize repositories
        user_repo = SQLiteUserRepository()
        session_repo = SQLiteSessionRepository()
        command_repo = SQLiteCommandRepository()

        # Initialize Account Service (for auth mode switching)
        logger.info("Initializing account service...")
        account_repo = SQLiteAccountRepository()
        await account_repo.initialize()
        self.account_service = AccountService(account_repo)
        logger.info("✓ Account service initialized")

        # Initialize Claude Code proxy
        default_working_dir = os.getenv("CLAUDE_WORKING_DIR", "/root")
        self.claude_proxy = ClaudeCodeProxyService(
            claude_path=os.getenv("CLAUDE_PATH", "claude"),
            default_working_dir=default_working_dir,
            max_turns=int(os.getenv("CLAUDE_MAX_TURNS", "50")),
            timeout_seconds=int(os.getenv("CLAUDE_TIMEOUT", "600")),
        )

        # Check if Claude Code CLI is installed (fallback)
        installed, message = await self.claude_proxy.check_claude_installed()
        if installed:
            logger.info(f"✓ CLI: {message}")
            # Run full diagnostics
            logger.info("Running Claude Code diagnostics...")
            await run_and_log_diagnostics(self.claude_proxy.claude_path)
        else:
            logger.warning(f"⚠ CLI: {message}")
            logger.warning("Bot will start but CLI fallback will fail until installed")

        # Initialize SDK service (preferred backend for HITL)
        if SDK_AVAILABLE:
            try:
                # Configure plugins from official anthropic repo
                plugins_dir = os.getenv("CLAUDE_PLUGINS_DIR", "/plugins")
                enabled_plugins_str = os.getenv(
                    "CLAUDE_PLUGINS",
                    "commit-commands,code-review,feature-dev,frontend-design,ralph-loop"
                )
                enabled_plugins = [p.strip() for p in enabled_plugins_str.split(",") if p.strip()]

                self.claude_sdk = ClaudeAgentSDKService(
                    default_working_dir=default_working_dir,
                    max_turns=int(os.getenv("CLAUDE_MAX_TURNS", "50")),
                    permission_mode=os.getenv("CLAUDE_PERMISSION_MODE", "default"),
                    plugins_dir=plugins_dir,
                    enabled_plugins=enabled_plugins,
                    account_service=self.account_service,
                )
                sdk_ok, sdk_msg = await self.claude_sdk.check_sdk_available()
                if sdk_ok:
                    logger.info(f"✓ SDK: {sdk_msg}")
                    # Log enabled plugins
                    plugins_info = self.claude_sdk.get_enabled_plugins_info()
                    available_plugins = [p["name"] for p in plugins_info if p.get("available")]
                    if available_plugins:
                        logger.info(f"✓ Плагины: {', '.join(available_plugins)}")
                    else:
                        logger.warning("⚠ Плагины настроены, но не найдены в директории")
                else:
                    logger.warning(f"⚠ SDK: {sdk_msg}")
                    self.claude_sdk = None
            except Exception as e:
                logger.warning(f"⚠ SDK initialization failed: {e}")
                self.claude_sdk = None
        else:
            logger.info("ℹ SDK not available, using CLI-only mode")
            self.claude_sdk = None

        # Initialize bot service (for auth and legacy features)
        self.bot_service = BotService(
            user_repository=user_repo,
            session_repository=session_repo,
            command_repository=command_repo,
        )

        # Initialize project/context repositories and services
        logger.info("Initializing project management...")
        project_repo = SQLiteProjectRepository()
        context_repo = SQLiteProjectContextRepository()

        # Initialize database tables for projects
        await project_repo.initialize()
        await context_repo.initialize()

        self.project_service = ProjectService(project_repo, context_repo)
        self.context_service = ContextService(context_repo)
        self.file_browser_service = FileBrowserService(root_path="/root/projects")
        logger.info("✓ Project management initialized")

        # Initialize bot
        self.bot = Bot(
            token=settings.telegram.token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        self.dp = Dispatcher()

        # Register handlers
        self._register_handlers()

        # Register middleware
        self.dp.message.middleware(AuthMiddleware(self.bot_service))
        self.dp.callback_query.middleware(CallbackAuthMiddleware(self.bot_service))

        # Register bot commands in Telegram menu
        await self._register_bot_commands()

        logger.info("Bot initialized successfully")
        logger.info(f"Default working directory: {default_working_dir}")

    def _register_handlers(self):
        """Register all handlers"""
        # Account handlers (for /account command and mode switching)
        account_handlers = AccountHandlers(
            self.account_service,
            context_service=self.context_service  # For session reset on model change
        )
        register_account_handlers(self.dp, account_handlers)

        # Message handlers (with SDK service preferred, CLI as fallback)
        msg_handlers = MessageHandlers(
            self.bot_service,
            self.claude_proxy,
            sdk_service=self.claude_sdk,  # Pass SDK service for proper HITL
            project_service=self.project_service,
            context_service=self.context_service
        )

        # Link message_handlers to account_handlers for session cache clear
        account_handlers.message_handlers = msg_handlers

        # Command handlers (with claude_proxy and project/context services)
        cmd_handlers = CommandHandlers(
            self.bot_service,
            self.claude_proxy,
            project_service=self.project_service,
            context_service=self.context_service,
            file_browser_service=self.file_browser_service
        )
        cmd_handlers.message_handlers = msg_handlers  # Link for /project, /status commands
        register_cmd_handlers(self.dp, cmd_handlers)

        # Menu handlers - main inline menu system
        menu_handlers = MenuHandlers(
            bot_service=self.bot_service,
            claude_proxy=self.claude_proxy,
            sdk_service=self.claude_sdk,
            project_service=self.project_service,
            context_service=self.context_service,
            file_browser_service=self.file_browser_service,
            account_service=self.account_service,
            message_handlers=msg_handlers,
        )
        register_menu_handlers(self.dp, menu_handlers)

        # Register message handlers after commands (commands take priority)
        register_msg_handlers(self.dp, msg_handlers)

        # Callback handlers (with claude_proxy, sdk_service and project/context services for HITL)
        callback_handlers = CallbackHandlers(
            self.bot_service,
            msg_handlers,
            self.claude_proxy,
            self.claude_sdk,  # SDK service for proper cancellation
            self.project_service,
            self.context_service,
            self.file_browser_service
        )
        register_callback_handlers(self.dp, callback_handlers)

    async def _register_bot_commands(self):
        """Register bot commands in Telegram menu"""
        # Only register essential commands - all functionality is in inline menu
        commands = [
            BotCommand(command="start", description="📱 Открыть меню"),
            BotCommand(command="cancel", description="🛑 Отменить задачу"),
        ]

        try:
            await self.bot.set_my_commands(commands)
            logger.info(f"✓ Registered {len(commands)} bot commands in Telegram menu")
        except Exception as e:
            logger.warning(f"⚠ Failed to register bot commands: {e}")

    async def _notify_admin_startup(self, bot_info):
        """Notify admin that bot has started successfully"""
        admin_id = 664382290

        # Build status message
        sdk_status = "✅ SDK" if self.claude_sdk else "❌ SDK"
        cli_ok, _ = await self.claude_proxy.check_claude_installed()
        cli_status = "✅ CLI" if cli_ok else "❌ CLI"

        # Get credentials info
        creds_info = self.account_service.get_credentials_info()
        creds_status = (
            f"✅ {creds_info.subscription_type}" if creds_info.exists
            else "❌ не найден"
        )

        message = (
            f"🚀 <b>Бот запущен!</b>\n\n"
            f"🤖 @{bot_info.username}\n"
            f"📦 {sdk_status} | {cli_status}\n"
            f"☁️ Claude creds: {creds_status}\n"
            f"📁 {os.getenv('CLAUDE_WORKING_DIR', '/root')}\n\n"
            f"<i>Готов к работе</i>"
        )

        try:
            await self.bot.send_message(admin_id, message)
            logger.info(f"✓ Admin {admin_id} notified about startup")
        except Exception as e:
            logger.warning(f"⚠ Failed to notify admin: {e}")

    async def start(self):
        """Start the bot"""
        await self.setup()

        logger.info("Starting bot polling...")
        info = await self.bot.get_me()
        logger.info(f"Bot: @{info.username} (ID: {info.id})")

        # Notify admin that bot started
        await self._notify_admin_startup(info)

        # Set up signal handlers (Unix only)
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

        # Start polling
        await self.dp.start_polling(
            self.bot,
            handle_signals=sys.platform == "win32"  # Let aiogram handle signals on Windows
        )

    async def shutdown(self):
        """Graceful shutdown"""
        if self._shutdown_event.is_set():
            return

        logger.info("Shutting down...")
        self._shutdown_event.set()

        # Stop polling
        if self.dp:
            await self.dp.stop_polling()

        # Close bot session
        if self.bot:
            await self.bot.session.close()

        logger.info("Shutdown complete")


async def main():
    """Main entry point"""
    app = Application()

    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
