"""
User Statistics Value Object

Encapsulates user statistics calculation.
Moves stats logic from BotService into the domain (fixes Feature Envy).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from domain.entities.user import User
    from domain.entities.command import Command
    from domain.entities.session import Session


@dataclass(frozen=True)
class CommandStats:
    """Statistics about user's commands"""
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    completed: int = 0
    failed: int = 0

    @classmethod
    def from_commands(cls, commands: List["Command"]) -> "CommandStats":
        """Calculate stats from command list"""
        stats = {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "completed": 0,
            "failed": 0,
        }
        for cmd in commands:
            status = cmd.status.value.lower()
            if status in stats:
                stats[status] += 1
        return cls(
            total=len(commands),
            **stats
        )


@dataclass(frozen=True)
class SessionStats:
    """Statistics about user's sessions"""
    total: int = 0
    active: int = 0
    total_messages: int = 0

    @classmethod
    def from_sessions(cls, sessions: List["Session"]) -> "SessionStats":
        """Calculate stats from session list"""
        active = sum(1 for s in sessions if s.is_active)
        messages = sum(len(s.messages) for s in sessions)
        return cls(
            total=len(sessions),
            active=active,
            total_messages=messages,
        )


@dataclass(frozen=True)
class UserStats:
    """
    User statistics value object.

    Contains all statistics about a user, calculated from their
    entities rather than being fetched separately.
    """
    user_id: int
    username: Optional[str]
    role: str
    is_active: bool
    created_at: Optional[datetime]
    last_command_at: Optional[datetime]
    commands: CommandStats = field(default_factory=CommandStats)
    sessions: SessionStats = field(default_factory=SessionStats)

    @classmethod
    def from_user(
        cls,
        user: "User",
        commands: List["Command"] = None,
        sessions: List["Session"] = None
    ) -> "UserStats":
        """
        Create UserStats from user entity and related data.

        This encapsulates the stats calculation that was previously
        spread across BotService (Feature Envy pattern).
        """
        return cls(
            user_id=int(user.user_id),
            username=user.username,
            role=user.role.name,
            is_active=user.is_active,
            created_at=user.created_at,
            last_command_at=user.last_command_at,
            commands=CommandStats.from_commands(commands or []),
            sessions=SessionStats.from_sessions(sessions or []),
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response"""
        return {
            "user": {
                "id": self.user_id,
                "username": self.username,
                "role": self.role,
                "is_active": self.is_active,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "last_command_at": self.last_command_at.isoformat() if self.last_command_at else None,
            },
            "commands": {
                "total": self.commands.total,
                "by_status": {
                    "pending": self.commands.pending,
                    "approved": self.commands.approved,
                    "rejected": self.commands.rejected,
                    "completed": self.commands.completed,
                    "failed": self.commands.failed,
                }
            },
            "sessions": {
                "total": self.sessions.total,
                "active": self.sessions.active,
                "total_messages": self.sessions.total_messages,
            }
        }
