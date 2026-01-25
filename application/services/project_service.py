"""
Project Service

Application service for managing projects.
Orchestrates project operations following SRP.
"""

import os
import logging
from typing import List, Optional

from domain.entities.project import Project
from domain.value_objects.user_id import UserId
from domain.value_objects.project_path import ProjectPath
from domain.repositories.project_repository import IProjectRepository
from domain.repositories.project_context_repository import IProjectContextRepository

logger = logging.getLogger(__name__)


class ProjectService:
    """
    Service for managing projects.

    Handles:
    - Project CRUD operations
    - Project switching
    - Project discovery in /root/projects
    """

    def __init__(
        self,
        project_repository: IProjectRepository,
        context_repository: IProjectContextRepository
    ):
        self.project_repository = project_repository
        self.context_repository = context_repository

    async def list_projects(self, user_id: UserId) -> List[Project]:
        """
        Get all projects for a user.

        Args:
            user_id: User ID

        Returns:
            List of user's projects
        """
        return await self.project_repository.find_by_user(user_id)

    async def get_current(self, user_id: UserId) -> Optional[Project]:
        """
        Get the currently active project for a user.

        Args:
            user_id: User ID

        Returns:
            Current project or None
        """
        return await self.project_repository.get_current(user_id)

    async def get_by_id(self, project_id: str) -> Optional[Project]:
        """
        Get project by ID.

        Args:
            project_id: Project ID

        Returns:
            Project or None
        """
        return await self.project_repository.find_by_id(project_id)

    async def get_or_create(
        self,
        user_id: UserId,
        path: str,
        name: Optional[str] = None
    ) -> Project:
        """
        Get existing project or create new one.

        If path is a subfolder of an existing project, returns the parent project
        instead of creating a new one.

        Args:
            user_id: User ID
            path: Project path
            name: Optional name (derived from path if not provided)

        Returns:
            Project (existing or newly created)
        """
        # 1. Check for exact path match
        existing = await self.project_repository.find_by_path(user_id, path)
        if existing:
            return existing

        # 2. Check if path is inside an existing project (subfolder)
        parent = await self.project_repository.find_parent_project(user_id, path)
        if parent:
            logger.info(f"Path {path} is subfolder of project '{parent.name}'")
            return parent

        # 3. Create new project only if no parent found
        project_path = ProjectPath.from_path(path)
        project_name = name or project_path.name

        return await self.create_project(user_id, project_name, path)

    async def create_project(
        self,
        user_id: UserId,
        name: str,
        path: str,
        description: Optional[str] = None
    ) -> Project:
        """
        Create a new project.

        Args:
            user_id: Owner's user ID
            name: Project name
            path: Project directory path
            description: Optional description

        Returns:
            Newly created Project
        """
        # Check if already exists
        if await self.project_repository.exists(user_id, path):
            existing = await self.project_repository.find_by_path(user_id, path)
            if existing:
                logger.info(f"Project already exists at {path}")
                return existing

        # Create project
        project = Project.create(user_id, name, path, description)
        await self.project_repository.save(project)
        logger.info(f"Created project '{name}' at {path}")

        # Create default "main" context
        context = await self.context_repository.create_new(
            project.id,
            user_id,
            "main"
        )
        context.mark_as_current()
        await self.context_repository.save(context)
        logger.info(f"Created main context for project '{name}'")

        return project

    async def switch_project(self, user_id: UserId, project_id: str) -> Optional[Project]:
        """
        Switch to a different project.

        Args:
            user_id: User ID
            project_id: Project ID to switch to

        Returns:
            The switched-to Project or None if not found
        """
        # Verify project exists and belongs to user
        project = await self.project_repository.find_by_id(project_id)
        if not project:
            logger.warning(f"Project {project_id} not found")
            return None

        if int(project.user_id) != int(user_id):
            logger.warning(f"Project {project_id} does not belong to user {user_id}")
            return None

        # Set as current
        await self.project_repository.set_current(user_id, project_id)
        logger.info(f"Switched to project '{project.name}'")

        return project

    async def delete_project(self, user_id: UserId, project_id: str) -> bool:
        """
        Delete a project.

        Args:
            user_id: User ID (for verification)
            project_id: Project ID to delete

        Returns:
            True if deleted, False otherwise
        """
        # Verify ownership
        project = await self.project_repository.find_by_id(project_id)
        if not project or int(project.user_id) != int(user_id):
            return False

        # Delete all contexts first
        contexts = await self.context_repository.find_by_project(project_id)
        for ctx in contexts:
            await self.context_repository.delete(ctx.id)

        # Delete project
        result = await self.project_repository.delete(project_id)
        if result:
            logger.info(f"Deleted project '{project.name}'")

        return result

    async def discover_projects(self, root_path: str = None) -> List[str]:
        """
        Discover available project folders.

        Args:
            root_path: Root directory to scan (defaults to ProjectPath.ROOT)

        Returns:
            List of discovered folder paths
        """
        root = root_path or ProjectPath.ROOT
        folders = []

        try:
            if os.path.exists(root):
                for entry in os.scandir(root):
                    if entry.is_dir() and not entry.name.startswith('.'):
                        folders.append(entry.path)
        except OSError as e:
            logger.error(f"Error scanning {root}: {e}")

        return sorted(folders)

    async def ensure_project_exists(
        self,
        user_id: UserId,
        path: str
    ) -> Project:
        """
        Ensure a project exists at path, creating if necessary.

        Args:
            user_id: User ID
            path: Project path

        Returns:
            Project (existing or created)
        """
        project = await self.project_repository.find_by_path(user_id, path)
        if project:
            return project

        # Create project from path
        project_path = ProjectPath.from_path(path)
        return await self.create_project(user_id, project_path.name, path)
