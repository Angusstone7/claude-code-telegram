"""
SQLite Project Context Repository Implementation

Handles project context and message persistence.
"""

import aiosqlite
import json
import logging
from typing import List, Optional, Dict
from datetime import datetime

from domain.entities.project_context import ProjectContext, ContextMessage
from domain.value_objects.user_id import UserId
from domain.repositories.project_context_repository import IProjectContextRepository
from shared.config.settings import settings

logger = logging.getLogger(__name__)


class SQLiteProjectContextRepository(IProjectContextRepository):
    """SQLite implementation of IProjectContextRepository"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.database.url.replace("sqlite:///", "")

    async def initialize(self) -> None:
        """Initialize database tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Project contexts table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS project_contexts (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    name TEXT,
                    claude_session_id TEXT,
                    is_current INTEGER DEFAULT 0,
                    message_count INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            """)

            # Context messages table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS context_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    context_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_name TEXT,
                    tool_result TEXT,
                    timestamp TEXT,
                    FOREIGN KEY (context_id) REFERENCES project_contexts(id)
                )
            """)

            # Context variables table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS context_variables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    context_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT,
                    FOREIGN KEY (context_id) REFERENCES project_contexts(id),
                    UNIQUE(context_id, name)
                )
            """)

            # Create indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_contexts_project_id
                ON project_contexts(project_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_context_id
                ON context_messages(context_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_variables_context_id
                ON context_variables(context_id)
            """)

            await db.commit()
            logger.info("Project context tables initialized")

    # ==================== Context CRUD ====================

    async def save(self, context: ProjectContext) -> None:
        """Save or update a context (including variables)"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO project_contexts
                (id, project_id, user_id, name, claude_session_id, is_current, message_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                context.id,
                context.project_id,
                int(context.user_id),
                context.name,
                context.claude_session_id,
                1 if context.is_current else 0,
                context.message_count,
                context.created_at.isoformat(),
                context.updated_at.isoformat()
            ))

            # Save variables
            await self._save_variables(db, context.id, context.variables)

            await db.commit()

    async def find_by_id(self, context_id: str) -> Optional[ProjectContext]:
        """Find context by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM project_contexts WHERE id = ?",
                (context_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    variables = await self._load_variables(db, context_id)
                    return self._row_to_context(row, variables)
        return None

    async def find_by_project(self, project_id: str) -> List[ProjectContext]:
        """Find all contexts for a project"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM project_contexts WHERE project_id = ? ORDER BY updated_at DESC",
                (project_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                contexts = []
                for row in rows:
                    variables = await self._load_variables(db, row["id"])
                    contexts.append(self._row_to_context(row, variables))
                return contexts

    async def get_current(self, project_id: str) -> Optional[ProjectContext]:
        """Get the current context for a project"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM project_contexts WHERE project_id = ? AND is_current = 1",
                (project_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    variables = await self._load_variables(db, row["id"])
                    return self._row_to_context(row, variables)
        return None

    async def set_current(self, project_id: str, context_id: str) -> None:
        """Set the current context for a project"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now().isoformat()

            # Unset all current contexts for this project
            await db.execute("""
                UPDATE project_contexts
                SET is_current = 0, updated_at = ?
                WHERE project_id = ?
            """, (now, project_id))

            # Set new current context
            await db.execute("""
                UPDATE project_contexts
                SET is_current = 1, updated_at = ?
                WHERE id = ?
            """, (now, context_id))

            # Also update user_workspace with current context
            async with db.execute(
                "SELECT user_id FROM project_contexts WHERE id = ?",
                (context_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    user_id = row[0]
                    await db.execute("""
                        UPDATE user_workspace
                        SET current_context_id = ?, updated_at = ?
                        WHERE user_id = ?
                    """, (context_id, now, user_id))

            await db.commit()

    async def create_new(
        self,
        project_id: str,
        user_id: UserId,
        name: Optional[str] = None
    ) -> ProjectContext:
        """Create a new context for a project"""
        context = ProjectContext.create(project_id, user_id, name)

        # Save it
        await self.save(context)

        return context

    async def delete(self, context_id: str) -> bool:
        """Delete a context and all its messages and variables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if exists
            async with db.execute(
                "SELECT id FROM project_contexts WHERE id = ?",
                (context_id,)
            ) as cursor:
                if not await cursor.fetchone():
                    return False

            # Delete variables
            await db.execute(
                "DELETE FROM context_variables WHERE context_id = ?",
                (context_id,)
            )

            # Delete messages
            await db.execute(
                "DELETE FROM context_messages WHERE context_id = ?",
                (context_id,)
            )

            # Delete context
            await db.execute(
                "DELETE FROM project_contexts WHERE id = ?",
                (context_id,)
            )

            await db.commit()

        return True

    # ==================== Message Operations ====================

    async def add_message(
        self,
        context_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
        tool_result: Optional[str] = None
    ) -> None:
        """Add a message to a context"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now().isoformat()

            # Insert message
            await db.execute("""
                INSERT INTO context_messages
                (context_id, role, content, tool_name, tool_result, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (context_id, role, content, tool_name, tool_result, now))

            # Update message count
            await db.execute("""
                UPDATE project_contexts
                SET message_count = message_count + 1, updated_at = ?
                WHERE id = ?
            """, (now, context_id))

            await db.commit()

    async def get_messages(
        self,
        context_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[ContextMessage]:
        """Get messages for a context"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM context_messages
                WHERE context_id = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """, (context_id, limit, offset)) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_message(row) for row in reversed(rows)]

    async def clear_messages(self, context_id: str) -> None:
        """Clear all messages in a context"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now().isoformat()

            await db.execute(
                "DELETE FROM context_messages WHERE context_id = ?",
                (context_id,)
            )

            await db.execute("""
                UPDATE project_contexts
                SET message_count = 0, updated_at = ?
                WHERE id = ?
            """, (now, context_id))

            await db.commit()

    # ==================== Claude Session ====================

    async def set_claude_session_id(self, context_id: str, session_id: str) -> None:
        """Set Claude Code session ID for a context"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now().isoformat()
            await db.execute("""
                UPDATE project_contexts
                SET claude_session_id = ?, updated_at = ?
                WHERE id = ?
            """, (session_id, now, context_id))
            await db.commit()

    async def get_claude_session_id(self, context_id: str) -> Optional[str]:
        """Get Claude Code session ID for a context"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT claude_session_id FROM project_contexts WHERE id = ?",
                (context_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
        return None

    async def clear_claude_session_id(self, context_id: str) -> None:
        """Clear Claude Code session ID (start fresh)"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now().isoformat()
            await db.execute("""
                UPDATE project_contexts
                SET claude_session_id = NULL, updated_at = ?
                WHERE id = ?
            """, (now, context_id))
            await db.commit()

    # ==================== Helpers ====================

    def _row_to_context(self, row, variables: Dict[str, str] = None) -> ProjectContext:
        """Convert database row to ProjectContext entity"""
        return ProjectContext(
            id=row["id"],
            project_id=row["project_id"],
            user_id=UserId.from_int(row["user_id"]),
            name=row["name"] or "unnamed",
            claude_session_id=row["claude_session_id"],
            is_current=bool(row["is_current"]),
            message_count=row["message_count"] or 0,
            variables=variables or {},
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.now()
        )

    def _row_to_message(self, row) -> ContextMessage:
        """Convert database row to ContextMessage"""
        return ContextMessage(
            id=row["id"],
            context_id=row["context_id"],
            role=row["role"],
            content=row["content"],
            tool_name=row["tool_name"],
            tool_result=row["tool_result"],
            timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else datetime.now()
        )

    # ==================== Variable Operations ====================

    async def _save_variables(self, db, context_id: str, variables: Dict[str, str]) -> None:
        """Save context variables (replaces existing)"""
        # Delete existing variables
        await db.execute(
            "DELETE FROM context_variables WHERE context_id = ?",
            (context_id,)
        )

        # Insert new variables
        now = datetime.now().isoformat()
        for name, value in variables.items():
            await db.execute("""
                INSERT INTO context_variables (context_id, name, value, created_at)
                VALUES (?, ?, ?, ?)
            """, (context_id, name, value, now))

    async def _load_variables(self, db, context_id: str) -> Dict[str, str]:
        """Load context variables"""
        variables = {}
        async with db.execute(
            "SELECT name, value FROM context_variables WHERE context_id = ?",
            (context_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                variables[row[0]] = row[1]
        return variables

    async def set_variable(self, context_id: str, name: str, value: str) -> None:
        """Set a single context variable"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now().isoformat()
            await db.execute("""
                INSERT OR REPLACE INTO context_variables (context_id, name, value, created_at)
                VALUES (?, ?, ?, ?)
            """, (context_id, name, value, now))

            # Update context updated_at
            await db.execute("""
                UPDATE project_contexts SET updated_at = ? WHERE id = ?
            """, (now, context_id))

            await db.commit()

    async def delete_variable(self, context_id: str, name: str) -> bool:
        """Delete a single context variable"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM context_variables WHERE context_id = ? AND name = ?",
                (context_id, name)
            )
            deleted = cursor.rowcount > 0

            if deleted:
                now = datetime.now().isoformat()
                await db.execute("""
                    UPDATE project_contexts SET updated_at = ? WHERE id = ?
                """, (now, context_id))

            await db.commit()
            return deleted

    async def get_variables(self, context_id: str) -> Dict[str, str]:
        """Get all variables for a context"""
        async with aiosqlite.connect(self.db_path) as db:
            return await self._load_variables(db, context_id)
