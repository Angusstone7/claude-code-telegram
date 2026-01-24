"""
Project Entity

Represents a user's project/workspace with its configuration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from domain.value_objects.user_id import UserId
from domain.value_objects.project_path import ProjectPath


@dataclass
class Project:
    """
    Project entity representing a user's workspace.

    Each project has:
    - Unique ID
    - Owner (user_id)
    - Name and path
    - Optional description
    - Active status
    - Timestamps
    """

    id: str
    user_id: UserId
    name: str
    path: ProjectPath
    description: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        user_id: UserId,
        name: str,
        path: str,
        description: Optional[str] = None
    ) -> "Project":
        """
        Factory method to create a new project.

        Args:
            user_id: Owner's user ID
            name: Project display name
            path: Project directory path
            description: Optional description

        Returns:
            New Project instance
        """
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            path=ProjectPath.from_path(path),
            description=description,
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    @classmethod
    def from_name(
        cls,
        user_id: UserId,
        name: str,
        description: Optional[str] = None
    ) -> "Project":
        """
        Create project from name only (path auto-generated).

        Args:
            user_id: Owner's user ID
            name: Project name
            description: Optional description

        Returns:
            New Project instance with auto-generated path
        """
        path = ProjectPath.from_name(name)
        return cls.create(user_id, name, path.value, description)

    def update(self, **kwargs) -> None:
        """Update project fields"""
        allowed_fields = {'name', 'description', 'is_active'}

        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(self, key, value)

        self.updated_at = datetime.now()

    def deactivate(self) -> None:
        """Mark project as inactive"""
        self.is_active = False
        self.updated_at = datetime.now()

    def activate(self) -> None:
        """Mark project as active"""
        self.is_active = True
        self.updated_at = datetime.now()

    @property
    def working_dir(self) -> str:
        """Get working directory path as string"""
        return self.path.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Project):
            return self.id == other.id
        return False

    def __hash__(self) -> int:
        return hash(self.id)
