"""
Command Execution Service

Contains result type and interface for command execution.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class CommandExecutionResult:
    """
    Result of command execution.

    Used by BotService and SSHCommandExecutor.
    """
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float

    @property
    def success(self) -> bool:
        """Check if command executed successfully"""
        return self.exit_code == 0

    @property
    def full_output(self) -> str:
        """Get combined stdout and stderr"""
        result = self.stdout
        if self.stderr:
            result += f"\n[STDERR]: {self.stderr}"
        return result

    @property
    def has_error(self) -> bool:
        """Check if there was an error"""
        return self.exit_code != 0 or bool(self.stderr)

    def truncate_output(self, max_length: int = 5000) -> str:
        """Get truncated output for display"""
        output = self.full_output
        if len(output) > max_length:
            return output[:max_length] + "\n... (обрезано)"
        return output


class ICommandExecutionService(ABC):
    """Interface for command execution services"""

    @abstractmethod
    async def execute(self, command: str, timeout: int = 300) -> CommandExecutionResult:
        """Execute a command and return the result"""
        pass

    @abstractmethod
    async def execute_script(self, script: str, timeout: int = 300) -> CommandExecutionResult:
        """Execute a multi-line script and return the result"""
        pass

    @abstractmethod
    def validate_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """Validate command for safety. Returns (is_valid, error_message)"""
        pass
