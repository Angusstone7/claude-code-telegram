"""
Step-by-step streaming handler for Claude tool operations.

Shows brief status of each tool step without code details:
- Tool name and file (icon changes: ⏳ → 🔧 → ✅)
- Change summary (+5 -3 lines)
- Claude thinking in collapsible blocks 💭
"""

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from presentation.handlers.streaming.handler import StreamingHandler

logger = logging.getLogger(__name__)


class StepStreamingHandler:
    """
    Обёртка для краткого стриминга шагов без кода.

    РЕФАКТОРИНГ: Использует StreamingUIState для управления UI.
    Вместо строковых манипуляций (rfind/replace) - структурированное состояние.

    Показывает:
    - Название операции и файл (иконка меняется: ⏳ → 🔧 → ✅)
    - Сводку изменений (+5 -3 lines)
    - Рассуждения Claude в сворачиваемых блоках 💭
    """

    def __init__(self, base: "StreamingHandler"):
        self.base = base
        self._last_message_index: int = 1
        self._current_tool_input: dict = {}  # Для file tracker

    async def on_permission_request(self, tool_name: str, tool_input: dict) -> None:
        """Показать что ожидается разрешение на инструмент."""
        logger.debug(f"StepStreaming: on_permission_request({tool_name})")

        await self._check_message_transition()

        # Сворачиваем thinking блоки
        self.base.ui.collapse_all_thinking()

        from presentation.handlers.streaming_ui import ToolStatus
        detail = self._extract_detail(tool_name.lower(), tool_input)

        # ВАЖНО: on_tool_start может быть вызван ДО on_permission_request!
        # Если уже есть EXECUTING tool - не добавляем PENDING (он уже в работе)
        if self.base.ui.find_executing_tool(tool_name):
            logger.debug(f"StepStreaming: skip PENDING, already have EXECUTING for {tool_name}")
            return

        # КРИТИЧНО: sync buffer ПЕРЕД add_tool, чтобы flush захватил контент до этого tool
        self.base.ui.sync_from_buffer(self.base.buffer)
        self.base.ui.add_tool(tool_name, detail, ToolStatus.PENDING)

        await self.base._do_update()

    async def on_permission_granted(self, tool_name: str) -> None:
        """Показать что разрешение получено - перевести в EXECUTING."""
        logger.debug(f"StepStreaming: on_permission_granted({tool_name})")

        # Находим pending tool и переводим в executing
        # Если нет PENDING (tool уже EXECUTING от on_tool_start) - это нормально
        if not self.base.ui.update_pending_to_executing(tool_name):
            logger.debug(f"StepStreaming: no PENDING for {tool_name}, already EXECUTING")
            return

        await self.base._do_update()

    async def on_tool_start(self, tool_name: str, tool_input: dict) -> None:
        """Показать что инструмент начал выполняться."""
        logger.debug(f"StepStreaming: on_tool_start({tool_name})")

        await self._check_message_transition()

        # Сворачиваем thinking блоки и прошлый контент
        self.base.ui.collapse_all_thinking()
        self.base.ui.collapse_previous_content()

        # Сохраняем input для file tracker
        self._current_tool_input = tool_input

        from presentation.handlers.streaming_ui import ToolStatus
        detail = self._extract_detail(tool_name.lower(), tool_input)

        # Если есть pending tool - обновить его
        if self.base.ui.update_pending_to_executing(tool_name, detail):
            pass  # Tool уже обновлён (PENDING -> EXECUTING)
        elif self.base.ui.find_executing_tool(tool_name):
            # Уже есть EXECUTING tool (после on_permission_granted) - не добавляем дубль
            pass
        else:
            # Иначе создать новый (YOLO mode без permission request)
            # КРИТИЧНО: sync buffer ПЕРЕД add_tool, чтобы flush захватил контент до этого tool
            self.base.ui.sync_from_buffer(self.base.buffer)
            self.base.ui.add_tool(tool_name, detail, ToolStatus.EXECUTING)

        await self.base._do_update()

    async def on_tool_complete(
        self,
        tool_name: str,
        tool_input: Optional[dict] = None,
        success: bool = True
    ) -> None:
        """Завершить инструмент - показать ✅ или ❌."""
        logger.debug(f"StepStreaming: on_tool_complete({tool_name}, success={success})")

        await self._check_message_transition()

        # Use saved tool_input if not provided
        if tool_input is None:
            tool_input = self._current_tool_input

        # Для файловых операций - получить +/- строк
        change_info = ""
        tool_lower = tool_name.lower() if tool_name else ""
        if tool_lower in ("write", "edit") and tool_input:
            tracker = self.base.get_file_tracker()
            file_path = tool_input.get("file_path", "")
            changes = tracker._changes.get(file_path)
            if changes:
                parts = []
                if changes.lines_added > 0:
                    parts.append(f"+{changes.lines_added}")
                if changes.lines_removed > 0:
                    parts.append(f"-{changes.lines_removed}")
                if parts:
                    change_info = f"{' '.join(parts)} lines"

        # Завершаем tool
        self.base.ui.complete_tool(tool_name, success, change_info=change_info)

        # Добавляем детальную информацию в output
        detail_block = self._get_detail_block(tool_lower, tool_input or {})
        if detail_block:
            # Найти tool и добавить output
            tool = self.base.ui.find_executing_tool(tool_name)
            if not tool:
                # Tool уже completed - найти последний completed
                for t in reversed(self.base.ui.tools):
                    if t.name == tool_lower:
                        t.output = detail_block
                        break

        # Сбросить состояние
        self._current_tool_input = {}

        await self.base._do_update()

    async def on_thinking(self, text: str) -> None:
        """Добавить текст в thinking."""
        if not text:
            return

        await self._check_message_transition()

        # Добавляем в UI state - он сам решает когда показать блок
        self.base.ui.add_thinking(text)

        await self.base._do_update()

    def _extract_detail(self, tool_name: str, tool_input: dict) -> str:
        """Извлечь краткую деталь (имя файла, команду)."""
        if tool_name in ("read", "write", "edit", "notebookedit"):
            path = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
            return path.split("/")[-1] if path else ""
        elif tool_name == "bash":
            cmd = tool_input.get("command", "")
            first_word = cmd.split()[0] if cmd.split() else ""
            return first_word[:20] if first_word else ""
        elif tool_name in ("glob", "grep"):
            return tool_input.get("pattern", "")[:25]
        elif tool_name in ("webfetch", "websearch"):
            url_or_query = tool_input.get("url", "") or tool_input.get("query", "")
            return url_or_query[:30] if url_or_query else ""
        return ""

    def _get_detail_block(self, tool_name: str, tool_input: dict) -> str:
        """Получить детальную информацию для блока кода под операцией."""
        if tool_name == "bash":
            cmd = tool_input.get("command", "")
            if cmd:
                if len(cmd) > 150:
                    return cmd[:147] + "..."
                return cmd
        elif tool_name in ("read", "write", "edit", "notebookedit"):
            path = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
            return path or ""
        elif tool_name in ("glob", "grep"):
            pattern = tool_input.get("pattern", "")
            path = tool_input.get("path", "")
            if pattern:
                return f"{pattern} in {path}" if path else pattern
        elif tool_name in ("webfetch", "websearch"):
            return tool_input.get("url", "") or tool_input.get("query", "")
        return ""

    def get_current_tool(self) -> str:
        """Get name of currently executing tool."""
        tool = self.base.ui.get_current_tool()
        return tool.name if tool else ""

    def get_current_tool_input(self) -> dict:
        """Get input of currently executing tool."""
        return self._current_tool_input

    async def _check_message_transition(self) -> None:
        """Проверить переход на новое сообщение."""
        current_index = self.base._message_index
        if current_index != self._last_message_index:
            logger.debug(f"Message transition: {self._last_message_index} -> {current_index}")

            # Сбрасываем UI state для нового сообщения
            self.base.ui.reset()

            self._last_message_index = current_index
