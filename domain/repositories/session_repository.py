from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities.session import Session
from domain.value_objects.user_id import UserId


class SessionRepository(ABC):
    """Repository interface for Session aggregate"""

    @abstractmethod
    async def find_by_id(self, session_id: str) -> Optional[Session]:
        """Find session by ID"""
        pass

    @abstractmethod
    async def find_by_user(self, user_id: UserId) -> List[Session]:
        """Find all sessions for a user"""
        pass

    @abstractmethod
    async def find_active_by_user(self, user_id: UserId) -> Optional[Session]:
        """Find active session for a user"""
        pass

    @abstractmethod
    async def save(self, session: Session) -> None:
        """Save session (create or update)"""
        pass

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """Delete session"""
        pass

    @abstractmethod
    async def delete_old_sessions(self, days: int = 7) -> int:
        """Delete sessions older than specified days"""
        pass
