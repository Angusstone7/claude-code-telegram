"""
Tool Response Formatters (Strategy Pattern)

Replaces the giant if-elif chain in _format_tool_response()
with extensible Strategy pattern (fixes Open/Closed Principle violation).

Each tool has its own formatter class that knows how to format
its responses. New tools can be added without modifying existing code.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ToolResponseFormatter(ABC):
    """
    Abstract base class for tool response formatters.

    Each tool type implements its own formatting logic.
    """

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Name of the tool this formatter handles (lowercase)"""
        pass

    @abstractmethod
    def format(self, response: Any, max_length: int = 500) -> str:
        """
        Format the tool response for display.

        Args:
            response: Raw response from the tool (dict, str, or other)
            max_length: Maximum length of formatted output

        Returns:
            Formatted string for display
        """
        pass


class GlobFormatter(ToolResponseFormatter):
    """Formatter for Glob tool responses"""

    @property
    def tool_name(self) -> str:
        return "glob"

    def format(self, response: Any, max_length: int = 500) -> str:
        if not isinstance(response, dict):
            return str(response)[:max_length]

        files = response.get("filenames", [])
        if not files:
            return "Файлов не найдено"

        file_list = "\n".join(f"  {f}" for f in files[:20])
        if len(files) > 20:
            file_list += f"\n  ... и ещё {len(files) - 20} файлов"
        return f"Найдено {len(files)} файлов:\n{file_list}"


class ReadFormatter(ToolResponseFormatter):
    """Formatter for Read tool responses"""

    @property
    def tool_name(self) -> str:
        return "read"

    def format(self, response: Any, max_length: int = 500) -> str:
        if not isinstance(response, dict):
            return str(response)[:max_length]

        file_info = response.get("file", {})
        content = file_info.get("content", "")
        path = file_info.get("filePath", "")

        if content:
            truncated = content[:max_length]
            if len(content) > max_length:
                truncated += "\n... (обрезано)"
            return truncated
        return f"Файл прочитан: {path}"


class GrepFormatter(ToolResponseFormatter):
    """Formatter for Grep tool responses"""

    @property
    def tool_name(self) -> str:
        return "grep"

    def format(self, response: Any, max_length: int = 500) -> str:
        if not isinstance(response, dict):
            return str(response)[:max_length]

        matches = response.get("matches", [])
        if not matches:
            return "Совпадений не найдено"
        return f"Найдено {len(matches)} совпадений"


class BashFormatter(ToolResponseFormatter):
    """Formatter for Bash tool responses"""

    @property
    def tool_name(self) -> str:
        return "bash"

    def format(self, response: Any, max_length: int = 500) -> str:
        if isinstance(response, dict):
            output = response.get("output", response.get("stdout", ""))
            if output:
                return str(output)[:max_length]
            stderr = response.get("stderr", "")
            if stderr:
                return f"stderr: {stderr[:max_length]}"
            return str(response)[:max_length]
        return str(response)[:max_length]


class WriteFormatter(ToolResponseFormatter):
    """Formatter for Write tool responses"""

    @property
    def tool_name(self) -> str:
        return "write"

    def format(self, response: Any, max_length: int = 500) -> str:
        if isinstance(response, dict):
            path = response.get("file_path", response.get("path", ""))
            if path:
                return f"Файл записан: {path}"
        return "Файл записан"


class EditFormatter(ToolResponseFormatter):
    """Formatter for Edit tool responses"""

    @property
    def tool_name(self) -> str:
        return "edit"

    def format(self, response: Any, max_length: int = 500) -> str:
        if isinstance(response, dict):
            path = response.get("file_path", response.get("path", ""))
            if path:
                return f"Файл изменён: {path}"
        return "Файл изменён"


class DefaultFormatter(ToolResponseFormatter):
    """Default formatter for unknown tools"""

    @property
    def tool_name(self) -> str:
        return "default"

    def format(self, response: Any, max_length: int = 500) -> str:
        if not response:
            return ""

        if isinstance(response, dict):
            # Try to extract useful info
            if "content" in response:
                return str(response["content"])[:max_length]
            if "output" in response:
                return str(response["output"])[:max_length]
            if "result" in response:
                return str(response["result"])[:max_length]

            # Skip technical dicts with only metadata
            if set(response.keys()) <= {"durationMs", "numFiles", "truncated", "type"}:
                return ""

        return str(response)[:max_length]


class FormatterRegistry:
    """
    Registry of tool response formatters.

    Use this to get the appropriate formatter for a tool,
    or register new formatters.
    """

    def __init__(self):
        self._formatters: Dict[str, ToolResponseFormatter] = {}
        self._default = DefaultFormatter()

        # Register built-in formatters
        self._register_builtin()

    def _register_builtin(self) -> None:
        """Register built-in formatters"""
        for formatter in [
            GlobFormatter(),
            ReadFormatter(),
            GrepFormatter(),
            BashFormatter(),
            WriteFormatter(),
            EditFormatter(),
        ]:
            self.register(formatter)

    def register(self, formatter: ToolResponseFormatter) -> None:
        """Register a formatter"""
        self._formatters[formatter.tool_name.lower()] = formatter
        logger.debug(f"Registered formatter for tool: {formatter.tool_name}")

    def get(self, tool_name: str) -> ToolResponseFormatter:
        """Get formatter for tool (returns default if not found)"""
        return self._formatters.get(tool_name.lower(), self._default)

    def format(self, tool_name: str, response: Any, max_length: int = 500) -> str:
        """Format tool response using appropriate formatter"""
        formatter = self.get(tool_name)
        return formatter.format(response, max_length)


# Global registry instance
_registry: Optional[FormatterRegistry] = None


def get_formatter_registry() -> FormatterRegistry:
    """Get the global formatter registry"""
    global _registry
    if _registry is None:
        _registry = FormatterRegistry()
    return _registry


def format_tool_response(tool_name: str, response: Any, max_length: int = 500) -> str:
    """
    Format tool response for display.

    This is the main entry point - replaces _format_tool_response().

    Args:
        tool_name: Name of the tool
        response: Raw response from the tool
max_length: Maximum length of output

    Returns:
        Formatted string for display
    """
    # Parse JSON string if needed
    if isinstance(response, str):
        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                response = parsed
        except (json.JSONDecodeError, TypeError):
            pass

    return get_formatter_registry().format(tool_name, response, max_length)
