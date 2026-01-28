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
from dataclasses import dataclass
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

    Fault-tolerant:
    - Handles partial markdown constructs during streaming
    - Escapes problematic characters to prevent Telegram parse errors
    - Preserves original text on conversion failure
    """
    if not text:
        return text

    try:
        return _markdown_to_html_impl(text, is_streaming)
    except Exception as e:
        # Fallback: escape everything and return as-is
        logger.warning(f"markdown_to_html failed, using fallback: {e}")
        return html_module.escape(text)


def _markdown_to_html_impl(text: str, is_streaming: bool = False) -> str:
    """Internal implementation of markdown to HTML conversion."""
    # Placeholder system to protect code blocks from double-processing
    placeholders = []

    def get_placeholder(index: int) -> str:
        return f"\x00BLOCK{index}\x00"  # Use null bytes as unlikely delimiters

    # 1. Handle UNCLOSED code block (for streaming)
    code_fence_count = text.count('```')
    unclosed_code_placeholder = None

    if code_fence_count % 2 != 0 and is_streaming:
        last_fence = text.rfind('```')
        text_before = text[:last_fence]
        unclosed_code = text[last_fence + 3:]

        # Extract language hint (ASCII only to avoid capturing Cyrillic/Unicode text)
        lang_match = re.match(r"([a-zA-Z][a-zA-Z0-9_+-]*|)\n?", unclosed_code)
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
        r"```([a-zA-Z][a-zA-Z0-9_+-]*)?\n?([\s\S]*?)```",
        protect_code_block,
        text
    )

    # 3. Protect inline code (but not partial backticks at end during streaming)
    def protect_inline_code(m: re.Match) -> str:
        key = get_placeholder(len(placeholders))
        placeholders.append(f'<code>{html_module.escape(m.group(1))}</code>')
        return key

    text = re.sub(r'`([^`\n]+)`', protect_inline_code, text)

    # 4. Escape HTML ONLY in unprotected text (outside placeholders)
    text = html_module.escape(text)

    # 5. Markdown conversions (now safe - code blocks are protected)
    # Use non-greedy matching and be careful with partial constructs

    # Bold: **text** - but not if it's just ** at the end (streaming)
    if is_streaming and text.rstrip().endswith('**'):
        # Don't convert, might be partial
        pass
    else:
        text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)

    # Underline: __text__
    if is_streaming and text.rstrip().endswith('__'):
        pass
    else:
        text = re.sub(r'__([^_]+)__', r'<u>\1</u>', text)

    # Strikethrough: ~~text~~
    if is_streaming and text.rstrip().endswith('~~'):
        pass
    else:
        text = re.sub(r'~~([^~]+)~~', r'<s>\1</s>', text)

    # Italic: *text* (but not ** which is bold)
    if is_streaming and text.rstrip().endswith('*') and not text.rstrip().endswith('**'):
        pass
    else:
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
    Prepare HTML text for Telegram - close unclosed tags.

    Args:
        text: HTML text to prepare
        is_final: If True, this is the final message (no longer used for cursor)
    """
    # Remove incomplete opening tag at the end (e.g. "<b" without ">")
    last_open = text.rfind('<')
    last_close = text.rfind('>')
    if last_open > last_close:
        text = text[:last_open]

    # Close all open tags
    open_tags = get_open_html_tags(text)
    closing_tags = "".join([f"</{tag}>" for tag in reversed(open_tags)])

    return text + closing_tags


class StableHTMLFormatter:
    """
    Stable HTML formatter that ONLY outputs valid HTML.

    Strategy:
    - Find the last stable point in markdown (closed code blocks, paragraphs)
    - Only format and return content up to that stable point
    - Never return partial/broken HTML

    This completely eliminates flickering by only sending valid HTML.
    """

    def __init__(self):
        self._last_sent_html = ""  # Last HTML we actually sent
        self._last_sent_length = 0  # Length of raw text that produced it

    def format(self, raw_text: str, is_final: bool = False) -> tuple[str, bool]:
        """
        Format markdown to valid HTML.

        Args:
            raw_text: Full raw Markdown text
            is_final: Whether this is the final format (force output all)

        Returns:
            Tuple of (html_text, should_update)
            - html_text: Valid HTML string
            - should_update: True if content changed and should be sent
        """
        if not raw_text:
            return "", False

        if is_final:
            # Final - format everything and force close tags
            html_text = markdown_to_html(raw_text, is_streaming=False)
            html_text = prepare_html_for_telegram(html_text, is_final=True)
            changed = html_text != self._last_sent_html
            self._last_sent_html = html_text
            self._last_sent_length = len(raw_text)
            return html_text, changed

        # Find stable boundary - point where all markdown constructs are closed
        stable_end = self._find_stable_end(raw_text)

        if stable_end == 0:
            # Nothing stable yet - return last sent or empty
            return self._last_sent_html, False

        # Only format the stable part
        stable_text = raw_text[:stable_end]

        # Check if we have new stable content
        if stable_end <= self._last_sent_length:
            # No new stable content
            return self._last_sent_html, False

        # Format the stable part
        html_text = markdown_to_html(stable_text, is_streaming=False)
        html_text = prepare_html_for_telegram(html_text, is_final=True)

        # Verify it's valid
        if not self._is_valid_html(html_text):
            # Something went wrong - don't update
            return self._last_sent_html, False

        # Update cache and return
        self._last_sent_html = html_text
        self._last_sent_length = stable_end
        return html_text, True

    def _find_stable_end(self, text: str) -> int:
        """
        Find the end position of stable (complete) content.

        Content is stable when:
        - All code blocks (```) are closed
        - All inline formatting (**bold**, *italic*, `code`) is closed
        - We're at a paragraph boundary (double newline)
        """
        original_text = text

        # Check for unclosed code blocks
        code_fence_count = text.count('```')
        if code_fence_count % 2 != 0:
            # Find last complete code block
            last_open = text.rfind('```')
            # Search backwards for the opening fence
            text = text[:last_open]

        # Find last paragraph boundary (double newline)
        last_para = text.rfind('\n\n')
        if last_para > 0:
            candidate = text[:last_para]
            # Verify all inline markers are paired
            if self._are_markers_paired(candidate):
                return last_para

        # Try to find last complete line
        last_newline = text.rfind('\n')
        if last_newline > 0:
            candidate = text[:last_newline]
            if self._are_markers_paired(candidate):
                return last_newline

        # Check if entire text is stable
        if self._are_markers_paired(text):
            return len(text)

        # FALLBACK: If text is long but we can't find stable point,
        # find ANY newline and use text up to there.
        # This prevents updates from freezing during long unstable content.
        if len(original_text) > 500:
            # Find a newline in the text we've processed
            for i in range(len(text) - 1, 0, -1):
                if text[i] == '\n':
                    # Use content up to this newline
                    return i
            # Last resort: use first 80% of processed text
            if len(text) > 100:
                return int(len(text) * 0.8)

        return 0

    def _are_markers_paired(self, text: str) -> bool:
        """Check that all markdown markers are paired."""
        # Check code blocks
        if text.count('```') % 2 != 0:
            return False

        # For inline markers, we need smarter checking
        # because * can be in text naturally
        markers = ['**', '__', '~~']
        for marker in markers:
            if text.count(marker) % 2 != 0:
                return False

        # Check backticks (but not triple)
        # Remove code blocks first
        text_no_blocks = re.sub(r'```[\s\S]*?```', '', text)
        if text_no_blocks.count('`') % 2 != 0:
            return False

        return True

    def _is_valid_html(self, html_text: str) -> bool:
        """Verify HTML has all tags closed."""
        open_tags = get_open_html_tags(html_text)
        return len(open_tags) == 0

    def reset(self):
        """Reset formatter state for new message."""
        self._last_sent_html = ""
        self._last_sent_length = 0


# Alias for backward compatibility
IncrementalFormatter = StableHTMLFormatter


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
    DEBOUNCE_INTERVAL = 2.0  # Base seconds between updates (increased to avoid rate limits)
    MIN_UPDATE_INTERVAL = 1.5  # Minimum seconds between edits (increased from 0.8)

    # Adaptive interval thresholds (bytes)
    LARGE_TEXT_BYTES = 2000  # >2KB → 3.0s interval (lowered threshold)
    VERY_LARGE_TEXT_BYTES = 4000  # >4KB → 5.0s interval (lowered threshold)

    # Rate limit backoff settings
    MAX_RATE_LIMIT_RETRIES = 3  # Max retries before giving up on update
    RATE_LIMIT_BACKOFF_MULTIPLIER = 1.5  # Multiply retry_after by this

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
        self._status_line = "🤖 <b>Запускаю...</b> ⠋ (0с)"  # Status line shown at bottom (always visible, HTML formatted)
        self._formatter = IncrementalFormatter()  # Anti-flicker formatter
        self._todo_message: Optional[Message] = None  # Separate message for todo list
        self._plan_mode_message: Optional[Message] = None  # Plan mode indicator message
        self._is_plan_mode: bool = False  # Whether Claude is in plan mode

        # Token tracking for context usage display
        self._estimated_tokens: int = 0  # Accumulated token estimate
        self._context_limit: int = context_limit  # Max context window

        # File change tracking for end-of-session summary
        self._file_change_tracker: Optional["FileChangeTracker"] = None

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

    def get_file_tracker(self) -> "FileChangeTracker":
        """Get or create file change tracker for this session."""
        if self._file_change_tracker is None:
            self._file_change_tracker = FileChangeTracker()
        return self._file_change_tracker

    def track_file_change(self, tool_name: str, tool_input: dict) -> None:
        """Track a file-modifying tool use."""
        tracker = self.get_file_tracker()
        tracker.track_tool_use(tool_name, tool_input)

    async def show_file_changes_summary(self) -> Optional[Message]:
        """
        Show summary of all file changes at end of session.

        Sends a separate message with Cursor-style file change summary
        showing all files that were created, edited, or deleted.

        Returns:
            Sent message or None if no changes
        """
        if self._file_change_tracker is None or not self._file_change_tracker.has_changes():
            return None

        summary = self._file_change_tracker.get_summary()
        if not summary:
            return None

        try:
            msg = await self.bot.send_message(
                self.chat_id,
                summary,
                parse_mode="HTML"
            )
            return msg
        except TelegramBadRequest as e:
            logger.warning(f"Failed to send file changes summary: {e}")
            # Try without formatting
            try:
                plain_summary = self._file_change_tracker.get_summary()
                # Strip HTML tags for plain text
                plain_summary = re.sub(r'<[^>]+>', '', plain_summary)
                msg = await self.bot.send_message(
                    self.chat_id,
                    plain_summary,
                    parse_mode=None
                )
                return msg
            except Exception:
                return None
        except Exception as e:
            logger.error(f"Error sending file changes summary: {e}")
            return None

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
        """Set a status line at the bottom of the current message.

        Status is always visible until finalize() is called.
        """
        self._status_line = status
        await self._schedule_update()

    def _get_display_buffer(self) -> str:
        """Get buffer content only (without status).

        Status line is added separately after HTML formatting.
        """
        return self.buffer

    def _get_status_line(self) -> str:
        """Get status line (already HTML formatted).

        Returns empty string if finalized or no status.
        """
        if self.is_finalized or not self._status_line:
            return ""
        return self._status_line

    def _calc_edit_interval(self) -> float:
        """Calculate adaptive edit interval based on buffer size.

        Uses conservative intervals to avoid Telegram rate limits:
        - Small messages (<2KB): 2.0s
        - Medium messages (2-4KB): 3.0s
        - Large messages (>4KB): 5.0s
        """
        try:
            byte_size = len(self.buffer.encode('utf-8'))
        except Exception:
            byte_size = len(self.buffer)

        if byte_size >= self.VERY_LARGE_TEXT_BYTES:
            return 5.0  # Very large messages - update less frequently
        if byte_size >= self.LARGE_TEXT_BYTES:
            return 3.0  # Large messages
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
        """Schedule a debounced update with adaptive interval.

        Uses adaptive intervals based on buffer size to avoid rate limits.
        Logs scheduling decisions for debugging streaming issues.
        """
        async with self._update_lock:
            now = time.time()
            time_since_update = now - self.last_update_time
            interval = self._calc_edit_interval()

            if time_since_update >= interval:
                # Enough time passed, update immediately
                logger.debug(f"Streaming: immediate update (interval={interval:.1f}s, since_last={time_since_update:.1f}s)")
                await self._do_update()
            else:
                # Schedule delayed update if not already pending
                if self._pending_update is None or self._pending_update.done():
                    delay = interval - time_since_update
                    logger.debug(f"Streaming: scheduling update in {delay:.1f}s (interval={interval:.1f}s)")
                    self._pending_update = asyncio.create_task(
                        self._delayed_update(delay)
                    )

    async def _delayed_update(self, delay: float):
        """Wait and then perform update"""
        await asyncio.sleep(delay)
        async with self._update_lock:
            await self._do_update()

    async def _do_update(self, _retry_count: int = 0):
        """Actually perform the update to Telegram.

        Args:
            _retry_count: Internal retry counter for rate limit handling
        """
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
            # Rate limited - use exponential backoff
            if _retry_count >= self.MAX_RATE_LIMIT_RETRIES:
                logger.error(f"Rate limit exceeded {self.MAX_RATE_LIMIT_RETRIES} retries, skipping update")
                return

            # Calculate wait time with backoff multiplier
            wait_time = e.retry_after * self.RATE_LIMIT_BACKOFF_MULTIPLIER
            logger.warning(f"Rate limited (retry {_retry_count + 1}/{self.MAX_RATE_LIMIT_RETRIES}), waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            await self._do_update(_retry_count=_retry_count + 1)

        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                # Same content, ignore
                pass
            elif "message to edit not found" in str(e):
                # Message deleted, send new one
                logger.info("Message was deleted, sending new one")
                await self._send_new_message(display_text)
            else:
                logger.error(f"Telegram error: {e}")

        except Exception as e:
            logger.error(f"Error updating message: {e}")

    async def _edit_current_message(self, text: str, is_final: bool = False):
        """Edit the current message with valid HTML only.

        Uses StableHTMLFormatter to ensure we only send properly closed HTML.
        This prevents flickering from broken/partial tags.
        """
        if not self.current_message:
            return

        # Get status line (already HTML formatted)
        status = self._get_status_line()

        # Use formatter to get valid HTML
        html_text, should_update = self._formatter.format(text, is_final=is_final)

        # Debug logging for troubleshooting frozen updates
        if not should_update and text:
            logger.debug(
                f"Formatter returned should_update=False: "
                f"text_len={len(text)}, html_len={len(html_text)}, "
                f"last_sent_len={self._formatter._last_sent_length}"
            )

        # If formatter has no stable content yet, we still want to show status
        # This ensures the spinner keeps updating even during unstable markdown
        if not should_update and not status:
            return

        # If we got no HTML from formatter but have previous HTML, use that
        # This prevents blank messages when formatter returns empty
        if not html_text and self._formatter._last_sent_html:
            html_text = self._formatter._last_sent_html

        # Add status line
        if status:
            if html_text:
                html_text = f"{html_text}\n\n{status}"
            else:
                html_text = status

        if not html_text:
            return

        try:
            await self.current_message.edit_text(
                html_text,
                parse_mode="HTML",
                reply_markup=self.reply_markup
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                pass  # Same content, ignore
            else:
                # Fallback - strip all HTML and send plain
                plain_text = re.sub(r'<[^>]+>', '', html_text)
                try:
                    await self.current_message.edit_text(
                        plain_text, parse_mode=None, reply_markup=self.reply_markup
                    )
                except Exception:
                    pass  # Give up on this update

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

        # CRITICAL: Reset formatter when buffer is trimmed!
        # Otherwise _last_sent_length stays at old value and formatter
        # thinks there's no new content (stable_end <= _last_sent_length)
        if trimmed:
            self._formatter.reset()
            logger.debug(f"Buffer trimmed to {len(self.buffer)} chars, formatter reset")

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

    Shows elapsed time and current action with animated spinner.
    Updates every second for smooth animation.
    """

    # Braille spinner animation (smooth rotating dots)
    SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # Action-specific emojis (static, one per action)
    ACTION_EMOJIS = {
        "thinking": "🧠",
        "reading": "📖",
        "writing": "✍️",
        "editing": "✏️",
        "searching": "🔎",
        "executing": "⚡",
        "planning": "🎯",
        "analyzing": "🔬",
        "waiting": "⏳",
        "default": "🤖",
    }

    # Action labels in Russian
    ACTION_LABELS = {
        "thinking": "Думаю",
        "reading": "Читаю",
        "writing": "Пишу",
        "editing": "Редактирую",
        "searching": "Ищу",
        "executing": "Выполняю",
        "planning": "Планирую",
        "analyzing": "Анализирую",
        "waiting": "Жду ответа",
        "default": "Работаю",
    }

    def __init__(self, streaming: StreamingHandler, interval: float = 1.0):
        self.streaming = streaming
        self.interval = interval
        self.start_time = time.time()
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._spinner_idx = 0
        self._current_action = "default"
        self._action_detail = ""  # Additional detail like filename

    def set_action(self, action: str, detail: str = ""):
        """Set current action being performed.

        Args:
            action: One of: thinking, reading, writing, editing, searching,
                   executing, planning, analyzing, waiting, default
            detail: Optional detail like filename (will be truncated)
        """
        if action in self.ACTION_EMOJIS:
            self._current_action = action
        else:
            self._current_action = "default"

        # Truncate detail to keep status line short
        if detail:
            if len(detail) > 30:
                detail = "..." + detail[-27:]
            self._action_detail = detail
        else:
            self._action_detail = ""

    async def start(self):
        """Start heartbeat updates"""
        self.is_running = True
        self.start_time = time.time()
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
        """Periodic status update loop - updates every second"""
        while self.is_running:
            try:
                elapsed = int(time.time() - self.start_time)

                # Get animated spinner
                spinner = self.SPINNERS[self._spinner_idx % len(self.SPINNERS)]
                self._spinner_idx += 1

                # Get emoji for current action
                emoji = self.ACTION_EMOJIS.get(self._current_action, "🤖")

                # Format time nicely
                if elapsed < 60:
                    time_str = f"{elapsed}с"
                else:
                    mins = elapsed // 60
                    secs = elapsed % 60
                    time_str = f"{mins}м {secs}с"

                # Get action label
                label = self.ACTION_LABELS.get(self._current_action, "Работаю")

                # Build status line with HTML formatting (stable, no flickering):
                # emoji <b>action</b> spinner (time) <i>detail</i>
                if self._action_detail:
                    status = f"{emoji} <b>{label}</b> {spinner} ({time_str}) · <i>{self._action_detail}</i>"
                else:
                    status = f"{emoji} <b>{label}...</b> {spinner} ({time_str})"

                await self.streaming.set_status(status)
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Heartbeat error: {e}")
                break


@dataclass
class FileChange:
    """Represents a single file change."""
    file_path: str
    action: str  # "create", "edit", "delete"
    lines_added: int = 0
    lines_removed: int = 0


class FileChangeTracker:
    """
    Tracks file changes during a Claude session.

    Monitors Edit, Write, and Bash (for git operations) tool uses
    to build a summary of all modifications.

    Usage:
        tracker = FileChangeTracker()
        tracker.track_tool_use("Edit", {"file_path": "/app/main.py", ...})
        tracker.track_tool_result("Edit", "...edited 5 lines...")
        summary = tracker.get_summary()
    """

    def __init__(self):
        self._changes: dict[str, FileChange] = {}  # file_path -> FileChange
        self._current_tool: Optional[str] = None
        self._current_file: Optional[str] = None

    def track_tool_use(self, tool_name: str, tool_input: dict) -> None:
        """
        Track a tool use event.

        Args:
            tool_name: Name of the tool (Edit, Write, Bash, etc.)
            tool_input: Tool input parameters
        """
        tool_lower = tool_name.lower()
        self._current_tool = tool_lower

        if tool_lower == "write":
            file_path = tool_input.get("file_path", "")
            if file_path:
                self._current_file = file_path
                content = tool_input.get("content", "")
                lines = content.count('\n') + 1 if content else 0

                # Check if file exists (new or overwrite)
                if file_path in self._changes:
                    # Overwriting existing tracked file
                    self._changes[file_path].lines_added += lines
                    self._changes[file_path].action = "edit"
                else:
                    self._changes[file_path] = FileChange(
                        file_path=file_path,
                        action="create",
                        lines_added=lines,
                        lines_removed=0
                    )

        elif tool_lower == "edit":
            file_path = tool_input.get("file_path", "")
            if file_path:
                self._current_file = file_path
                old_string = tool_input.get("old_string", "")
                new_string = tool_input.get("new_string", "")

                old_lines = old_string.count('\n') + 1 if old_string else 0
                new_lines = new_string.count('\n') + 1 if new_string else 0

                if file_path in self._changes:
                    self._changes[file_path].lines_added += new_lines
                    self._changes[file_path].lines_removed += old_lines
                else:
                    self._changes[file_path] = FileChange(
                        file_path=file_path,
                        action="edit",
                        lines_added=new_lines,
                        lines_removed=old_lines
                    )

        elif tool_lower == "bash":
            command = tool_input.get("command", "")
            # Track git-related commands
            if "git add" in command or "git commit" in command:
                # Git operations are tracked but don't count as file changes
                pass
            elif "rm " in command or "del " in command:
                # Try to extract file path from delete commands
                import shlex
                try:
                    parts = shlex.split(command)
                    for i, part in enumerate(parts):
                        if part in ("rm", "del") and i + 1 < len(parts):
                            file_path = parts[i + 1]
                            if not file_path.startswith("-"):
                                self._changes[file_path] = FileChange(
                                    file_path=file_path,
                                    action="delete",
                                    lines_added=0,
                                    lines_removed=0
                                )
                except Exception:
                    pass

    def track_tool_result(self, tool_name: str, output: str) -> None:
        """
        Track a tool result to update change statistics.

        Args:
            tool_name: Name of the tool
            output: Tool output/result
        """
        # Could parse output for more accurate line counts
        # For now, we rely on input-based tracking
        self._current_tool = None
        self._current_file = None

    def get_changes(self) -> list[FileChange]:
        """Get list of all tracked changes."""
        return list(self._changes.values())

    def get_summary(self) -> str:
        """
        Generate a Cursor-style summary of file changes.

        Returns:
            Formatted summary string with file changes
        """
        if not self._changes:
            return ""

        lines = ["📊 <b>Изменённые файлы:</b>\n"]

        total_added = 0
        total_removed = 0

        # Sort by action: creates first, then edits, then deletes
        action_order = {"create": 0, "edit": 1, "delete": 2}
        sorted_changes = sorted(
            self._changes.values(),
            key=lambda c: (action_order.get(c.action, 1), c.file_path)
        )

        for change in sorted_changes:
            # Get just the filename for display
            filename = change.file_path.split("/")[-1].split("\\")[-1]

            # Action emoji
            if change.action == "create":
                action_emoji = "✨"
            elif change.action == "delete":
                action_emoji = "🗑️"
            else:
                action_emoji = "📝"

            # Format line changes
            changes_str = ""
            if change.lines_added > 0:
                changes_str += f"<code>+{change.lines_added}</code>"
                total_added += change.lines_added
            if change.lines_removed > 0:
                if changes_str:
                    changes_str += " "
                changes_str += f"<code>-{change.lines_removed}</code>"
                total_removed += change.lines_removed

            if changes_str:
                lines.append(f"  {action_emoji} <code>{filename}</code> {changes_str}")
            else:
                lines.append(f"  {action_emoji} <code>{filename}</code>")

        # Total summary
        if total_added > 0 or total_removed > 0:
            total_str = ""
            if total_added > 0:
                total_str += f"<code>+{total_added}</code>"
            if total_removed > 0:
                if total_str:
                    total_str += " "
                total_str += f"<code>-{total_removed}</code>"
            lines.append(f"\n<i>Итого: {len(self._changes)} файл(ов), {total_str}</i>")

        return "\n".join(lines)

    def has_changes(self) -> bool:
        """Check if any changes were tracked."""
        return len(self._changes) > 0

    def reset(self) -> None:
        """Clear all tracked changes."""
        self._changes.clear()
        self._current_tool = None
        self._current_file = None
