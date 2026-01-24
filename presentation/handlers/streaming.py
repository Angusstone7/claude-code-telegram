"""
Streaming Handler for Telegram

Handles real-time streaming of Claude Code output to Telegram with:
- Rate limiting (debounce) to avoid Telegram API spam
- Message length management (split long messages)
- Edit vs Send strategy for efficiency
"""

import asyncio
import logging
import time
from typing import Optional
from aiogram import Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

logger = logging.getLogger(__name__)


class StreamingHandler:
    """
    Manages streaming output to Telegram with rate limiting.

    Handles the complexities of:
    - Debouncing updates to avoid API rate limits
    - Splitting long messages that exceed Telegram's 4096 char limit
    - Graceful handling of rate limit errors with exponential backoff
    """

    # Telegram limits
    MAX_MESSAGE_LENGTH = 4000  # Leave buffer from 4096
    DEBOUNCE_INTERVAL = 2.0  # Seconds between updates
    MIN_UPDATE_INTERVAL = 1.0  # Minimum seconds between edits

    def __init__(self, bot: Bot, chat_id: int, initial_message: Optional[Message] = None):
        self.bot = bot
        self.chat_id = chat_id
        self.current_message = initial_message
        self.buffer = ""
        self.last_update_time = 0.0
        self.messages: list[Message] = []  # All sent messages
        self.is_finalized = False
        self._update_lock = asyncio.Lock()
        self._pending_update: Optional[asyncio.Task] = None

        if initial_message:
            self.messages.append(initial_message)

    async def start(self, initial_text: str = "🤖 Starting...") -> Message:
        """Start streaming with an initial message"""
        if not self.current_message:
            self.current_message = await self.bot.send_message(
                self.chat_id,
                initial_text,
                parse_mode="Markdown"
            )
            self.messages.append(self.current_message)
        self.buffer = initial_text
        self.last_update_time = time.time()
        return self.current_message

    async def append(self, text: str):
        """
        Append text to the stream buffer.
        Updates are debounced to avoid rate limits.
        """
        if self.is_finalized:
            return

        self.buffer += text

        # Schedule debounced update
        await self._schedule_update()

    async def append_line(self, text: str):
        """Append text followed by a newline"""
        await self.append(text + "\n")

    async def set_status(self, status: str):
        """Set a status line at the top of the current message"""
        lines = self.buffer.split("\n")

        # Replace first line if it's a status line, otherwise prepend
        if lines and lines[0].startswith("🤖"):
            lines[0] = f"🤖 {status}"
        else:
            lines.insert(0, f"🤖 {status}")

        self.buffer = "\n".join(lines)
        await self._schedule_update()

    async def show_tool_use(self, tool_name: str, details: str = ""):
        """Show that a tool is being used with nice formatting"""
        # Emoji mapping for different tools
        emoji_map = {
            "bash": "💻",
            "write": "📝",
            "read": "📖",
            "edit": "✏️",
            "glob": "🔍",
            "grep": "🔎",
            "task": "🤖",
            "webfetch": "🌐",
            "websearch": "🔎",
            "askuserquestion": "❓",
            "todowrite": "📋",
        }
        emoji = emoji_map.get(tool_name.lower(), "🔧")

        tool_display = f"\n{emoji} **{tool_name}**"
        if details:
            # Truncate long details
            if len(details) > 150:
                details = details[:150] + "..."
            tool_display += f"\n`{details}`"
        tool_display += "\n"
        await self.append(tool_display)

    async def show_tool_result(self, output: str, success: bool = True):
        """Show tool execution result with formatting"""
        if not output or not output.strip():
            return

        # Truncate long output
        truncated = output.strip()
        if len(truncated) > 1500:
            truncated = truncated[:1500] + "\n... (truncated)"

        status = "✅" if success else "❌"
        result_text = f"{status} **Output:**\n```\n{truncated}\n```\n"
        await self.append(result_text)

    async def _schedule_update(self):
        """Schedule a debounced update"""
        async with self._update_lock:
            now = time.time()
            time_since_update = now - self.last_update_time

            if time_since_update >= self.DEBOUNCE_INTERVAL:
                # Enough time passed, update immediately
                await self._do_update()
            else:
                # Schedule delayed update if not already pending
                if self._pending_update is None or self._pending_update.done():
                    delay = self.DEBOUNCE_INTERVAL - time_since_update
                    self._pending_update = asyncio.create_task(
                        self._delayed_update(delay)
                    )

    async def _delayed_update(self, delay: float):
        """Wait and then perform update"""
        await asyncio.sleep(delay)
        async with self._update_lock:
            await self._do_update()

    async def _do_update(self):
        """Actually perform the update to Telegram"""
        if not self.buffer or self.is_finalized:
            return

        try:
            # Check if we need to split into multiple messages
            if len(self.buffer) > self.MAX_MESSAGE_LENGTH:
                await self._handle_overflow()
            else:
                await self._edit_current_message(self.buffer)

            self.last_update_time = time.time()

        except TelegramRetryAfter as e:
            # Rate limited - wait and retry
            logger.warning(f"Rate limited, waiting {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
            await self._do_update()

        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                # Same content, ignore
                pass
            elif "message to edit not found" in str(e):
                # Message deleted, send new one
                await self._send_new_message(self.buffer)
            else:
                logger.error(f"Telegram error: {e}")

        except Exception as e:
            logger.error(f"Error updating message: {e}")

    async def _edit_current_message(self, text: str):
        """Edit the current message with new text"""
        if self.current_message:
            try:
                await self.current_message.edit_text(
                    text,
                    parse_mode="Markdown"
                )
            except TelegramBadRequest:
                # Try without markdown if it fails
                await self.current_message.edit_text(text)

    async def _send_new_message(self, text: str) -> Message:
        """Send a new message"""
        try:
            msg = await self.bot.send_message(
                self.chat_id,
                text,
                parse_mode="Markdown"
            )
        except TelegramBadRequest:
            # Try without markdown
            msg = await self.bot.send_message(self.chat_id, text)

        self.messages.append(msg)
        self.current_message = msg
        return msg

    async def _handle_overflow(self):
        """Handle buffer overflow by splitting into multiple messages"""
        # Find a good split point (newline near the limit)
        split_point = self.buffer.rfind("\n", 0, self.MAX_MESSAGE_LENGTH)
        if split_point == -1:
            split_point = self.MAX_MESSAGE_LENGTH

        # Send the completed portion as a new message (finalize previous)
        completed = self.buffer[:split_point]
        remaining = self.buffer[split_point:].lstrip("\n")

        # Update current message with completed text
        await self._edit_current_message(completed)

        # Start a new message with remaining text
        if remaining:
            self.buffer = remaining
            self.current_message = await self._send_new_message(remaining)
        else:
            self.buffer = ""

    async def finalize(self, final_text: Optional[str] = None):
        """Finalize the stream with optional final text"""
        self.is_finalized = True

        # Cancel any pending updates
        if self._pending_update and not self._pending_update.done():
            self._pending_update.cancel()

        if final_text:
            self.buffer = final_text

        # Force final update
        if self.buffer:
            try:
                if len(self.buffer) > self.MAX_MESSAGE_LENGTH:
                    await self._handle_overflow()
                else:
                    await self._edit_current_message(self.buffer)
            except Exception as e:
                logger.error(f"Error finalizing: {e}")

    async def send_error(self, error: str):
        """Send an error message"""
        error_text = f"❌ **Error**\n```\n{error[:1000]}\n```"
        await self.append(f"\n\n{error_text}")
        await self.finalize()

    async def send_completion(self, success: bool = True):
        """Send a completion indicator"""
        if success:
            await self.append("\n\n✅ **Done**")
        else:
            await self.append("\n\n⚠️ **Completed with issues**")
        await self.finalize()


class ProgressTracker:
    """Track progress of multi-step operations"""

    def __init__(self, streaming_handler: StreamingHandler):
        self.handler = streaming_handler
        self.steps: list[str] = []
        self.current_step = 0
        self.total_steps = 0

    async def set_steps(self, steps: list[str]):
        """Set the steps for this operation"""
        self.steps = steps
        self.total_steps = len(steps)
        self.current_step = 0
        await self._update_progress()

    async def advance(self):
        """Move to the next step"""
        self.current_step = min(self.current_step + 1, self.total_steps)
        await self._update_progress()

    async def complete_step(self, step_index: int):
        """Mark a specific step as complete"""
        self.current_step = max(self.current_step, step_index + 1)
        await self._update_progress()

    async def _update_progress(self):
        """Update the progress display"""
        if not self.steps:
            return

        progress_lines = []
        for i, step in enumerate(self.steps):
            if i < self.current_step:
                progress_lines.append(f"✅ {step}")
            elif i == self.current_step:
                progress_lines.append(f"⏳ {step}")
            else:
                progress_lines.append(f"⬜ {step}")

        progress_text = "\n".join(progress_lines)
        await self.handler.set_status(f"Progress ({self.current_step}/{self.total_steps})")
