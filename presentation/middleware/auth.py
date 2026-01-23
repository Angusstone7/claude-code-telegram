import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Awaitable, Any, Dict
from application.services.bot_service import BotService

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Middleware for user authorization"""

    def __init__(self, bot_service: BotService):
        super().__init__()
        self.bot_service = bot_service

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """Check if user is authorized"""
        user_id = event.from_user.id

        # For specific commands that don't need auth
        if event.text and event.text.startswith("/start"):
            return await handler(event, data)

        # Check authorization
        user = await self.bot_service.authorize_user(user_id)
        if not user:
            await event.answer("❌ You are not authorized to use this bot.")
            return

        # Add user to data
        data["user"] = user
        return await handler(event, data)


class CallbackAuthMiddleware(BaseMiddleware):
    """Middleware for callback query authorization"""

    def __init__(self, bot_service: BotService):
        super().__init__()
        self.bot_service = bot_service

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """Check if user is authorized for callback"""
        user_id = event.from_user.id

        user = await self.bot_service.authorize_user(user_id)
        if not user:
            await event.answer("❌ You are not authorized.")
            return

        data["user"] = user
        return await handler(event, data)
