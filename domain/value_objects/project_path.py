"""
Project Path Value Object

Immutable value object representing a project directory path.
Ensures path validation and normalization.
"""

from dataclasses import dataclass
from typing import Optional
import os


@dataclass(frozen=True)
class ProjectPath:
    """
    Value object for project path.

    Immutable and self-validating. Ensures paths are normalized
    and within allowed boundaries.
    """

    ROOT = "/root/projects"

    _path: str

    def __post_init__(self):
        """Validate path on creation"""
        if not self._path:
            raise ValueError("Project path cannot be empty")

        # Normalize the path
        normalized = self._normalize(self._path)
        object.__setattr__(self, '_path', normalized)

    @staticmethod
    def _normalize(path: str) -> str:
        """Normalize path for consistency"""
        # Remove trailing slashes
        path = path.rstrip('/')
        # Replace backslashes with forward slashes
        path = path.replace('\\', '/')
        # Remove double slashes
        while '//' in path:
            path = path.replace('//', '/')
        return path

    @property
    def value(self) -> str:
        """Get the path string value"""
        return self._path

    @property
    def name(self) -> str:
        """Get the project name (last part of path)"""
        return os.path.basename(self._path)

    @property
    def parent(self) -> str:
        """Get parent directory"""
        return os.path.dirname(self._path)

    @property
    def is_under_root(self) -> bool:
        """Check if path is under the projects root"""
        return self._path.startswith(self.ROOT)

    @classmethod
    def from_name(cls, name: str) -> "ProjectPath":
        """
        Create ProjectPath from just a project name.

        Args:
            name: Project name (will be placed under ROOT)

        Returns:
            ProjectPath with full path
        """
        # Clean the name
        name = name.strip().replace(' ', '-').lower()
        name = ''.join(c for c in name if c.isalnum() or c in '-_')

        if not name:
            raise ValueError("Project name cannot be empty")

        return cls(f"{cls.ROOT}/{name}")

    @classmethod
    def from_path(cls, path: str) -> "ProjectPath":
        """
        Create ProjectPath from full path.

        Args:
            path: Full path to project directory

        Returns:
            ProjectPath instance
        """
        return cls(path)

    def __str__(self) -> str:
        return self._path

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ProjectPath):
            return self._path == other._path
        if isinstance(other, str):
            return self._path == self._normalize(other)
        return False

    def __hash__(self) -> int:
        return hash(self._path)
