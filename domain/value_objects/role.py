from dataclasses import dataclass
from enum import Enum
from typing import Set


class Permission(Enum):
    """User permissions"""
    EXECUTE_COMMANDS = "execute_commands"
    VIEW_LOGS = "view_logs"
    MANAGE_SESSIONS = "manage_sessions"
    MANAGE_USERS = "manage_users"
    MANAGE_DOCKER = "manage_docker"
    MANAGE_GITLAB = "manage_gitlab"
    VIEW_METRICS = "view_metrics"
    SCHEDULE_TASKS = "schedule_tasks"


@dataclass(frozen=True)
class Role:
    """Value object representing user role with permissions"""
    name: str
    permissions: Set[Permission]

    def has_permission(self, permission: Permission) -> bool:
        """Check if role has specific permission"""
        return permission in self.permissions

    def can_execute(self) -> bool:
        """Check if role can execute commands"""
        return self.has_permission(Permission.EXECUTE_COMMANDS)

    @classmethod
    def admin(cls) -> "Role":
        """Create admin role with all permissions"""
        return cls(
            name="admin",
            permissions=set(Permission)
        )

    @classmethod
    def user(cls) -> "Role":
        """Create standard user role"""
        return cls(
            name="user",
            permissions={
                Permission.EXECUTE_COMMANDS,
                Permission.VIEW_LOGS,
                Permission.MANAGE_SESSIONS,
                Permission.VIEW_METRICS,
            }
        )

    @classmethod
    def readonly(cls) -> "Role":
        """Create readonly role"""
        return cls(
            name="readonly",
            permissions={
                Permission.VIEW_LOGS,
                Permission.VIEW_METRICS,
            }
        )

    @classmethod
    def devops(cls) -> "Role":
        """Create devops role"""
        return cls(
            name="devops",
            permissions={
                Permission.EXECUTE_COMMANDS,
                Permission.VIEW_LOGS,
                Permission.MANAGE_SESSIONS,
                Permission.MANAGE_DOCKER,
                Permission.MANAGE_GITLAB,
                Permission.VIEW_METRICS,
                Permission.SCHEDULE_TASKS,
            }
        )
