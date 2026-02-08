"""
Markdown to HTML formatting for Telegram streaming.

Handles real-time formatting of Claude Code output with:
- Placeholder protection for code blocks
- Streaming-aware partial markdown handling
- Tag closure for valid Telegram HTML
"""

import html as html_module
import logging
import re

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
        # Use Unicode Private Use Area characters as the ENTIRE placeholder
        # U+E000 to U+F8FF is the Private Use Area - never in normal text
        # Each placeholder is a single unique PUA character: U+E000 + index
        # This avoids any text that could accidentally match
        return chr(0xE000 + index)

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

        # Escape code content - only escape <, >, & (not quotes, they display as &quot; in Telegram)
        escaped_code = code_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
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
        # Escape only <, >, & (not quotes, they display as &quot; in Telegram)
        escaped_code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
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
        # Escape only <, >, & (not quotes, they display as &quot; in Telegram)
        code = m.group(1)
        escaped_code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        placeholders.append(f'<code>{escaped_code}</code>')
        return key

    text = re.sub(r'`([^`\n]+)`', protect_inline_code, text)

    # 3.5. Protect blockquote tags (expandable quotes for thinking blocks)
    # Handle both closed and unclosed blockquotes (for streaming)
    unclosed_blockquote_placeholder = None

    def protect_blockquote(m: re.Match) -> str:
        key = get_placeholder(len(placeholders))
        tag_attrs = m.group(1) or ""
        content = m.group(2)
        # Don't escape - preserve placeholders and already-escaped content
        placeholders.append(f'<blockquote{tag_attrs}>{content}</blockquote>')
        return key

    # First, handle closed blockquotes
    text = re.sub(r'<blockquote([^>]*)>(.*?)</blockquote>', protect_blockquote, text, flags=re.DOTALL)

    # Handle UNCLOSED blockquote (for streaming) - similar to code blocks
    if is_streaming and '<blockquote' in text:
        # Find unclosed blockquote - has opening tag but no closing
        unclosed_match = re.search(r'<blockquote([^>]*)>([^<]*(?:<(?!/blockquote>)[^<]*)*)$', text, flags=re.DOTALL)
        if unclosed_match:
            # Temporarily close it for display, will be fixed on next update
            unclosed_blockquote_placeholder = get_placeholder(len(placeholders))
            tag_attrs = unclosed_match.group(1) or ""
            content = unclosed_match.group(2)
            # Store with closing tag for display
            placeholders.append(f'<blockquote{tag_attrs}>{content}</blockquote>')
            text = text[:unclosed_match.start()] + unclosed_blockquote_placeholder

    # 3.6. Protect other HTML tags that we generate ourselves (b, i, code, pre, s, u)
    # These come from our own formatting and should not be escaped
    def protect_html_tag(m: re.Match) -> str:
        key = get_placeholder(len(placeholders))
        placeholders.append(m.group(0))  # Keep the whole tag as-is
        return key

    # Protect paired tags: <b>...</b>, <i>...</i>, <code>...</code>, <pre>...</pre>, <s>...</s>, <u>...</u>
    text = re.sub(r'<(b|i|code|pre|s|u)>([^<]*)</\1>', protect_html_tag, text)

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

    # Links: [text](url) → <a href="url">text</a>
    # Note: text and url are already HTML-escaped at this point
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2">\1</a>',
        text
    )

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

        КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ: Всегда форматирует ВЕСЬ текст!
        - НЕ использует _find_stable_end() - это блокировало обновления
        - markdown_to_html(is_streaming=True) сам обрабатывает незакрытые конструкции
        - Координатор решает когда обновлять Telegram (каждые 2 сек)

        Args:
            raw_text: Full raw Markdown text
            is_final: Whether this is the final format

        Returns:
            Tuple of (html_text, changed)
            - html_text: Valid HTML string
            - changed: True if content changed since last call
        """
        if not raw_text:
            return "", False

        # КРИТИЧЕСКИЙ ФИКС: Всегда форматировать ВЕСЬ текст!
        # is_streaming=True позволяет обрабатывать незакрытые конструкции
        html_text = markdown_to_html(raw_text, is_streaming=not is_final)
        html_text = prepare_html_for_telegram(html_text, is_final=is_final)

        # Check if content changed
        changed = html_text != self._last_sent_html

        # Update cache
        self._last_sent_html = html_text

        return html_text, changed

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

        # FALLBACK: If we can't find a stable point, still show something
        # to prevent the UI from appearing frozen.
        # Priority: find any newline, then use 80% of text, then use all

        # Try to find any newline in the processed text
        for i in range(len(text) - 1, 0, -1):
            if text[i] == '\n':
                return i

        # No newlines - use 80% of text if it's long enough
        if len(text) > 50:
            return int(len(text) * 0.8)

        # For very short text, just return everything
        # Better to show something than nothing!
        if len(text) > 10:
            return len(text)

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
