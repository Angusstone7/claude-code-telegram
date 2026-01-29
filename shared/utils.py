"""
Shared Utilities

Common utility functions to reduce code duplication across handlers.
"""

from functools import wraps
from typing import Callable, Any
from aiogram.types import CallbackQuery

from shared.constants import TEXT_TRUNCATE_LIMIT


def truncate_for_telegram(text: str, limit: int = TEXT_TRUNCATE_LIMIT) -> str:
    """
    Truncate text to fit Telegram message limits.

    Args:
        text: Text to truncate
        limit: Max characters (default from constants)

    Returns:
        Truncated text with "... (truncated)" suffix if needed
    """
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... (truncated)"


def require_same_user(error_message: str = "Это не ваше сообщение"):
    """
    Decorator to ensure callback is from the same user who triggered the action.

    Extracts user_id from callback.data (format: "action:user_id:...") and
    compares with callback.from_user.id.

    Usage:
        @require_same_user()
        async def handle_callback(self, callback: CallbackQuery):
            # Only executes if user_id matches
            pass

        @require_same_user("Вы не можете управлять чужой задачей")
        async def handle_cancel(self, callback: CallbackQuery):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, callback: CallbackQuery, *args, **kwargs) -> Any:
            # Extract user_id from callback data
            # Common formats: "action:user_id:..." or "action:user_id"
            parts = callback.data.split(":")
            if len(parts) >= 2:
                try:
                    expected_user_id = int(parts[1])
                    if callback.from_user.id != expected_user_id:
                        await callback.answer(error_message)
                        return
                except (ValueError, IndexError):
                    pass  # Can't extract user_id, proceed anyway

            return await func(self, callback, *args, **kwargs)
        return wrapper
    return decorator


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def safe_split_callback_data(data: str, expected_parts: int = 2) -> list[str]:
    """
    Safely split callback data into parts.

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
