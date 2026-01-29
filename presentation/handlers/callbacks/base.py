"""
Base Callback Handler

Base class for all callback handlers providing common functionality.
"""

import logging
from aiogram.types import CallbackQuery

logger = logging.getLogger(__name__)


class BaseCallbackHandler:
    """Base class for callback handlers with common dependencies."""

    def __init__(
        self,
        bot_service,
        message_handlers,
        claude_proxy=None,
        sdk_service=None,
        project_service=None,
        context_service=None,
        file_browser_service=None
    ):
        self.bot_service = bot_service
        self.message_handlers = message_handlers
        self.claude_proxy = claude_proxy
        self.sdk_service = sdk_service
        self.project_service = project_service
        self.context_service = context_service
        self.file_browser_service = file_browser_service

    async def _validate_same_user(
        self,
        callback: CallbackQuery,
        expected_user_id: int,
        error_message: str = "Это не ваше сообщение"
    ) -> bool:
        """
        Validate that callback is from the expected user.

        Returns True if valid, False if not (and answers callback).
        """
        if callback.from_user.id != expected_user_id:
            await callback.answer(error_message)
            return False
        return True

    async def _answer_error(self, callback: CallbackQuery, message: str) -> None:
        """Send error as callback answer."""
        await callback.answer(f"❌ {message}")

    async def _edit_message_error(self, callback: CallbackQuery, error: str) -> None:
        """Edit message to show error."""
        try:
            await callback.message.edit_text(f"❌ {error}", parse_mode=None)
        except Exception as e:
            logger.error(f"Failed to edit message with error: {e}")

    @staticmethod
    def parse_callback_data(data: str, expected_parts: int = 2) -> list[str]:
        """
        Safely parse callback data into parts.

        Args:
            data: Callback data string (e.g., "action:user_id:param")
            expected_parts: Minimum expected parts

        Returns:
            List of parts, padded with empty strings if needed
        """
        parts = data.split(":")
        while len(parts) < expected_parts:
            parts.append("")
        return parts
