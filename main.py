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

Refactored to use Dependency Injection Container for better testability
and maintainability (fixes DI violations from code review).
"""

# Disable Python bytecode caching to prevent stale .pyc issues
import sys
sys.dont_write_bytecode = True

import asyncio
import logging
import os
import signal
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand

from shared.config.settings import settings
from shared.container import Container, Config
from infrastructure.claude_code.diagnostics import run_and_log_diagnostics
from presentation.middleware.auth import AuthMiddleware, CallbackAuthMiddleware
from presentation.handlers.state.update_coordinator import init_coordinator

# Configure structured JSON logging
Path("logs").mkdir(exist_ok=True)
from shared.logging.config import setup_logging
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))

logger = logging.getLogger(__name__)


class Application:
    """
    Main application class.

    Uses Dependency Injection Container for all service creation,
    following Dependency Inversion Principle.
    """

    def __init__(self, container: Container = None):
        self.container = container or Container()
        self.bot: Bot = None
        self.dp: Dispatcher = None
        self._shutdown_event = asyncio.Event()

    async def setup(self):
        """Initialize application components"""
        logger.info("Initializing Claude Code Telegram Proxy...")

        # Ensure directories exist
        Path("logs").mkdir(exist_ok=True)
        Path("data").mkdir(exist_ok=True)

        # Initialize container (database, repositories)
        logger.info("Initializing container...")
        await self.container.init()

        # Check Claude Code backends
        claude_proxy = self.container.claude_proxy()
        claude_sdk = self.container.claude_sdk()

        # Check CLI backend
        installed, message = await claude_proxy.check_claude_installed()
        if installed:
            logger.info(f"✓ CLI: {message}")
            await run_and_log_diagnostics(claude_proxy.claude_path)
        else:
            logger.warning(f"⚠ CLI: {message}")

        # Check SDK backend
        if claude_sdk:
            sdk_ok, sdk_msg = await claude_sdk.check_sdk_available()
            if sdk_ok:
                logger.info(f"✓ SDK: {sdk_msg}")
                plugins_info = claude_sdk.get_enabled_plugins_info()
                available_plugins = [p["name"] for p in plugins_info if p.get("available")]
                if available_plugins:
                    logger.info(f"✓ Плагины: {', '.join(available_plugins)}")
            else:
                logger.warning(f"⚠ SDK: {sdk_msg}")

        # Initialize bot
        self.bot = Bot(
            token=settings.telegram.token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        self.dp = Dispatcher()

        # ВАЖНО: Инициализировать координатор обновлений ПЕРЕД хэндлерами!
        # Координатор гарантирует минимум 2 секунды между обновлениями сообщений
        coordinator = init_coordinator(self.bot)
        logger.info(f"✓ MessageUpdateCoordinator initialized (min interval: {coordinator.MIN_UPDATE_INTERVAL}s)")

        # Register handlers (using container)
        self._register_handlers()

        # Register middleware
        # Rate limiting FIRST (before auth to prevent DoS)
        from presentation.middleware.rate_limit import RateLimitMiddleware
        admin_ids = self.container.config.admin_ids or []
        self.dp.message.middleware(RateLimitMiddleware(
            rate_limit=0.5,  # 2 сообщения в секунду
            burst=5,  # Максимум 5 сообщений мгновенно
            admin_ids=admin_ids,  # Admins без ограничений
        ))
        logger.info("✓ RateLimitMiddleware registered (0.5s per message, burst=5)")

        self.dp.message.middleware(AuthMiddleware(self.container.bot_service()))
        self.dp.callback_query.middleware(CallbackAuthMiddleware(self.container.bot_service()))

        # Register bot commands
        await self._register_bot_commands()

        logger.info("Bot initialized successfully")
        logger.info(f"Default working directory: {self.container.config.claude_working_dir}")

    def _register_handlers(self):
        """Register all handlers using container"""
        # CRITICAL: Verify Keyboards class has all required methods before proceeding
        from presentation.keyboards.keyboards import Keyboards
        required_methods = ['proxy_settings_menu', 'proxy_type_selection', 'proxy_auth_options']
        missing = [m for m in required_methods if not hasattr(Keyboards, m)]
        if missing:
            logger.error(f"FATAL: Keyboards class missing methods: {missing}")
            logger.error(f"Available methods: {[m for m in dir(Keyboards) if not m.startswith('_')]}")
            raise RuntimeError(f"Keyboards class missing required methods: {missing}")
        logger.info(f"✓ Keyboards class verified (has {len([m for m in dir(Keyboards) if not m.startswith('_')])} methods)")

        from presentation.handlers.commands import register_handlers as register_cmd_handlers
        # REFACTORED VERSION - modular architecture
        from presentation.handlers.message import register_handlers as register_msg_handlers
        from presentation.handlers.callbacks import register_handlers as register_callback_handlers
        from presentation.handlers.account_handlers import register_account_handlers
        from presentation.handlers.menu_handlers import register_menu_handlers
        from presentation.handlers.proxy_handlers import register_proxy_handlers

        # Account handlers (for /account command and mode switching)
        register_account_handlers(self.dp, self.container.account_handlers())

        # Command handlers
        register_cmd_handlers(self.dp, self.container.command_handlers())

        # Menu handlers - main inline menu system
        register_menu_handlers(self.dp, self.container.menu_handlers())

        # Proxy handlers - proxy settings management
        register_proxy_handlers(self.dp, self.container.proxy_handlers())

        # Message handlers (after commands - commands take priority)
        register_msg_handlers(self.dp, self.container.message_handlers())

        # Callback handlers
        register_callback_handlers(self.dp, self.container.callback_handlers())

    async def _register_bot_commands(self):
        """Register bot commands in Telegram menu"""
        commands = [
            BotCommand(command="start", description="📱 Открыть меню"),
            BotCommand(command="yolo", description="⚡ Вкл/выкл авто-подтверждение"),
            BotCommand(command="cancel", description="🛑 Отменить задачу"),
        ]

        try:
            await self.bot.set_my_commands(commands)
            logger.info(f"✓ Registered {len(commands)} bot commands in Telegram menu")
        except Exception as e:
            logger.warning(f"⚠ Failed to register bot commands: {e}")

    async def _notify_admins_startup(self, bot_info):
        """
        Notify admins that bot has started successfully.

        Uses admin_ids from configuration instead of hardcoded value.
        """
        admin_ids = self.container.config.admin_ids
        if not admin_ids:
            logger.warning("No admin IDs configured, skipping startup notification")
            return

        # Build status message
        claude_sdk = self.container.claude_sdk()
        claude_proxy = self.container.claude_proxy()
        account_service = self.container.account_service()

        sdk_status = "✅ SDK" if claude_sdk else "❌ SDK"
        cli_ok, _ = await claude_proxy.check_claude_installed()
        cli_status = "✅ CLI" if cli_ok else "❌ CLI"

        creds_info = account_service.get_credentials_info()
        creds_status = (
            f"✅ {creds_info.subscription_type}" if creds_info.exists
            else "❌ не найден"
        )

        message = (
            f"🚀 <b>Бот запущен!</b>\n\n"
            f"🤖 @{bot_info.username}\n"
            f"📦 {sdk_status} | {cli_status}\n"
            f"☁️ Claude creds: {creds_status}\n"
            f"📁 {self.container.config.claude_working_dir}\n\n"
            f"<i>Готов к работе</i>"
        )

        # Notify all admins
        for admin_id in admin_ids:
            try:
                await self.bot.send_message(admin_id, message)
                logger.info(f"✓ Admin {admin_id} notified about startup")
            except Exception as e:
                logger.warning(f"⚠ Failed to notify admin {admin_id}: {e}")

    async def start(self):
        """Start the bot"""
        await self.setup()

        logger.info("Starting bot polling...")
        info = await self.bot.get_me()
        logger.info(f"Bot: @{info.username} (ID: {info.id})")

        # Start Prometheus metrics server if monitoring is enabled
        if settings.monitoring.enabled:
            from infrastructure.monitoring.prometheus_exporter import (
                start_metrics_server, update_system_metrics, bot_info
            )
            start_metrics_server(settings.monitoring.metrics_port)
            bot_info.info({'username': info.username, 'id': str(info.id)})
            # Background task: update system metrics every 15s
            monitor = self.container.system_monitor()
            asyncio.create_task(update_system_metrics(monitor))

        # Notify admins that bot started
        await self._notify_admins_startup(info)

        # Set up signal handlers (Unix only)
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

        # Start polling
        await self.dp.start_polling(
            self.bot,
            handle_signals=sys.platform == "win32"
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

        # Close container resources
        await self.container.close()

        # Close bot session
        if self.bot:
            await self.bot.session.close()

        logger.info("Shutdown complete")


async def main():
    """Main entry point"""
    # Create container with configuration
    config = Config.from_env()
    container = Container(config)

    app = Application(container)

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
