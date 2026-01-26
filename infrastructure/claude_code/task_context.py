"""
Task Context for Claude Agent SDK

Provides immutable task context to prevent race conditions
when multiple messages arrive for the same user.

Previously, sdk_service.py used multiple separate dictionaries:
- self._cancel_events[user_id]
- self._permission_events[user_id]
- self._question_events[user_id]
- etc.

These could be overwritten by a second message before the first
completed, causing deadlocks and lost events.

This module provides TaskContext - an immutable object that holds
all task-related state, passed by reference to callbacks.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    """Current state of a task"""
    IDLE = "idle"
    RUNNING = "running"
    WAITING_PERMISSION = "waiting_permission"
    WAITING_ANSWER = "waiting_answer"
    WAITING_PLAN = "waiting_plan"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class PermissionRequest:
    """Pending permission request"""
    request_id: str
    tool_name: str
    tool_input: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QuestionRequest:
    """Pending question request"""
    request_id: str
    question: str
    options: list[str]
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TaskContext:
    """
    Immutable task context for a single Claude Code task.

    All task-related state is stored here instead of in separate
    dictionaries keyed by user_id. This prevents race conditions
    where a second message overwrites events being waited on.

    Usage:
        # Create context at task start
        context = TaskContext(user_id=123)

        # Pass context to callbacks (they use context.* not self._*)
        async def can_use_tool(...):
            if context.cancel_event.is_set():
                return deny

            context.permission_event.clear()
            # notify UI
            await context.permission_event.wait()
            return context.permission_response

        # At task end, context is garbage collected
    """

    user_id: int
    working_dir: str = "/root"
    session_id: Optional[str] = None

    # Task state
    state: TaskState = TaskState.IDLE
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Cancellation
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    cancelled: bool = False

    # Permission handling
    permission_event: asyncio.Event = field(default_factory=asyncio.Event)
    permission_request: Optional[PermissionRequest] = None
    permission_response: bool = False

    # Question handling
    question_event: asyncio.Event = field(default_factory=asyncio.Event)
    question_request: Optional[QuestionRequest] = None
    question_response: str = ""

    # Plan approval handling (ExitPlanMode)
    plan_event: asyncio.Event = field(default_factory=asyncio.Event)
    plan_response: str = "reject"

    # Results
    output_buffer: list[str] = field(default_factory=list)
    result_session_id: Optional[str] = None
    result_cost_usd: Optional[float] = None
    result_num_turns: Optional[int] = None
    error: Optional[str] = None

    def __post_init__(self):
        """Ensure events are created if not provided"""
        if not isinstance(self.cancel_event, asyncio.Event):
            self.cancel_event = asyncio.Event()
        if not isinstance(self.permission_event, asyncio.Event):
            self.permission_event = asyncio.Event()
        if not isinstance(self.question_event, asyncio.Event):
            self.question_event = asyncio.Event()
        if not isinstance(self.plan_event, asyncio.Event):
            self.plan_event = asyncio.Event()

    # === State Transitions ===

    def start(self) -> None:
        """Mark task as started"""
        self.state = TaskState.RUNNING
        self.started_at = datetime.utcnow()

    def complete(self, session_id: str = None) -> None:
        """Mark task as completed"""
        self.state = TaskState.COMPLETED
        self.completed_at = datetime.utcnow()
        if session_id:
            self.result_session_id = session_id

    def fail(self, error: str) -> None:
        """Mark task as failed"""
        self.state = TaskState.FAILED
        self.completed_at = datetime.utcnow()
        self.error = error

    def cancel(self) -> None:
        """Cancel the task"""
        self.cancelled = True
        self.state = TaskState.CANCELLED
        self.cancel_event.set()
        # Wake up any waiting events
        self.permission_event.set()
        self.question_event.set()
        self.plan_event.set()

    # === Cancellation Check ===

    def is_cancelled(self) -> bool:
        """Check if task has been cancelled"""
        return self.cancelled or self.cancel_event.is_set()

    # === Permission Handling ===

    def start_permission_wait(self, request_id: str, tool_name: str, tool_input: dict) -> None:
        """Start waiting for permission response"""
        self.state = TaskState.WAITING_PERMISSION
        self.permission_request = PermissionRequest(
            request_id=request_id,
            tool_name=tool_name,
            tool_input=tool_input,
        )
        self.permission_event.clear()

    def respond_permission(self, approved: bool) -> bool:
        """Respond to pending permission"""
        if self.state != TaskState.WAITING_PERMISSION:
            return False
        self.permission_response = approved
        self.permission_event.set()
        return True

    def finish_permission_wait(self) -> None:
        """Finish permission wait and resume running"""
        self.state = TaskState.RUNNING
        self.permission_request = None

    # === Question Handling ===

    def start_question_wait(self, request_id: str, question: str, options: list[str]) -> None:
        """Start waiting for question response"""
        self.state = TaskState.WAITING_ANSWER
        self.question_request = QuestionRequest(
            request_id=request_id,
            question=question,
            options=options,
        )
        self.question_event.clear()

    def respond_question(self, answer: str) -> bool:
        """Respond to pending question"""
        if self.state != TaskState.WAITING_ANSWER:
            return False
        self.question_response = answer
        self.question_event.set()
        return True

    def finish_question_wait(self) -> None:
        """Finish question wait and resume running"""
        self.state = TaskState.RUNNING
        self.question_request = None

    # === Plan Handling ===

    def start_plan_wait(self) -> None:
        """Start waiting for plan approval"""
        self.state = TaskState.WAITING_PLAN
        self.plan_event.clear()

    def respond_plan(self, response: str) -> bool:
        """Respond to pending plan approval"""
        if self.state != TaskState.WAITING_PLAN:
            return False
        self.plan_response = response
        self.plan_event.set()
        return True

    def finish_plan_wait(self) -> None:
        """Finish plan wait and resume running"""
        self.state = TaskState.RUNNING

    # === Output ===

    def append_output(self, text: str) -> None:
        """Append text to output buffer"""
        self.output_buffer.append(text)

    def get_output(self) -> str:
        """Get combined output"""
        return "\n".join(self.output_buffer)


class TaskContextManager:
    """
    Manages TaskContext instances per user.

    Ensures only one active task per user at a time.
    """

    def __init__(self):
        self._contexts: Dict[int, TaskContext] = {}

    def get(self, user_id: int) -> Optional[TaskContext]:
        """Get active task context for user"""
        return self._contexts.get(user_id)

    def create(self, user_id: int, working_dir: str = "/root", session_id: str = None) -> TaskContext:
        """
        Create new task context for user.

        If a task is already running, it will be cancelled first.
        """
        # Cancel existing task if any
        existing = self._contexts.get(user_id)
        if existing and existing.state in (TaskState.RUNNING, TaskState.WAITING_PERMISSION,
                                           TaskState.WAITING_ANSWER, TaskState.WAITING_PLAN):
            logger.warning(f"[{user_id}] Cancelling existing task to start new one")
            existing.cancel()

        # Create new context
        context = TaskContext(
            user_id=user_id,
            working_dir=working_dir,
            session_id=session_id,
        )
        self._contexts[user_id] = context
        return context

    def remove(self, user_id: int) -> Optional[TaskContext]:
        """Remove and return task context"""
        return self._contexts.pop(user_id, None)

    def is_task_running(self, user_id: int) -> bool:
        """Check if a task is running for user"""
        context = self._contexts.get(user_id)
        if not context:
            return False
        return context.state in (TaskState.RUNNING, TaskState.WAITING_PERMISSION,
                                 TaskState.WAITING_ANSWER, TaskState.WAITING_PLAN)

    def cancel(self, user_id: int) -> bool:
        """Cancel task for user"""
        context = self._contexts.get(user_id)
        if context:
            context.cancel()
            return True
        return False
