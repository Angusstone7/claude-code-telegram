from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from domain.value_objects.user_id import UserId
from domain.value_objects.role import Role


@dataclass
class User:
    """User entity - represents a Telegram user with access to the bot"""
    user_id: UserId
    username: Optional[str]
    first_name: str
    last_name: Optional[str]
    role: Role
    is_active: bool = True
    created_at: datetime = None
    last_command_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def can_execute_commands(self) -> bool:
        """Check if user is allowed to execute commands"""
        return self.is_active and self.role.can_execute()

    def grant_role(self, role: Role) -> None:
        """Grant a new role to the user"""
        self.role = role

    def deactivate(self) -> None:
        """Deactivate user"""
        self.is_active = False

    def activate(self) -> None:
        """Activate user"""
        self.is_active = True

    def update_last_command(self) -> None:
        """Update last command timestamp"""
        self.last_command_at = datetime.utcnow()
