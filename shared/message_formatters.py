"""
Telegram message formatting utilities.

Shared HTML formatting functions for permission requests, plan display, etc.
Extracted from messages.py and ai_request_handler.py to eliminate duplication.
"""

import html


def format_permission_request(tool_name: str, details: str, max_detail_length: int = 500) -> str:
    """
    Format a permission request message with proper HTML escaping.

    Args:
        tool_name: Name of the tool requesting permission.
        details: Tool execution details.
        max_detail_length: Maximum length for details before truncation.

    Returns:
        HTML-formatted text ready for Telegram.
    """
    text = "<b>Запрос разрешения</b>\n\n"
    text += f"<b>Инструмент:</b> <code>{html.escape(tool_name)}</code>\n"
    if details:
        display_details = details if len(details) < max_detail_length else details[:max_detail_length] + "..."
        text += f"<b>Детали:</b>\n<pre><code>{html.escape(display_details)}</code></pre>"
    return text
