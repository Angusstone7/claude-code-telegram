"""
Streaming Handler for Telegram

Handles real-time streaming of Claude Code output to Telegram with:
- Rate limiting (debounce) to avoid Telegram API spam
- Message length management (split long messages)
- Edit vs Send strategy for efficiency
"""

import asyncio
import html as html_module
import logging
import re
import time
from typing import Optional
from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

logger = logging.getLogger(__name__)


def markdown_to_html(text: str, is_streaming: bool = False) -> str:
    """
    Convert Markdown to Telegram HTML with placeholder protection.

    Uses placeholder system to protect already-formatted blocks from re-processing,
    preventing flickering during streaming updates.

    Supports:
    - **bold** → <b>bold</b>
    - *italic* → <i>italic</i>
    - `code` → <code>code</code>
    - ```code block``` → <pre>code block</pre>
    - __underline__ → <u>underline</u>
    - ~~strike~~ → <s>strike</s>
    - Unclosed code blocks (for streaming)
    """
    if not text:
        return text

    # Placeholder system to protect code blocks from double-processing
    placeholders = []

    def get_placeholder(index: int) -> str:
        return f"[--CODE-BLOCK-{index}--]"

    # 1. Handle UNCLOSED code block (for streaming)
    code_fence_count = text.count('```')
    unclosed_code_placeholder = None

    if code_fence_count % 2 != 0 and is_streaming:
        last_fence = text.rfind('```')
        text_before = text[:last_fence]
        unclosed_code = text[last_fence + 3:]

        # Extract language hint
        lang_match = re.match(r"(\w*)\n?", unclosed_code)
        lang = lang_match.group(1) if lang_match else ""
        code_content = unclosed_code[lang_match.end():] if lang_match else unclosed_code

        # Escape code content
        escaped_code = html_module.escape(code_content)
        lang_class = f' class="language-{lang}"' if lang else ''

        # WITHOUT closing tags - prepare_html_for_telegram will add them
        key = get_placeholder(len(placeholders))
        placeholders.append(f'<pre><code{lang_class}>{escaped_code}')
        unclosed_code_placeholder = key
        text = text_before

    # 2. Protect CLOSED code blocks with placeholders
    def protect_code_block(m: re.Match) -> str:
        key = get_placeholder(len(placeholders))
        lang = m.group(1) or ''
        code = m.group(2)
        escaped_code = html_module.escape(code)
        lang_class = f' class="language-{lang}"' if lang else ''
        placeholders.append(f'<pre><code{lang_class}>{escaped_code}</code></pre>')
        return key

    text = re.sub(
        r"```(\w*)\n?([\s\S]*?)```",
        protect_code_block,
        text
    )

    # 3. Protect inline code
    def protect_inline_code(m: re.Match) -> str:
        key = get_placeholder(len(placeholders))
        placeholders.append(f'<code>{html_module.escape(m.group(1))}</code>')
        return key

    text = re.sub(r'`([^`\n]+)`', protect_inline_code, text)

    # 4. Escape HTML ONLY in unprotected text (outside placeholders)
    text = html_module.escape(text)

    # 5. Markdown conversions (now safe - code blocks are protected)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__([^_]+)__', r'<u>\1</u>', text)
    text = re.sub(r'~~([^~]+)~~', r'<s>\1</s>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', text)

    # 6. Add unclosed block at the end
    if unclosed_code_placeholder:
        text += unclosed_code_placeholder

    # 7. Restore placeholders
    for i, content in enumerate(placeholders):
        text = text.replace(get_placeholder(i), content, 1)

    return text


def get_open_html_tags(text: str) -> list[str]:
    """
    Returns stack of unclosed HTML tags.

    Used to properly close tags before sending to Telegram.
    """
    tags = re.findall(r'<(/?)(\w+)[^>]*>', text)
    stack = []
    for is_closing, tag_name in tags:
        tag_name_lower = tag_name.lower()
        # Skip self-closing tags
        if tag_name_lower in ('br', 'hr', 'img'):
            continue
        if not is_closing:
            stack.append(tag_name_lower)
        elif stack and tag_name_lower == stack[-1]:
            stack.pop()
    return stack


def prepare_html_for_telegram(text: str, is_final: bool = False) -> str:
    """
    Prepare HTML text for Telegram - close unclosed tags, add cursor.

    Args:
        text: HTML text to prepare
        is_final: If False, adds blinking cursor █ at the end
    """
    # Remove incomplete opening tag at the end (e.g. "<b" without ">")
    last_open = text.rfind('<')
    last_close = text.rfind('>')
    if last_open > last_close:
        text = text[:last_open]

    # Close all open tags
    open_tags = get_open_html_tags(text)
    closing_tags = "".join([f"</{tag}>" for tag in reversed(open_tags)])

    # Add blinking cursor for non-final messages
    suffix = "" if is_final else " █"

    return text + closing_tags + suffix


class IncrementalFormatter:
    """
    Incremental formatter with stable block caching.

    Caches HTML for already-processed closed constructs,
    only re-formats the unstable "tail" of the text.

    This prevents flickering by ensuring stable parts
    produce identical HTML on every call.
    """

    def __init__(self):
        self.stable_html = ""  # Cached HTML for stable parts
        self.stable_raw_length = 0  # Length of processed raw text

    def format(self, raw_text: str, is_final: bool = False) -> str:
        """
        Incremental formatting.

        Args:
            raw_text: Full raw Markdown text
            is_final: Whether this is the final format (closes all blocks)

        Returns:
            stable_html + newly_formatted_unstable_html
        """
        if len(raw_text) < self.stable_raw_length:
            # Text got shorter (rare) - reset cache
            self.reset()

        # Find stability boundary
        stable_boundary = self._find_stable_boundary(raw_text)

        if stable_boundary > self.stable_raw_length:
            # New stable parts appeared - format and cache them
            new_stable = raw_text[self.stable_raw_length:stable_boundary]
            new_stable_html = markdown_to_html(new_stable, is_streaming=False)
            self.stable_html += new_stable_html
            self.stable_raw_length = stable_boundary

        # Format unstable tail
        unstable_part = raw_text[stable_boundary:]
        if unstable_part:
            unstable_html = markdown_to_html(unstable_part, is_streaming=not is_final)
        else:
            unstable_html = ""

        return self.stable_html + unstable_html

    def _find_stable_boundary(self, text: str) -> int:
        """
        Find position up to which text is stable.

        Text is stable when:
        - All ``` are paired (code blocks closed)
        - After last closed block there's a paragraph separator \\n\\n
        """
        # Find all closed code blocks
        closed_blocks = list(re.finditer(r'```[\s\S]*?```', text))

        if closed_blocks:
            last_closed_end = closed_blocks[-1].end()
        else:
            last_closed_end = 0

        # After last closed block, look for paragraph separator
        after_blocks = text[last_closed_end:]

        # Find last \n\n (end of paragraph)
        last_para = after_blocks.rfind('\n\n')
        if last_para > 0:
            # Check that paragraph is "stable" (all markers paired)
            para_text = after_blocks[:last_para]
            if self._is_paragraph_stable(para_text):
                return last_closed_end + last_para + 2

        return last_closed_end

    def _is_paragraph_stable(self, text: str) -> bool:
        """Check that all inline markers are paired."""
        markers = ['**', '__', '~~', '`']
        for marker in markers:
            if text.count(marker) % 2 != 0:
                return False
        return True

    def reset(self):
        """Reset cache for new message."""
        self.stable_html = ""
        self.stable_raw_length = 0


class StreamingHandler:
    """
    Manages streaming output to Telegram with rate limiting.

    Handles the complexities of:
    - Debouncing updates to avoid API rate limits
    - Splitting long messages that exceed Telegram's 4096 char limit
    - Graceful handling of rate limit errors with exponential backoff
    - Adaptive update intervals based on message size
    """

    # Telegram limits
    MAX_MESSAGE_LENGTH = 4000  # Leave buffer from 4096
    DEBOUNCE_INTERVAL = 2.0  # Base seconds between updates
    MIN_UPDATE_INTERVAL = 1.0  # Minimum seconds between edits

    # Adaptive interval thresholds (bytes)
    LARGE_TEXT_BYTES = 2500  # >2.5KB → 2.5s interval
    VERY_LARGE_TEXT_BYTES = 6000  # >6KB → 4.0s interval

    # Token estimation constants
    CHARS_PER_TOKEN = 4  # Approximate: 1 token ≈ 4 characters
    DEFAULT_CONTEXT_LIMIT = 200_000  # Claude Opus/Sonnet context window

    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        initial_message: Optional[Message] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        context_limit: int = DEFAULT_CONTEXT_LIMIT
    ):
        self.bot = bot
        self.chat_id = chat_id
        self.current_message = initial_message
        self.buffer = ""
        self.last_update_time = 0.0
        self.messages: list[Message] = []  # All sent messages
        self.is_finalized = False
        self._update_lock = asyncio.Lock()
        self._pending_update: Optional[asyncio.Task] = None
        self.reply_markup = reply_markup  # Cancel button etc.
        self._status_line = ""  # Status line shown at bottom
        self._formatter = IncrementalFormatter()  # Anti-flicker formatter
        self._todo_message: Optional[Message] = None  # Separate message for todo list
        self._plan_mode_message: Optional[Message] = None  # Plan mode indicator message
        self._is_plan_mode: bool = False  # Whether Claude is in plan mode

        # Token tracking for context usage display
        self._estimated_tokens: int = 0  # Accumulated token estimate
        self._context_limit: int = context_limit  # Max context window

        if initial_message:
            self.messages.append(initial_message)

    def add_tokens(self, text: str, multiplier: float = 1.0) -> int:
        """Add estimated tokens from text to the running total.

        Args:
            text: Text to estimate tokens for
            multiplier: Weight factor (e.g., 0.5 for tool results which are compressed)

        Returns:
            Number of tokens added
        """
        if not text:
            return 0
        tokens = int(len(text) / self.CHARS_PER_TOKEN * multiplier)
        self._estimated_tokens += tokens
        return tokens

    def get_context_usage(self) -> tuple[int, int, int]:
        """Get current context usage stats.

        Returns:
            Tuple of (estimated_tokens, context_limit, percentage)
        """
        pct = int(100 * self._estimated_tokens / self._context_limit) if self._context_limit > 0 else 0
        return self._estimated_tokens, self._context_limit, min(pct, 100)

    async def start(self, initial_text: str = "🤖 Запускаю...") -> Message:
        """Start streaming with an initial message"""
        if not self.current_message:
            html_text = markdown_to_html(initial_text)
            try:
                self.current_message = await self.bot.send_message(
                    self.chat_id,
                    html_text,
                    parse_mode="HTML",
                    reply_markup=self.reply_markup
                )
            except TelegramBadRequest:
                # Fallback without formatting if parsing fails
                self.current_message = await self.bot.send_message(
                    self.chat_id,
                    initial_text,
                    parse_mode=None,
                    reply_markup=self.reply_markup
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
        """Set a status line at the bottom of the current message"""
        self._status_line = f"🤖 {status}"
        await self._schedule_update()

    def _get_display_buffer(self) -> str:
        """Get buffer with status line at bottom"""
        if self._status_line:
            return f"{self.buffer}\n\n{self._status_line}"
        return self.buffer

    def _calc_edit_interval(self) -> float:
        """Calculate adaptive edit interval based on buffer size."""
        try:
            byte_size = len(self.buffer.encode('utf-8'))
        except Exception:
            byte_size = len(self.buffer)

        if byte_size >= self.VERY_LARGE_TEXT_BYTES:
            return 4.0  # Very large messages - update less frequently
        if byte_size >= self.LARGE_TEXT_BYTES:
            return 2.5  # Large messages
        return self.DEBOUNCE_INTERVAL  # Default 2.0s

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
        result_text = f"{status} **Вывод:**\n```\n{truncated}\n```\n"
        await self.append(result_text)

    async def show_todo_list(self, todos: list[dict]) -> None:
        """Show/update todo list in a separate message.

        Creates a dedicated message for the task plan that updates
        in-place as tasks progress. Shows:
        - ✅ Completed tasks (strikethrough)
        - ⏳ Current task (bold)
        - ⬜ Pending tasks

        Args:
            todos: List of todo items with content, status, activeForm
        """
        if not todos:
            return

        lines = ["📋 <b>План выполнения:</b>\n"]

        for todo in todos:
            status = todo.get("status", "pending")
            # Use activeForm for in_progress, content for others
            if status == "in_progress":
                text = todo.get("activeForm", todo.get("content", ""))
            else:
                text = todo.get("content", "")

            if status == "completed":
                lines.append(f"  ✅ <s>{text}</s>")
            elif status == "in_progress":
                lines.append(f"  ⏳ <b>{text}</b>")
            else:  # pending
                lines.append(f"  ⬜ {text}")

        # Count stats
        completed = sum(1 for t in todos if t.get("status") == "completed")
        total = len(todos)
        lines.append(f"\n<i>Прогресс: {completed}/{total}</i>")

        html_text = "\n".join(lines)

        try:
            if self._todo_message:
                # Update existing message
                await self._todo_message.edit_text(html_text, parse_mode="HTML")
            else:
                # Create new message
                self._todo_message = await self.bot.send_message(
                    self.chat_id,
                    html_text,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.debug(f"Error updating todo message: {e}")

    async def show_plan_mode_enter(self) -> None:
        """Show that Claude entered plan mode.

        Displays a visual indicator that Claude is analyzing
        the task and creating a plan before execution.
        """
        self._is_plan_mode = True

        html_text = (
            "🎯 <b>Режим планирования</b>\n\n"
            "<i>Claude анализирует задачу и составляет план...</i>"
        )

        try:
            if self._plan_mode_message:
                await self._plan_mode_message.edit_text(html_text, parse_mode="HTML")
            else:
                self._plan_mode_message = await self.bot.send_message(
                    self.chat_id,
                    html_text,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.debug(f"Error showing plan mode: {e}")

    async def show_plan_mode_exit(self, plan_approved: bool = False) -> None:
        """Show that Claude exited plan mode.

        Args:
            plan_approved: Whether the plan was approved (True) or just ready (False)
        """
        self._is_plan_mode = False

        if plan_approved:
            html_text = "✅ <b>План утверждён</b> — начинаю выполнение"
        else:
            html_text = "📋 <b>План готов</b> — ожидаю подтверждения"

        try:
            if self._plan_mode_message:
                await self._plan_mode_message.edit_text(html_text, parse_mode="HTML")
                self._plan_mode_message = None
            else:
                await self.bot.send_message(
                    self.chat_id,
                    html_text,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.debug(f"Error showing plan mode exit: {e}")

    async def show_question(
        self,
        question_id: str,
        questions: list[dict],
        keyboard: Optional[InlineKeyboardMarkup] = None
    ) -> Optional[Message]:
        """Show Claude's question with option buttons.

        Displays AskUserQuestion from Claude with inline keyboard
        for selecting answers.

        Args:
            question_id: Unique ID for callback matching
            questions: List of question dicts with question, header, options
            keyboard: Pre-built keyboard (optional, will be built if not provided)

        Returns:
            Sent message for later reference
        """
        if not questions:
            return None

        # Build message text
        lines = ["❓ <b>Вопрос от Claude:</b>\n"]

        for q in questions:
            header = q.get("header", "")
            question = q.get("question", "")

            if header:
                lines.append(f"<b>{header}</b>")
            lines.append(question)

            # Show option descriptions if available
            options = q.get("options", [])
            for opt in options:
                desc = opt.get("description", "")
                if desc:
                    label = opt.get("label", "")
                    lines.append(f"  • <b>{label}</b>: {desc}")

            lines.append("")  # Empty line between questions

        html_text = "\n".join(lines)

        # Build keyboard if not provided
        if keyboard is None:
            from presentation.keyboards.keyboards import Keyboards
            keyboard = Keyboards.question_options(questions, question_id)

        try:
            msg = await self.bot.send_message(
                self.chat_id,
                html_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            return msg
        except Exception as e:
            logger.error(f"Error showing question: {e}")
            return None

    async def _schedule_update(self):
        """Schedule a debounced update with adaptive interval"""
        async with self._update_lock:
            now = time.time()
            time_since_update = now - self.last_update_time
            interval = self._calc_edit_interval()

            if time_since_update >= interval:
                # Enough time passed, update immediately
                await self._do_update()
            else:
                # Schedule delayed update if not already pending
                if self._pending_update is None or self._pending_update.done():
                    delay = interval - time_since_update
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

        display_text = self._get_display_buffer()

        try:
            # Check if we need to split into multiple messages
            if len(display_text) > self.MAX_MESSAGE_LENGTH:
                await self._handle_overflow()
            else:
                await self._edit_current_message(display_text)

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
                await self._send_new_message(display_text)
            else:
                logger.error(f"Telegram error: {e}")

        except Exception as e:
            logger.error(f"Error updating message: {e}")

    async def _edit_current_message(self, text: str, is_final: bool = False):
        """Edit the current message with new text using incremental formatting"""
        if self.current_message:
            # Use incremental formatter to prevent flickering
            if is_final:
                # Final message - full format for reliability, then reset formatter
                html_text = markdown_to_html(text, is_streaming=False)
                self._formatter.reset()
            else:
                # Streaming - use incremental formatter (caches stable parts)
                html_text = self._formatter.format(text, is_final=False)

            # Prepare for Telegram - close unclosed tags, add cursor if not final
            html_text = prepare_html_for_telegram(html_text, is_final=is_final)
            try:
                await self.current_message.edit_text(
                    html_text,
                    parse_mode="HTML",
                    reply_markup=self.reply_markup
                )
            except TelegramBadRequest:
                # Fallback without formatting
                await self.current_message.edit_text(
                    text, parse_mode=None, reply_markup=self.reply_markup
                )

    async def _send_new_message(self, text: str, is_final: bool = False) -> Message:
        """Send a new message (converts Markdown to HTML)"""
        # Reset formatter for new message
        self._formatter.reset()

        # Convert Markdown to HTML with streaming support
        html_text = markdown_to_html(text, is_streaming=not is_final)
        # Prepare for Telegram - close unclosed tags, add cursor if not final
        html_text = prepare_html_for_telegram(html_text, is_final=is_final)
        try:
            msg = await self.bot.send_message(
                self.chat_id,
                html_text,
                parse_mode="HTML",
                reply_markup=self.reply_markup
            )
        except TelegramBadRequest:
            # Fallback without formatting
            msg = await self.bot.send_message(
                self.chat_id, text, parse_mode=None, reply_markup=self.reply_markup
            )

        self.messages.append(msg)
        self.current_message = msg
        return msg

    async def _handle_overflow(self, is_final: bool = False):
        """Handle buffer overflow with sliding window - remove old content, keep newest"""
        # Extract header (first lines with emoji status)
        lines = self.buffer.split("\n")
        header_lines = []
        content_start = 0

        # Keep header lines (status and project info)
        for i, line in enumerate(lines):
            if line.startswith("🤖") or line.startswith("📂") or line.startswith("📁"):
                header_lines.append(line)
                content_start = i + 1
            elif header_lines:  # Stop after first non-header line
                break

        header = "\n".join(header_lines)
        content = "\n".join(lines[content_start:])

        # Target size - leave room for new content
        target_size = self.MAX_MESSAGE_LENGTH - 500

        # Remove oldest content blocks until we fit
        trimmed = False
        while len(header) + len(content) + 50 > target_size and content:
            trimmed = True
            # Find first block separator (double newline or tool result end)
            block_end = content.find("\n\n")
            if block_end > 0 and block_end < len(content) - 100:
                content = content[block_end + 2:]
            else:
                # Fallback: remove first 300 chars
                content = content[300:]

        # Build new buffer with trim indicator
        if trimmed:
            trim_indicator = "\n*(...)*\n"
            self.buffer = header + trim_indicator + content.lstrip("\n")
        else:
            self.buffer = header + "\n" + content if header else content

        # Update message with trimmed content
        await self._edit_current_message(self.buffer, is_final=is_final)

    async def finalize(self, final_text: Optional[str] = None):
        """Finalize the stream with optional final text"""
        self.is_finalized = True

        # Cancel any pending updates
        if self._pending_update and not self._pending_update.done():
            self._pending_update.cancel()

        # Clear status line and cancel button
        self._status_line = ""
        self.reply_markup = None

        if final_text:
            self.buffer = final_text

        # Force final update (without status, without cancel button, without cursor)
        if self.buffer:
            try:
                if len(self.buffer) > self.MAX_MESSAGE_LENGTH:
                    await self._handle_overflow(is_final=True)
                else:
                    await self._edit_current_message(self.buffer, is_final=True)
            except Exception as e:
                logger.error(f"Error finalizing: {e}")

    async def send_error(self, error: str):
        """Send an error message"""
        error_text = f"❌ **Ошибка**\n```\n{error[:1000]}\n```"
        await self.append(f"\n\n{error_text}")
        await self.finalize()

    async def send_completion(self, success: bool = True):
        """Send a completion indicator"""
        if success:
            await self.append("\n\n✅ **Готово**")
        else:
            await self.append("\n\n⚠️ **Завершено с проблемами**")
        await self.finalize()

    async def move_to_bottom(self, header: str = ""):
        """
        Create a new message at the bottom for continued streaming.

        Call this after sending other messages (like permission requests)
        to ensure the streaming output stays at the bottom of the chat.
        """
        # Finalize current message without the completion marker
        if self.current_message and self.buffer:
            try:
                await self._edit_current_message(self.buffer)
            except Exception as e:
                logger.debug(f"Could not finalize old message: {e}")

        # Reset state for new message
        self.current_message = None
        self.buffer = header or "🤖 **Продолжаю...**\n\n"
        self.is_finalized = False

        # Send new message at bottom
        self.current_message = await self._send_new_message(self.buffer)
        self.last_update_time = time.time()
        return self.current_message


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


class HeartbeatTracker:
    """Periodic status updates during long operations.

    Shows elapsed time and animated spinner to indicate the bot is still working.
    """

    SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, streaming: StreamingHandler, interval: float = 5.0):
        self.streaming = streaming
        self.interval = interval
        self.start_time = time.time()
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._spinner_idx = 0

    async def start(self):
        """Start heartbeat updates"""
        self.is_running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        """Stop heartbeat updates"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        """Periodic status update loop"""
        while self.is_running:
            try:
                elapsed = int(time.time() - self.start_time)
                spinner = self.SPINNERS[self._spinner_idx % len(self.SPINNERS)]
                self._spinner_idx += 1

                # Format time nicely
                if elapsed < 60:
                    time_str = f"{elapsed} сек"
                else:
                    mins = elapsed // 60
                    secs = elapsed % 60
                    time_str = f"{mins}:{secs:02d}"

                # Get context usage stats
                tokens, limit, pct = self.streaming.get_context_usage()
                tokens_k = tokens // 1000
                limit_k = limit // 1000

                # Format status with context info
                status = f"Работаю... {spinner} ({time_str}) | ~{tokens_k}K/{limit_k}K ({pct}%)"
                await self.streaming.set_status(status)
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Heartbeat error: {e}")
                break
