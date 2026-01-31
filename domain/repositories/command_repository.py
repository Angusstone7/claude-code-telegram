from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities.command import Command, CommandStatus


class CommandRepository(ABC):
    """Repository interface for Command aggregate"""

    @abstractmethod
    async def find_by_id(self, command_id: str) -> Optional[Command]:
        """Find command by ID"""
        pass

    @abstractmethod
    async def find_by_user(self, user_id: int, limit: int = 100) -> List[Command]:
        """Find commands for a user"""
        pass

    @abstractmethod
    async def find_pending(self) -> List[Command]:
        """Find all pending commands"""
        pass

    @abstractmethod
    async def save(self, command: Command) -> None:
        """Save command (create or update)"""
        pass

    @abstractmethod
    async def delete_old_commands(self, days: int = 30) -> int:
        """Delete commands older than specified days"""
        pass

    @abstractmethod
    async def get_statistics(self, user_id: Optional[int] = None) -> dict:
        """Get command execution statistics"""
        pass
