#!/usr/bin/env python3
"""
Claude DevOps Bot - Telegram bot for server management using Claude AI

Architecture:
- Domain: Business entities and logic
- Application: Use cases and orchestration
- Infrastructure: External dependencies (SSH, AI, DB)
- Presentation: Telegram bot interface

Follows SOLID and DDD principles.
"""

import asyncio
import logging
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
from infrastructure.ssh.ssh_executor import SSHCommandExecutor
from infrastructure.messaging.claude_service import ClaudeAIService
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
        self._shutdown_event = asyncio.Event()

    async def setup(self):
        """Initialize application components"""
        logger.info("Initializing Claude DevOps Bot...")

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

        # Initialize services
        ai_service = ClaudeAIService()
        command_executor = SSHCommandExecutor()

        # Initialize bot service
        self.bot_service = BotService(
            user_repository=user_repo,
            session_repository=session_repo,
            command_repository=command_repo,
            ai_service=ai_service,
            command_executor=command_executor
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
        self.dp.update.middleware(AuthMiddleware(self.bot_service))
        self.dp.callback_query.middleware(CallbackAuthMiddleware(self.bot_service))

        logger.info("Bot initialized successfully")

    def _register_handlers(self):
        """Register all handlers"""
        # Command handlers
        cmd_handlers = CommandHandlers(self.bot_service)
        register_cmd_handlers(self.dp, cmd_handlers)

        # Message handlers
        msg_handlers = MessageHandlers(self.bot_service)
        register_msg_handlers(self.dp, msg_handlers)

        # Callback handlers
        callback_handlers = CallbackHandlers(self.bot_service, msg_handlers)
        register_callback_handlers(self.dp, callback_handlers)

    async def start(self):
        """Start the bot"""
        await self.setup()

        logger.info("Starting bot polling...")
        info = await self.bot.get_me()
        logger.info(f"Bot: @{info.username} (ID: {info.id})")

        # Set up signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

        # Start polling
        await self.dp.start_polling(
            self.bot,
            handle_signals=False  # We handle signals ourselves
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
