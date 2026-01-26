"""
Command Execution Service

Contains result type for command execution.

Note: ICommandExecutionService interface was removed as dead code -
it was defined but never implemented or used.
"""

from dataclasses import dataclass
from typing import Optional


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
