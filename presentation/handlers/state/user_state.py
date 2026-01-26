"""
User State Manager

Manages core user state:
- Claude Code sessions
- Working directories
- Session continuity
- YOLO mode
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict
from datetime import datetime

from domain.entities.claude_code_session import ClaudeCodeSession
from presentation.handlers.streaming import StreamingHandler

logger = logging.getLogger(__name__)


@dataclass
class UserSession:
    """
    Immutable user session state.

    Consolidates all per-user state into a single object
    to prevent race conditions from multiple dict accesses.
    """
    user_id: int
    working_dir: str
    claude_session: Optional[ClaudeCodeSession] = None
    continue_session_id: Optional[str] = None
    streaming_handler: Optional[StreamingHandler] = None
    yolo_mode: bool = False
    context_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def with_working_dir(self, path: str) -> "UserSession":
        """Return copy with updated working dir"""
        return UserSession(
            user_id=self.user_id,
            working_dir=path,
            claude_session=self.claude_session,
            continue_session_id=self.continue_session_id,
            streaming_handler=self.streaming_handler,
            yolo_mode=self.yolo_mode,
            context_id=self.context_id,
            created_at=self.created_at,
        )

    def with_claude_session(self, session: ClaudeCodeSession) -> "UserSession":
        """Return copy with updated claude session"""
        return UserSession(
            user_id=self.user_id,
            working_dir=self.working_dir,
            claude_session=session,
            continue_session_id=self.continue_session_id,
            streaming_handler=self.streaming_handler,
            yolo_mode=self.yolo_mode,
            context_id=self.context_id,
            created_at=self.created_at,
        )


class UserStateManager:
    """
    Manages core user state with thread-safe operations.

    Replaces the 15+ separate dictionaries in MessageHandlers
    with a single consolidated state per user.
    """

    def __init__(self, default_working_dir: str = "/root"):
        self._default_working_dir = default_working_dir
        self._sessions: Dict[int, UserSession] = {}
        self._streaming_handlers: Dict[int, StreamingHandler] = {}

    def get_or_create(self, user_id: int) -> UserSession:
        """Get existing user session or create new one"""
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession(
                user_id=user_id,
                working_dir=self._default_working_dir,
            )
        return self._sessions[user_id]

    def get(self, user_id: int) -> Optional[UserSession]:
        """Get user session if exists"""
        return self._sessions.get(user_id)

    def update(self, session: UserSession) -> None:
        """Update user session"""
        self._sessions[session.user_id] = session

    # === Working Directory ===

    def get_working_dir(self, user_id: int) -> str:
        """Get user's current working directory"""
        session = self.get(user_id)
        return session.working_dir if session else self._default_working_dir

    def set_working_dir(self, user_id: int, path: str) -> None:
        """Set user's working directory"""
        session = self.get_or_create(user_id)
        self._sessions[user_id] = session.with_working_dir(path)
        logger.debug(f"[{user_id}] Working dir set to: {path}")

    # === Session Continuity ===

    def get_continue_session_id(self, user_id: int) -> Optional[str]:
        """Get session ID to continue (for auto-resume)"""
        session = self.get(user_id)
        return session.continue_session_id if session else None

    def set_continue_session_id(self, user_id: int, session_id: str) -> None:
        """Set session ID for continuation"""
        session = self.get_or_create(user_id)
        session.continue_session_id = session_id
        logger.debug(f"[{user_id}] Continue session set: {session_id[:16]}...")

    def clear_session_cache(self, user_id: int) -> None:
        """Clear session continuation cache (for context reset)"""
        session = self.get(user_id)
        if session:
            session.continue_session_id = None
            logger.debug(f"[{user_id}] Session cache cleared")

    # === Claude Code Session ===

    def get_claude_session(self, user_id: int) -> Optional[ClaudeCodeSession]:
        """Get active Claude Code session"""
        session = self.get(user_id)
        return session.claude_session if session else None

    def set_claude_session(self, user_id: int, claude_session: ClaudeCodeSession) -> None:
        """Set active Claude Code session"""
        session = self.get_or_create(user_id)
        session.claude_session = claude_session

    # === YOLO Mode ===

    def is_yolo_mode(self, user_id: int) -> bool:
        """Check if YOLO mode (auto-approve) is enabled"""
        session = self.get(user_id)
        return session.yolo_mode if session else False

    def set_yolo_mode(self, user_id: int, enabled: bool) -> None:
        """Enable/disable YOLO mode"""
        session = self.get_or_create(user_id)
        session.yolo_mode = enabled
        logger.info(f"[{user_id}] YOLO mode: {enabled}")

    # === Streaming Handler ===

    def get_streaming_handler(self, user_id: int) -> Optional[StreamingHandler]:
        """Get active streaming handler"""
        return self._streaming_handlers.get(user_id)

    def set_streaming_handler(self, user_id: int, handler: StreamingHandler) -> None:
        """Set streaming handler"""
        self._streaming_handlers[user_id] = handler

    def remove_streaming_handler(self, user_id: int) -> None:
        """Remove streaming handler"""
        self._streaming_handlers.pop(user_id, None)

    # === Context ===

    def get_context_id(self, user_id: int) -> Optional[str]:
        """Get current context ID"""
        session = self.get(user_id)
        return session.context_id if session else None

    def set_context_id(self, user_id: int, context_id: str) -> None:
        """Set current context ID"""
        session = self.get_or_create(user_id)
        session.context_id = context_id

    # === Cleanup ===

    def cleanup(self, user_id: int) -> None:
        """Clean up all state for user (after task completion)"""
        self._streaming_handlers.pop(user_id, None)
        # Keep session for state continuity
        session = self.get(user_id)
        if session and session.claude_session:
            session.claude_session = None
