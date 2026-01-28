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
from presentation.handlers.streaming import StreamingHandler, HeartbeatTracker

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
    step_streaming_mode: bool = True  # Default ON - show brief output without code
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
            step_streaming_mode=self.step_streaming_mode,
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
            step_streaming_mode=self.step_streaming_mode,
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
        self._heartbeat_trackers: Dict[int, HeartbeatTracker] = {}
        # Lazy-loaded repository for persistent settings
        self._account_repo = None

    def _get_account_repo(self):
        """Get or create account repository (lazy init)"""
        if self._account_repo is None:
            from infrastructure.persistence.sqlite_account_repository import SQLiteAccountRepository
            self._account_repo = SQLiteAccountRepository()
        return self._account_repo

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
        # Persist to database asynchronously
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._persist_yolo_mode(user_id, enabled))
            else:
                loop.run_until_complete(self._persist_yolo_mode(user_id, enabled))
        except Exception as e:
            logger.warning(f"Could not persist yolo mode: {e}")

    async def _persist_yolo_mode(self, user_id: int, enabled: bool) -> None:
        """Persist yolo mode to database"""
        try:
            repo = self._get_account_repo()
            await repo.set_yolo_mode(user_id, enabled)
            logger.debug(f"[{user_id}] YOLO mode persisted: {enabled}")
        except Exception as e:
            logger.warning(f"Failed to persist yolo mode: {e}")

    async def load_yolo_mode(self, user_id: int) -> bool:
        """Load yolo mode from database"""
        try:
            repo = self._get_account_repo()
            enabled = await repo.get_yolo_mode(user_id)
            if enabled:
                session = self.get_or_create(user_id)
                session.yolo_mode = enabled
                logger.info(f"[{user_id}] YOLO mode loaded from DB: {enabled}")
            return enabled
        except Exception as e:
            logger.warning(f"Failed to load yolo mode: {e}")
            return False

    # === Step Streaming Mode ===

    def is_step_streaming_mode(self, user_id: int) -> bool:
        """Check if step streaming mode (brief output) is enabled"""
        session = self.get(user_id)
        return session.step_streaming_mode if session else False

    def set_step_streaming_mode(self, user_id: int, enabled: bool) -> None:
        """Enable/disable step streaming mode"""
        session = self.get_or_create(user_id)
        session.step_streaming_mode = enabled
        logger.info(f"[{user_id}] Step streaming mode: {enabled}")

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

    # === Heartbeat Tracker ===

    def get_heartbeat(self, user_id: int) -> Optional[HeartbeatTracker]:
        """Get active heartbeat tracker"""
        return self._heartbeat_trackers.get(user_id)

    def set_heartbeat(self, user_id: int, tracker: HeartbeatTracker) -> None:
        """Set heartbeat tracker"""
        self._heartbeat_trackers[user_id] = tracker

    def remove_heartbeat(self, user_id: int) -> None:
        """Remove heartbeat tracker"""
        self._heartbeat_trackers.pop(user_id, None)

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
        self._heartbeat_trackers.pop(user_id, None)
        # Keep session for state continuity
        session = self.get(user_id)
        if session and session.claude_session:
            session.claude_session = None
