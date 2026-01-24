import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from typing import Callable, Awaitable, Any, Dict, Union
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
        event: Union[Message, Update],
        data: Dict[str, Any]
    ) -> Any:
        """Check if user is authorized"""

        # Handle Update object (aiogram 3.x may pass Update directly)
        if isinstance(event, Update):
            # Extract the actual event from Update
            if event.message:
                event = event.message
            elif event.callback_query:
                event = event.callback_query
            else:
                logger.warning(f"Unhandled update type: {type(event)}")
                return

        # Get user_id from the event
        user_id = event.from_user.id if hasattr(event, 'from_user') and event.from_user else None
        if not user_id:
            logger.warning("Event has no from_user")
            return

        # For specific commands that don't need auth
        if hasattr(event, 'text') and event.text and event.text.startswith("/start"):
            return await handler(event, data)

        # Check authorization
        user = await self.bot_service.authorize_user(user_id)
        if not user:
            if hasattr(event, 'answer'):
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
        event: Union[CallbackQuery, Update],
        data: Dict[str, Any]
    ) -> Any:
        """Check if user is authorized for callback"""

        # Handle Update object
        if isinstance(event, Update):
            if event.callback_query:
                event = event.callback_query
            else:
                logger.warning(f"Non-callback update in CallbackAuthMiddleware: {type(event)}")
                return

        # Get user_id
        user_id = event.from_user.id if hasattr(event, 'from_user') and event.from_user else None
        if not user_id:
            logger.warning("Callback query has no from_user")
            return

        user = await self.bot_service.authorize_user(user_id)
        if not user:
            if hasattr(event, 'answer'):
                await event.answer("❌ You are not authorized.")
            return

        data["user"] = user
        return await handler(event, data)
