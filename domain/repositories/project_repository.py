"""
Project Repository Interface

Defines the contract for project persistence operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from domain.entities.project import Project
from domain.value_objects.user_id import UserId


class IProjectRepository(ABC):
    """
    Repository interface for Project entity.

    Follows the Repository pattern from DDD.
    """

    @abstractmethod
    async def save(self, project: Project) -> None:
        """
        Save or update a project.

        Args:
            project: Project entity to save
        """
        pass

    @abstractmethod
    async def find_by_id(self, project_id: str) -> Optional[Project]:
        """
        Find project by ID.

        Args:
            project_id: Project UUID

        Returns:
            Project if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_by_user(self, user_id: UserId) -> List[Project]:
        """
        Find all projects for a user.

        Args:
            user_id: User ID

        Returns:
            List of user's projects
        """
        pass

    @abstractmethod
    async def find_by_path(self, user_id: UserId, path: str) -> Optional[Project]:
        """
        Find project by path for a specific user.

        Args:
            user_id: User ID
            path: Project path

        Returns:
            Project if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_parent_project(self, user_id: UserId, path: str) -> Optional[Project]:
        """
        Find project that contains the given path (path is subfolder of project).

        Used to detect if a path like /root/projects/myproject/src belongs
        to an existing project at /root/projects/myproject.

        Args:
            user_id: User ID
            path: Path to check (may be subfolder of a project)

        Returns:
            Parent project if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_current(self, user_id: UserId) -> Optional[Project]:
        """
        Get the currently active project for a user.

        Args:
            user_id: User ID

        Returns:
            Current project if set, None otherwise
        """
        pass

    @abstractmethod
    async def set_current(self, user_id: UserId, project_id: str) -> None:
        """
        Set the current project for a user.

        Args:
            user_id: User ID
            project_id: Project ID to set as current
        """
        pass

    @abstractmethod
    async def delete(self, project_id: str) -> bool:
        """
        Delete a project.

        Args:
            project_id: Project ID to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, user_id: UserId, path: str) -> bool:
        """
        Check if a project exists at path for user.

        Args:
            user_id: User ID
            path: Project path

        Returns:
            True if exists
        """
        pass
