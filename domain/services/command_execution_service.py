from abc import ABC, abstractmethod
from typing import Optional, Tuple
from domain.entities.command import Command


class CommandExecutionResult:
    """Result of command execution"""
    def __init__(self, stdout: str, stderr: str, exit_code: int, execution_time: float):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.execution_time = execution_time

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def full_output(self) -> str:
        result = self.stdout
        if self.stderr:
            result += f"\n[STDERR]: {self.stderr}"
        return result


class ICommandExecutionService(ABC):
    """Interface for command execution service"""

    @abstractmethod
    async def execute(self, command: str, timeout: int = 300) -> CommandExecutionResult:
        """Execute a command and return the result"""
        pass

    @abstractmethod
    async def execute_script(self, script: str, timeout: int = 300) -> CommandExecutionResult:
        """Execute a multi-line script"""
        pass

    @abstractmethod
    def validate_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """Validate command for safety"""
        pass
