"""
Claude Code Session Entity

Represents a Claude Code session state for a user, including:
- Working directory
- Claude session ID for resume
- HITL pending state (permission requests, questions)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any


class SessionStatus(str, Enum):
    """Status of a Claude Code session"""
    IDLE = "idle"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_ANSWER = "waiting_answer"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PendingPermission:
    """Pending permission request from Claude Code"""
    request_id: str
    tool_name: str
    details: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PendingQuestion:
    """Pending question from Claude Code"""
    request_id: str
    question: str
    options: list[str]
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ClaudeCodeSession:
    """
    Claude Code session entity.

    Tracks the state of an active Claude Code session for a user.
    """
    user_id: int
    working_dir: str
    status: SessionStatus = SessionStatus.IDLE
    claude_session_id: Optional[str] = None
    current_prompt: Optional[str] = None
    pending_permission: Optional[PendingPermission] = None
    pending_question: Optional[PendingQuestion] = None
    last_output: str = ""
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def start_task(self, prompt: str):
        """Mark session as running a task"""
        self.status = SessionStatus.RUNNING
        self.current_prompt = prompt
        self.error = None
        self.pending_permission = None
        self.pending_question = None
        self.updated_at = datetime.utcnow()

    def set_waiting_approval(self, request_id: str, tool_name: str, details: str):
        """Mark session as waiting for permission approval"""
        self.status = SessionStatus.WAITING_APPROVAL
        self.pending_permission = PendingPermission(
            request_id=request_id,
            tool_name=tool_name,
            details=details
        )
        self.updated_at = datetime.utcnow()

    def set_waiting_answer(self, request_id: str, question: str, options: list[str]):
        """Mark session as waiting for user answer"""
        self.status = SessionStatus.WAITING_ANSWER
        self.pending_question = PendingQuestion(
            request_id=request_id,
            question=question,
            options=options
        )
        self.updated_at = datetime.utcnow()

    def resume_running(self):
        """Resume running after HITL response"""
        self.status = SessionStatus.RUNNING
        self.pending_permission = None
        self.pending_question = None
        self.updated_at = datetime.utcnow()

    def complete(self, session_id: Optional[str] = None):
        """Mark session as completed"""
        self.status = SessionStatus.COMPLETED
        if session_id:
            self.claude_session_id = session_id
        self.pending_permission = None
        self.pending_question = None
        self.updated_at = datetime.utcnow()

    def fail(self, error: str):
        """Mark session as failed"""
        self.status = SessionStatus.FAILED
        self.error = error
        self.pending_permission = None
        self.pending_question = None
        self.updated_at = datetime.utcnow()

    def cancel(self):
        """Mark session as cancelled"""
        self.status = SessionStatus.CANCELLED
        self.pending_permission = None
        self.pending_question = None
        self.updated_at = datetime.utcnow()

    def set_idle(self):
        """Reset to idle state"""
        self.status = SessionStatus.IDLE
        self.current_prompt = None
        self.pending_permission = None
        self.pending_question = None
        self.error = None
        self.updated_at = datetime.utcnow()

    @property
    def is_active(self) -> bool:
        """Check if session has active task"""
        return self.status in (
            SessionStatus.RUNNING,
            SessionStatus.WAITING_APPROVAL,
            SessionStatus.WAITING_ANSWER
        )

    @property
    def can_continue(self) -> bool:
        """Check if session can be continued"""
        return (
            self.claude_session_id is not None and
            self.status in (SessionStatus.COMPLETED, SessionStatus.IDLE)
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for persistence"""
        return {
            "user_id": self.user_id,
            "working_dir": self.working_dir,
            "status": self.status.value,
            "claude_session_id": self.claude_session_id,
            "current_prompt": self.current_prompt,
            "last_output": self.last_output,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ClaudeCodeSession":
        """Create from dictionary"""
        return cls(
            user_id=data["user_id"],
            working_dir=data["working_dir"],
            status=SessionStatus(data.get("status", "idle")),
            claude_session_id=data.get("claude_session_id"),
            current_prompt=data.get("current_prompt"),
            last_output=data.get("last_output", ""),
            error=data.get("error"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
        )
