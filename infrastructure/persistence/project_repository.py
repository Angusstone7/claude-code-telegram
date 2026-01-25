"""
SQLite Project Repository Implementation

Handles project persistence and user workspace state.
"""

import aiosqlite
import logging
from typing import List, Optional
from datetime import datetime

from domain.entities.project import Project
from domain.value_objects.user_id import UserId
from domain.value_objects.project_path import ProjectPath
from domain.repositories.project_repository import IProjectRepository
from shared.config.settings import settings

logger = logging.getLogger(__name__)


class SQLiteProjectRepository(IProjectRepository):
    """SQLite implementation of IProjectRepository"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.database.url.replace("sqlite:///", "")

    async def initialize(self) -> None:
        """Initialize database tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Projects table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(user_id, path)
                )
            """)

            # User workspace table (tracks current project per user)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_workspace (
                    user_id INTEGER PRIMARY KEY,
                    current_project_id TEXT,
                    current_context_id TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (current_project_id) REFERENCES projects(id)
                )
            """)

            # Create indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_projects_user_id
                ON projects(user_id)
            """)

            await db.commit()
            logger.info("Project tables initialized")

    async def save(self, project: Project) -> None:
        """Save or update a project"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO projects
                (id, user_id, name, path, description, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.id,
                int(project.user_id),
                project.name,
                project.path.value,
                project.description,
                1 if project.is_active else 0,
                project.created_at.isoformat(),
                project.updated_at.isoformat()
            ))
            await db.commit()

    async def find_by_id(self, project_id: str) -> Optional[Project]:
        """Find project by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_project(row)
        return None

    async def find_by_user(self, user_id: UserId) -> List[Project]:
        """Find all projects for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM projects WHERE user_id = ? AND is_active = 1 ORDER BY updated_at DESC",
                (int(user_id),)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_project(row) for row in rows]

    async def find_by_path(self, user_id: UserId, path: str) -> Optional[Project]:
        """Find project by path for a specific user"""
        # Normalize path for comparison
        normalized_path = ProjectPath.from_path(path).value

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM projects WHERE user_id = ? AND path = ?",
                (int(user_id), normalized_path)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_project(row)
        return None

    async def find_parent_project(self, user_id: UserId, path: str) -> Optional[Project]:
        """Find project that contains the given path (path is subfolder of project).

        Uses SQL prefix matching to find if the given path starts with
        any stored project path + '/'.

        Example:
            - Path '/root/projects/myproject/src' matches project at '/root/projects/myproject'
            - Path '/root/projects/myprojectX' does NOT match '/root/projects/myproject'
        """
        normalized_path = ProjectPath.from_path(path).value

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Find project where stored path is a prefix of given path
            # The '/%' ensures we only match actual subfolders, not similar names
            # ORDER BY LENGTH(path) DESC gives us the deepest (most specific) match
            async with db.execute("""
                SELECT * FROM projects
                WHERE user_id = ?
                  AND ? LIKE (path || '/%')
                  AND is_active = 1
                ORDER BY LENGTH(path) DESC
                LIMIT 1
            """, (int(user_id), normalized_path)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_project(row)
        return None

    async def get_current(self, user_id: UserId) -> Optional[Project]:
        """Get the currently active project for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Get current project ID from workspace
            async with db.execute(
                "SELECT current_project_id FROM user_workspace WHERE user_id = ?",
                (int(user_id),)
            ) as cursor:
                row = await cursor.fetchone()
                if not row or not row["current_project_id"]:
                    return None

                project_id = row["current_project_id"]

            # Get the project
            async with db.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_project(row)

        return None

    async def set_current(self, user_id: UserId, project_id: str) -> None:
        """Set the current project for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now().isoformat()

            # Upsert user workspace
            await db.execute("""
                INSERT INTO user_workspace (user_id, current_project_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    current_project_id = excluded.current_project_id,
                    updated_at = excluded.updated_at
            """, (int(user_id), project_id, now, now))

            await db.commit()

    async def delete(self, project_id: str) -> bool:
        """Delete a project"""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if project exists
            async with db.execute(
                "SELECT id FROM projects WHERE id = ?",
                (project_id,)
            ) as cursor:
                if not await cursor.fetchone():
                    return False

            # Remove from workspace if current
            await db.execute("""
                UPDATE user_workspace
                SET current_project_id = NULL, updated_at = ?
                WHERE current_project_id = ?
            """, (datetime.now().isoformat(), project_id))

            # Delete project
            await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            await db.commit()

        return True

    async def exists(self, user_id: UserId, path: str) -> bool:
        """Check if a project exists at path for user"""
        normalized_path = ProjectPath.from_path(path).value

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM projects WHERE user_id = ? AND path = ?",
                (int(user_id), normalized_path)
            ) as cursor:
                return await cursor.fetchone() is not None

    def _row_to_project(self, row) -> Project:
        """Convert database row to Project entity"""
        return Project(
            id=row["id"],
            user_id=UserId.from_int(row["user_id"]),
            name=row["name"],
            path=ProjectPath.from_path(row["path"]),
            description=row["description"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.now()
        )
