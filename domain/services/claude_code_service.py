"""
Claude Code Service Interfaces

Defines contracts for Claude Code integration backends (CLI proxy, Agent SDK).
These interfaces allow presentation layer to work with either backend
without depending on infrastructure details.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable, Optional


class TaskStatus(str, Enum):
    """Status of a Claude Code task"""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_PERMISSION = "waiting_permission"
    WAITING_ANSWER = "waiting_answer"


@dataclass
class TaskResult:
    """Result of a Claude Code task (CLI backend)"""
    success: bool
    output: str
    session_id: Optional[str] = None
    error: Optional[str] = None
    cancelled: bool = False


@dataclass
class SDKTaskResult:
    """Result of a Claude Code task (SDK backend)"""
    success: bool
    output: str
    session_id: Optional[str] = None
    error: Optional[str] = None
    cancelled: bool = False
    is_error: bool = False
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    duration_api_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    num_turns: int = 0


class IClaudeCodeProxyService(ABC):
    """Interface for Claude Code CLI proxy backend"""

    @abstractmethod
    async def run_task(
        self,
        prompt: str,
        working_dir: str = None,
        session_id: str = None,
        on_event: Callable = None,
        permission_callback: Callable = None,
        answer_callback: Callable = None,
    ) -> TaskResult:
        """Run a task through Claude Code CLI"""
        pass

    @abstractmethod
    async def cancel_task(self, user_id: int) -> bool:
        """Cancel running task for user"""
        pass

    @abstractmethod
    def is_task_running(self, user_id: int) -> bool:
        """Check if a task is running for user"""
        pass


class IClaudeCodeSDKService(ABC):
    """Interface for Claude Code Agent SDK backend"""

    @abstractmethod
    async def run_task(
        self,
        prompt: str,
        user_id: int,
        working_dir: str = None,
        session_id: str = None,
        on_event: Callable = None,
        files: list = None,
    ) -> SDKTaskResult:
        """Run a task through Claude Agent SDK"""
        pass

    @abstractmethod
    async def cancel_task(self, user_id: int) -> bool:
        """Cancel running task for user"""
        pass

    @abstractmethod
    def is_task_running(self, user_id: int) -> bool:
        """Check if a task is running for user"""
        pass

    @abstractmethod
    async def respond_to_permission(self, user_id: int, approved: bool, reason: str = None) -> bool:
        """Respond to a permission request"""
        pass

    @abstractmethod
    async def respond_to_question(self, user_id: int, answer: str) -> bool:
        """Respond to a question from Claude"""
        pass

    @abstractmethod
    async def respond_to_plan(self, user_id: int, response: str) -> bool:
        """Respond to a plan approval request"""
        pass
