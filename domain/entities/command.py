from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from enum import Enum


class CommandStatus(Enum):
    """Status of command execution"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Command:
    """Command entity - represents a shell command to be executed"""
    command_id: str
    user_id: int
    command: str
    status: CommandStatus = CommandStatus.PENDING
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    execution_time: Optional[float] = None
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def approve(self) -> None:
        """Mark command as approved for execution"""
        if self.status != CommandStatus.PENDING:
            raise ValueError(f"Cannot approve command with status {self.status}")
        self.status = CommandStatus.APPROVED

    def reject(self, reason: str = None) -> None:
        """Reject command execution"""
        if self.status not in (CommandStatus.PENDING, CommandStatus.APPROVED):
            raise ValueError(f"Cannot reject command with status {self.status}")
        self.status = CommandStatus.REJECTED
        self.error = reason or "Command rejected by user"

    def start_execution(self) -> None:
        """Mark command as started"""
        if self.status != CommandStatus.APPROVED:
            raise ValueError(f"Cannot start command with status {self.status}")
        self.status = CommandStatus.RUNNING
        self.started_at = datetime.utcnow()

    def complete(self, output: str, exit_code: int = 0) -> None:
        """Mark command as completed"""
        if self.status != CommandStatus.RUNNING:
            raise ValueError(f"Cannot complete command with status {self.status}")
        self.status = CommandStatus.COMPLETED
        self.output = output
        self.exit_code = exit_code
        self.completed_at = datetime.utcnow()
        if self.started_at:
            self.execution_time = (self.completed_at - self.started_at).total_seconds()

    def fail(self, error: str) -> None:
        """Mark command as failed"""
        if self.status != CommandStatus.RUNNING:
            raise ValueError(f"Cannot fail command with status {self.status}")
        self.status = CommandStatus.FAILED
        self.error = error
        self.completed_at = datetime.utcnow()
        if self.started_at:
            self.execution_time = (self.completed_at - self.started_at).total_seconds()

    @property
    def is_dangerous(self) -> bool:
        """Check if command is potentially dangerous"""
        dangerous_keywords = [
            "rm -rf", "mkfs", "format", "dd if=", "> /dev/",
            "shutdown", "reboot", "init 0", "halt",
            "chmod 000", "chown -R", "kill -9"
        ]
        command_lower = self.command.lower()
        return any(keyword in command_lower for keyword in dangerous_keywords)

    @property
    def duration(self) -> Optional[float]:
        """Get command execution duration"""
        return self.execution_time
