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

from shared.config.settings import settings
from infrastructure.persistence.sqlite_repository import (
    init_database,
    SQLiteUserRepository,
    SQLiteSessionRepository,
    SQLiteCommandRepository
)
from infrastructure.claude_code.proxy_service import ClaudeCodeProxyService
from application.services.bot_service import BotService
from presentation.handlers.commands import CommandHandlers, register_handlers as register_cmd_handlers
from presentation.handlers.messages import MessageHandlers, register_handlers as register_msg_handlers
from presentation.handlers.callbacks import CallbackHandlers, register_handlers as register_callback_handlers
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

        # Initialize Claude Code proxy
        default_working_dir = os.getenv("CLAUDE_WORKING_DIR", "/root")
        self.claude_proxy = ClaudeCodeProxyService(
            claude_path=os.getenv("CLAUDE_PATH", "claude"),
            default_working_dir=default_working_dir,
            max_turns=int(os.getenv("CLAUDE_MAX_TURNS", "50")),
            timeout_seconds=int(os.getenv("CLAUDE_TIMEOUT", "600")),
        )

        # Check if Claude Code is installed
        installed, message = await self.claude_proxy.check_claude_installed()
        if installed:
            logger.info(f"✓ {message}")
        else:
            logger.warning(f"⚠ {message}")
            logger.warning("Bot will start but Claude Code commands will fail until CLI is installed")

        # Initialize bot service (for auth and legacy features)
        self.bot_service = BotService(
            user_repository=user_repo,
            session_repository=session_repo,
            command_repository=command_repo,
        )

        # Initialize bot
        self.bot = Bot(
            token=settings.telegram.token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
        self.dp = Dispatcher()

        # Register handlers
        self._register_handlers()

        # Register middleware
        self.dp.message.middleware(AuthMiddleware(self.bot_service))
        self.dp.callback_query.middleware(CallbackAuthMiddleware(self.bot_service))

        logger.info("Bot initialized successfully")
        logger.info(f"Default working directory: {default_working_dir}")

    def _register_handlers(self):
        """Register all handlers"""
        # Message handlers (with claude_proxy for forwarding to Claude Code)
        msg_handlers = MessageHandlers(self.bot_service, self.claude_proxy)

        # Command handlers (with claude_proxy for new commands)
        cmd_handlers = CommandHandlers(self.bot_service, self.claude_proxy)
        cmd_handlers.message_handlers = msg_handlers  # Link for /project, /status commands
        register_cmd_handlers(self.dp, cmd_handlers)

        # Register message handlers after commands (commands take priority)
        register_msg_handlers(self.dp, msg_handlers)

        # Callback handlers (with claude_proxy for HITL)
        callback_handlers = CallbackHandlers(self.bot_service, msg_handlers, self.claude_proxy)
        register_callback_handlers(self.dp, callback_handlers)

    async def start(self):
        """Start the bot"""
        await self.setup()

        logger.info("Starting bot polling...")
        info = await self.bot.get_me()
        logger.info(f"Bot: @{info.username} (ID: {info.id})")

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
