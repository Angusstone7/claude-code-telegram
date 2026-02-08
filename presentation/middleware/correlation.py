"""
Correlation ID Middleware for aiogram.

Assigns a unique correlation_id to every incoming Telegram update
(message, callback_query, etc.) and stores it in contextvars.
All subsequent log lines within that request will include the ID.
"""

import logging
from typing import Callable, Awaitable, Any, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from shared.logging.correlation import set_correlation_id, generate_correlation_id

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseMiddleware):
    """
    Assigns a correlation_id to each incoming update.

    Format: tg-{8hex} for Telegram updates.
    The ID is stored in contextvars and automatically picked up
    by the JSON log formatter.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        cid = generate_correlation_id("tg-")
        set_correlation_id(cid)

        # Also put it in handler data so handlers can access it directly
        data["correlation_id"] = cid

        return await handler(event, data)
