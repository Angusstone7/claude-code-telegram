"""
Streaming UI Components

Component-based architecture for dynamic Telegram message UI.
Instead of string manipulation (rfind + replace), we use structured state
that renders to HTML deterministically.

State → Render → HTML → Telegram

Key benefits:
- In-place updates always work (no string matching issues)
- Clear state management (not hidden in buffer string)
- Easy to debug and test
- Extensible for new UI components
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Union
from enum import Enum
import html as html_module


class ElementType(Enum):
    """Type of UI element in the streaming message"""
    CONTENT = "content"  # Text content block
    TOOL = "tool"        # Tool execution status


@dataclass
class UIElement:
    """A single element in the streaming message (content or tool)"""
    type: ElementType
    data: Union[str, "ToolState"]  # str for CONTENT, ToolState for TOOL


class ToolStatus(Enum):
    """Status of a tool execution"""
    PENDING = "pending"      # ⏳ Waiting for permission
    EXECUTING = "executing"  # 🔧 In progress
    COMPLETED = "completed"  # ✅ Done
    ERROR = "error"          # ❌ Failed


# Tool icons for each type
TOOL_ICONS = {
    "bash": "🔧",
    "write": "📝",
    "edit": "✏️",
    "read": "📖",
    "glob": "🔍",
    "grep": "🔎",
    "webfetch": "🌐",
    "websearch": "🔎",
    "task": "🤖",
    "notebookedit": "📓",
}

# Tool action labels (executing, completed)
TOOL_ACTIONS = {
    "bash": ("Выполняю", "Выполнено"),
    "write": ("Записываю", "Записано"),
    "edit": ("Редактирую", "Отредактировано"),
    "read": ("Читаю", "Прочитано"),
    "glob": ("Ищу файлы", "Найдено"),
    "grep": ("Ищу в коде", "Найдено"),
    "webfetch": ("Загружаю", "Загружено"),
    "websearch": ("Ищу в сети", "Найдено"),
    "task": ("Запускаю агента", "Агент завершил"),
    "notebookedit": ("Редактирую notebook", "Notebook отредактирован"),
}


@dataclass
class ToolState:
    """State of a single tool execution"""
    id: str                    # Unique ID (e.g., "tool_0", "tool_1")
    name: str                  # Tool name (bash, read, write, etc.)
    status: ToolStatus         # Current status
    detail: str = ""           # Short detail (filename, command)
    output: str = ""           # Output for code block (optional)
    change_info: str = ""      # e.g., "+5 -3 lines"

    def render(self) -> str:
        """Render tool state to HTML"""
        # Get icon based on status
        if self.status == ToolStatus.PENDING:
            icon = "⏳"
        elif self.status == ToolStatus.EXECUTING:
            icon = TOOL_ICONS.get(self.name, "⏳")
        elif self.status == ToolStatus.COMPLETED:
            icon = "✅"
        else:  # ERROR
            icon = "❌"

        # Get action label
        actions = TOOL_ACTIONS.get(self.name, ("Обработка", "Готово"))
        if self.status == ToolStatus.PENDING:
            label = f"Ожидаю разрешение: `{self.name}`"
        elif self.status == ToolStatus.EXECUTING:
            label = actions[0]
        else:  # COMPLETED or ERROR
            label = actions[1]

        # Build the line
        if self.detail:
            line = f"{icon} {label} `{self.detail}`"
        else:
            line = f"{icon} {label}"

        # Add ellipsis for executing
        if self.status == ToolStatus.EXECUTING:
            line += "..."

        # Add change info if present
        if self.change_info and self.status == ToolStatus.COMPLETED:
            line += f" ({self.change_info})"

        # Add output in code block if present
        if self.output and self.status == ToolStatus.COMPLETED:
            # Escape and limit output
            escaped_output = html_module.escape(self.output[:500])
            if len(self.output) > 500:
                escaped_output += "..."
            line += f"\n<pre>{escaped_output}</pre>"

        return line


@dataclass
class ThinkingBlock:
    """A block of Claude's thinking/reasoning"""
    id: str                    # Unique ID (e.g., "thinking_0")
    content: str               # The thinking text
    collapsed: bool = False    # Whether to show as expandable blockquote

    def render(self) -> str:
        """Render thinking block to HTML"""
        # Escape content for HTML
        escaped = html_module.escape(self.content)

        if self.collapsed:
            return f"<blockquote expandable>💭 {escaped}</blockquote>"
        else:
            return f"💭 <i>{escaped}</i>"


@dataclass
class StreamingUIState:
    """
    Complete UI state for a streaming message.

    This is the single source of truth for what should be displayed.
    Call render() to get the HTML representation.

    Key design: elements list maintains order of content and tools.
    When a tool is added, accumulated content is flushed first.
    This ensures correct interleaving: content → tool → content → tool
    """
    # Unified list of elements in order of addition
    elements: List[UIElement] = field(default_factory=list)

    # Buffer for accumulating content (flushed when tool is added)
    _content_buffer: str = ""

    # Track how much of external buffer was already flushed to elements
    _flushed_length: int = 0

    # List of tools (for lookup by name - elements also has them)
    tools: List[ToolState] = field(default_factory=list)

    # Thinking blocks (completed)
    thinking: List[ThinkingBlock] = field(default_factory=list)

    # Buffer for accumulating thinking text
    thinking_buffer: str = ""

    # Status line at the bottom
    status_line: str = ""

    # Completion info (cost, tokens) - shown at the very bottom
    completion_info: str = ""  # e.g., "$0.0978 | ~5K токенов"

    # Completion status - shown after completion_info
    completion_status: str = ""  # e.g., "✅ Готово"

    # Whether the message is finalized
    finalized: bool = False

    # Legacy: keep content for backward compatibility
    @property
    def content(self) -> str:
        """Get all content (for backward compatibility)"""
        content_parts = []
        for element in self.elements:
            if element.type == ElementType.CONTENT:
                content_parts.append(element.data)
        if self._content_buffer:
            content_parts.append(self._content_buffer)
        return "".join(content_parts)

    def _flush_content_buffer(self) -> None:
        """Save accumulated content as an element."""
        if self._content_buffer.strip():
            self.elements.append(UIElement(
                type=ElementType.CONTENT,
                data=self._content_buffer
            ))
        # Track how much we've flushed for sync_from_buffer
        self._flushed_length += len(self._content_buffer)
        self._content_buffer = ""

    def render(self) -> str:
        """
        Render the complete UI state to HTML.

        Order (interleaved):
        1. Thinking blocks
        2. Elements in order (content and tools interleaved)
        3. Current content buffer (not yet flushed)
        4. Completion info/status
        """
        # Use render_non_content which now handles everything
        return self.render_non_content()

    def render_non_content(self) -> str:
        """
        Render all UI elements in correct order (interleaved).

        Order:
        1. Thinking blocks (at the top)
        2. Current thinking buffer
        3. Elements in order of addition (CONTENT and TOOL interleaved)
        4. Current content buffer (not yet flushed)
        5. Completion info (cost, tokens) - AT THE BOTTOM
        6. Completion status (✅ Готово) - AT THE VERY BOTTOM
        """
        parts = []

        # 1. Thinking blocks (at the top)
        for block in self.thinking:
            parts.append(block.render())

        # 2. Current thinking buffer (if any)
        if self.thinking_buffer:
            display = self.thinking_buffer[:800]
            if len(self.thinking_buffer) > 800:
                display += "..."
            escaped = html_module.escape(display)
            parts.append(f"💭 <i>{escaped}</i>")

        # 3. Elements in order of addition (CONTENT and TOOL interleaved)
        from presentation.handlers.streaming import markdown_to_html, prepare_html_for_telegram
        for element in self.elements:
            if element.type == ElementType.CONTENT:
                # Format content block
                html = markdown_to_html(element.data, is_streaming=not self.finalized)
                html = prepare_html_for_telegram(html, is_final=self.finalized)
                if html:
                    parts.append(html)
            elif element.type == ElementType.TOOL:
                # Render tool status
                parts.append(element.data.render())

        # 4. Current content buffer (not yet flushed, still streaming)
        if self._content_buffer:
            html = markdown_to_html(self._content_buffer, is_streaming=True)
            html = prepare_html_for_telegram(html, is_final=False)
            if html:
                parts.append(html)

        # 5. Completion info (cost, tokens) - at the bottom
        if self.completion_info:
            parts.append(self.completion_info)

        # 6. Completion status (✅ Готово) - at the very bottom
        if self.completion_status:
            parts.append(self.completion_status)

        return "\n\n".join(parts)

    # === API for updating state ===

    def append_content(self, text: str) -> None:
        """Append text to content buffer (will be flushed when tool is added)"""
        self._content_buffer += text

    def set_content(self, text: str) -> None:
        """Set content buffer (replaces existing buffer, not flushed elements)"""
        self._content_buffer = text

    def sync_from_buffer(self, full_buffer: str) -> None:
        """
        Sync content buffer from external buffer (e.g., StreamingHandler.buffer).

        Only takes the NEW part that hasn't been flushed to elements yet.
        This prevents duplication when tool flushes part of content.
        """
        # Only sync the part after what was already flushed
        if len(full_buffer) > self._flushed_length:
            self._content_buffer = full_buffer[self._flushed_length:]
        else:
            self._content_buffer = ""

    def add_tool(self, name: str, detail: str = "", status: ToolStatus = ToolStatus.EXECUTING) -> ToolState:
        """
        Add a new tool to the list.

        IMPORTANT: This flushes the content buffer first, ensuring correct order:
        content → tool → content → tool

        Returns the created ToolState for further modification.
        """
        # Flush accumulated content BEFORE adding tool
        self._flush_content_buffer()

        # Create tool
        tool = ToolState(
            id=f"tool_{len(self.tools)}",
            name=name.lower(),
            status=status,
            detail=detail
        )
        self.tools.append(tool)

        # Add to elements for correct ordering
        self.elements.append(UIElement(
            type=ElementType.TOOL,
            data=tool
        ))

        return tool

    def get_current_tool(self) -> Optional[ToolState]:
        """Get the most recent tool (for updates)"""
        if self.tools:
            return self.tools[-1]
        return None

    def find_executing_tool(self, name: str) -> Optional[ToolState]:
        """Find the last executing tool with given name"""
        name_lower = name.lower()
        for tool in reversed(self.tools):
            if tool.name == name_lower and tool.status == ToolStatus.EXECUTING:
                return tool
        return None

    def find_pending_tool(self, name: str) -> Optional[ToolState]:
        """Find the last pending tool with given name"""
        name_lower = name.lower()
        for tool in reversed(self.tools):
            if tool.name == name_lower and tool.status == ToolStatus.PENDING:
                return tool
        return None

    def update_pending_to_executing(self, name: str, detail: str = "") -> bool:
        """Update a pending tool to executing status"""
        tool = self.find_pending_tool(name)
        if tool:
            tool.status = ToolStatus.EXECUTING
            if detail:
                tool.detail = detail
            return True
        return False

    def complete_tool(self, name: str, success: bool = True, output: str = "", change_info: str = "") -> bool:
        """
        Complete the last executing tool with given name.

        Returns True if a tool was found and updated.
        """
        tool = self.find_executing_tool(name)
        if tool:
            tool.status = ToolStatus.COMPLETED if success else ToolStatus.ERROR
            if output:
                tool.output = output
            if change_info:
                tool.change_info = change_info
            return True
        return False

    def add_thinking(self, text: str) -> None:
        """
        Add text to thinking buffer.

        Automatically creates a block when buffer reaches threshold.
        """
        self.thinking_buffer += text

        # Check if we should create a block
        should_create_block = (
            len(self.thinking_buffer) >= 100 or
            '\n' in text or
            self.thinking_buffer.rstrip().endswith(('.', '!', '?', ':'))
        )

        if should_create_block:
            self._flush_thinking_buffer(collapsed=False)

    def _flush_thinking_buffer(self, collapsed: bool = False) -> None:
        """Convert thinking buffer to a block"""
        if not self.thinking_buffer:
            return

        # Collapse previous block if exists
        if self.thinking:
            self.thinking[-1].collapsed = True

        # Create new block
        content = self.thinking_buffer[:800]
        if len(self.thinking_buffer) > 800:
            content += "..."

        block = ThinkingBlock(
            id=f"thinking_{len(self.thinking)}",
            content=content,
            collapsed=collapsed
        )
        self.thinking.append(block)
        self.thinking_buffer = ""

    def collapse_all_thinking(self) -> None:
        """
        Collapse all thinking blocks.

        Called before showing tool output to keep UI clean.
        """
        # Collapse existing blocks
        for block in self.thinking:
            block.collapsed = True

        # Flush buffer as collapsed
        if self.thinking_buffer:
            self._flush_thinking_buffer(collapsed=True)

    def set_status(self, status: str) -> None:
        """Set the status line"""
        self.status_line = status

    def clear_status(self) -> None:
        """Clear the status line"""
        self.status_line = ""

    def set_completion_info(self, info: str) -> None:
        """Set completion info (cost, tokens) - shown at the bottom"""
        self.completion_info = info

    def set_completion_status(self, status: str) -> None:
        """Set completion status (✅ Готово) - shown at the very bottom"""
        self.completion_status = status

    def reset(self) -> None:
        """Reset state for new message"""
        self.elements = []
        self._content_buffer = ""
        self._flushed_length = 0
        self.tools = []
        self.thinking = []
        self.thinking_buffer = ""
        self.status_line = ""
        self.completion_info = ""
        self.completion_status = ""
        self.finalized = False

    def finalize(self) -> None:
        """Mark message as finalized"""
        # Flush remaining content buffer
        self._flush_content_buffer()

        self.finalized = True
        # Flush any remaining thinking
        if self.thinking_buffer:
            self._flush_thinking_buffer(collapsed=True)
