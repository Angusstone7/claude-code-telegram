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
from typing import List, Optional, Dict
from enum import Enum
import html as html_module


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
    """
    # Main content (Claude's text response)
    content: str = ""

    # List of tool executions
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

    def render(self) -> str:
        """
        Render the complete UI state to HTML.

        Order:
        1. Main content
        2. Thinking blocks
        3. Current thinking buffer
        4. Tool statuses
        5. Status line
        """
        parts = []

        # 1. Main content (with markdown to HTML conversion)
        if self.content:
            # Import here to avoid circular imports
            from presentation.handlers.streaming import markdown_to_html, prepare_html_for_telegram
            html_content = markdown_to_html(self.content, is_streaming=not self.finalized)
            html_content = prepare_html_for_telegram(html_content, is_final=self.finalized)
            if html_content:
                parts.append(html_content)

        # Add non-content components
        non_content = self.render_non_content()
        if non_content:
            parts.append(non_content)

        # Status line is handled separately in StreamingHandler
        return "\n\n".join(parts)

    def render_non_content(self) -> str:
        """
        Render only tools and thinking (no content).

        Used by StreamingHandler to append to formatted content.
        Returns HTML ready for Telegram.

        Order:
        1. Thinking blocks
        2. Current thinking buffer
        3. Tool statuses
        4. Completion info (cost, tokens) - AT THE BOTTOM
        5. Completion status (✅ Готово) - AT THE VERY BOTTOM
        """
        parts = []

        # 1. Thinking blocks
        for block in self.thinking:
            parts.append(block.render())

        # 2. Current thinking buffer (if any)
        if self.thinking_buffer:
            display = self.thinking_buffer[:800]
            if len(self.thinking_buffer) > 800:
                display += "..."
            escaped = html_module.escape(display)
            parts.append(f"💭 <i>{escaped}</i>")

        # 3. Tool statuses
        for tool in self.tools:
            parts.append(tool.render())

        # 4. Completion info (cost, tokens) - at the bottom
        if self.completion_info:
            parts.append(self.completion_info)

        # 5. Completion status (✅ Готово) - at the very bottom
        if self.completion_status:
            parts.append(self.completion_status)

        return "\n\n".join(parts)

    # === API for updating state ===

    def append_content(self, text: str) -> None:
        """Append text to main content"""
        self.content += text

    def set_content(self, text: str) -> None:
        """Set main content (replaces existing)"""
        self.content = text

    def add_tool(self, name: str, detail: str = "", status: ToolStatus = ToolStatus.EXECUTING) -> ToolState:
        """
        Add a new tool to the list.

        Returns the created ToolState for further modification.
        """
        tool = ToolState(
            id=f"tool_{len(self.tools)}",
            name=name.lower(),
            status=status,
            detail=detail
        )
        self.tools.append(tool)
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
        self.content = ""
        self.tools = []
        self.thinking = []
        self.thinking_buffer = ""
        self.status_line = ""
        self.completion_info = ""
        self.completion_status = ""
        self.finalized = False

    def finalize(self) -> None:
        """Mark message as finalized"""
        self.finalized = True
        # Flush any remaining thinking
        if self.thinking_buffer:
            self._flush_thinking_buffer(collapsed=True)
