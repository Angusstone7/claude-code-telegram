from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities.user import User
from domain.value_objects.user_id import UserId


class UserRepository(ABC):
    """Repository interface for User aggregate"""

    @abstractmethod
    async def find_by_id(self, user_id: UserId) -> Optional[User]:
        """Find user by ID"""
        pass

    @abstractmethod
    async def find_all(self) -> List[User]:
        """Find all users"""
        pass

    @abstractmethod
    async def save(self, user: User) -> None:
        """Save user (create or update)"""
        pass

    @abstractmethod
    async def delete(self, user_id: UserId) -> None:
        """Delete user"""
        pass

    @abstractmethod
    async def find_active(self) -> List[User]:
        """Find all active users"""
        pass
