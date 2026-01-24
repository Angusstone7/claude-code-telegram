import aiosqlite
import json
from typing import List, Optional
from datetime import datetime, timedelta
from domain.entities.user import User
from domain.entities.session import Session
from domain.entities.command import Command
from domain.entities.message import Message, MessageRole
from domain.value_objects.user_id import UserId
from domain.value_objects.role import Role, Permission
from domain.repositories.user_repository import UserRepository
from domain.repositories.session_repository import SessionRepository
from domain.repositories.command_repository import CommandRepository
from shared.config.settings import settings


class SQLiteUserRepository(UserRepository):
    """SQLite implementation of UserRepository"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.database.url.replace("sqlite:///", "")
        self._init_db()

    def _init_db(self):
        import os

        os.makedirs(
            os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".",
            exist_ok=True,
        )

    async def _get_connection(self) -> aiosqlite.Connection:
        return await aiosqlite.connect(self.db_path)

    async def find_by_id(self, user_id: UserId) -> Optional[User]:
        async with await self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?", (int(user_id),)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_user(row)
        return None

    async def find_all(self) -> List[User]:
        async with await self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users") as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_user(row) for row in rows]

    async def save(self, user: User) -> None:
        async with await self._get_connection() as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO users
                (user_id, username, first_name, last_name, role, is_active, created_at, last_command_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    int(user.user_id),
                    user.username,
                    user.first_name,
                    user.last_name,
                    user.role.name,
                    user.is_active,
                    user.created_at.isoformat() if user.created_at else None,
                    user.last_command_at.isoformat() if user.last_command_at else None,
                ),
            )
            await db.commit()

    async def delete(self, user_id: UserId) -> None:
        async with await self._get_connection() as db:
            await db.execute("DELETE FROM users WHERE user_id = ?", (int(user_id),))
            await db.commit()

    async def find_active(self) -> List[User]:
        async with await self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE is_active = 1") as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_user(row) for row in rows]

    def _row_to_user(self, row) -> User:
        role_map = {
            "admin": Role.admin(),
            "user": Role.user(),
            "readonly": Role.readonly(),
            "devops": Role.devops(),
        }
        role = role_map.get(row["role"], Role.user())
        return User(
            user_id=UserId.from_int(row["user_id"]),
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            role=role,
            is_active=bool(row["is_active"]),
            created_at=(
                datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            ),
            last_command_at=(
                datetime.fromisoformat(row["last_command_at"])
                if row["last_command_at"]
                else None
            ),
        )


class SQLiteSessionRepository(SessionRepository):
    """SQLite implementation of SessionRepository"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.database.url.replace("sqlite:///", "")
        self._init_db()

    def _init_db(self):
        import os

        os.makedirs(
            os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".",
            exist_ok=True,
        )

    async def _get_connection(self) -> aiosqlite.Connection:
        return await aiosqlite.connect(self.db_path)

    async def find_by_id(self, session_id: str) -> Optional[Session]:
        async with await self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return await self._row_to_session(db, row)
        return None

    async def find_by_user(self, user_id: UserId) -> List[Session]:
        async with await self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
                (int(user_id),),
            ) as cursor:
                rows = await cursor.fetchall()
                sessions = []
                for row in rows:
                    sessions.append(await self._row_to_session(db, row))
                return sessions

    async def find_active_by_user(self, user_id: UserId) -> Optional[Session]:
        async with await self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM sessions WHERE user_id = ? AND is_active = 1 ORDER BY updated_at DESC LIMIT 1",
                (int(user_id),),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return await self._row_to_session(db, row)
        return None

    async def save(self, session: Session) -> None:
        async with await self._get_connection() as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO sessions
                (session_id, user_id, context, created_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    session.session_id,
                    int(session.user_id),
                    json.dumps(session.context),
                    session.created_at.isoformat() if session.created_at else None,
                    session.updated_at.isoformat() if session.updated_at else None,
                    session.is_active,
                ),
            )
            # Save messages
            await db.execute(
                "DELETE FROM session_messages WHERE session_id = ?",
                (session.session_id,),
            )
            for msg in session.messages:
                await db.execute(
                    """
                    INSERT INTO session_messages
                    (session_id, role, content, timestamp, tool_use_id, tool_result)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        session.session_id,
                        msg.role.value,
                        msg.content,
                        msg.timestamp.isoformat() if msg.timestamp else None,
                        msg.tool_use_id,
                        msg.tool_result,
                    ),
                )
            await db.commit()

    async def delete(self, session_id: str) -> None:
        async with await self._get_connection() as db:
            await db.execute(
                "DELETE FROM session_messages WHERE session_id = ?", (session_id,)
            )
            await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            await db.commit()

    async def delete_old_sessions(self, days: int = 7) -> int:
        cutoff = datetime.utcnow() - timedelta(days=days)
        async with await self._get_connection() as db:
            cursor = await db.execute(
                "DELETE FROM sessions WHERE updated_at < ?", (cutoff.isoformat(),)
            )
            await db.commit()
            return cursor.rowcount

    async def _row_to_session(self, db: aiosqlite.Connection, row) -> Session:
        messages = []
        async with db.execute(
            "SELECT * FROM session_messages WHERE session_id = ? ORDER BY timestamp",
            (row["session_id"],),
        ) as msg_cursor:
            msg_rows = await msg_cursor.fetchall()
            for msg_row in msg_rows:
                messages.append(
                    Message(
                        role=MessageRole(msg_row["role"]),
                        content=msg_row["content"],
                        timestamp=(
                            datetime.fromisoformat(msg_row["timestamp"])
                            if msg_row["timestamp"]
                            else None
                        ),
                        tool_use_id=msg_row["tool_use_id"],
                        tool_result=msg_row["tool_result"],
                    )
                )

        return Session(
            session_id=row["session_id"],
            user_id=UserId.from_int(row["user_id"]),
            messages=messages,
            context=json.loads(row["context"]) if row["context"] else {},
            created_at=(
                datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            ),
            updated_at=(
                datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None
            ),
            is_active=bool(row["is_active"]),
        )


class SQLiteCommandRepository(CommandRepository):
    """SQLite implementation of CommandRepository"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.database.url.replace("sqlite:///", "")
        self._init_db()

    def _init_db(self):
        import os

        os.makedirs(
            os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".",
            exist_ok=True,
        )

    async def _get_connection(self) -> aiosqlite.Connection:
        return await aiosqlite.connect(self.db_path)

    async def find_by_id(self, command_id: str) -> Optional[Command]:
        async with await self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM commands WHERE command_id = ?", (command_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_command(row)
        return None

    async def find_by_user(self, user_id: int, limit: int = 100) -> List[Command]:
        async with await self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM commands WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_command(row) for row in rows]

    async def find_pending(self) -> List[Command]:
        async with await self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM commands WHERE status IN ('pending', 'approved') ORDER BY created_at"
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_command(row) for row in rows]

    async def save(self, command: Command) -> None:
        async with await self._get_connection() as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO commands
                (command_id, user_id, command, status, output, error, exit_code, execution_time,
                 created_at, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    command.command_id,
                    command.user_id,
                    command.command,
                    command.status.value,
                    command.output,
                    command.error,
                    command.exit_code,
                    command.execution_time,
                    command.created_at.isoformat() if command.created_at else None,
                    command.started_at.isoformat() if command.started_at else None,
                    command.completed_at.isoformat() if command.completed_at else None,
                ),
            )
            await db.commit()

    async def delete_old_commands(self, days: int = 30) -> int:
        cutoff = datetime.utcnow() - timedelta(days=days)
        async with await self._get_connection() as db:
            cursor = await db.execute(
                "DELETE FROM commands WHERE created_at < ?", (cutoff.isoformat(),)
            )
            await db.commit()
            return cursor.rowcount

    async def get_statistics(self, user_id: Optional[int] = None) -> dict:
        query = "SELECT status, COUNT(*) as count FROM commands"
        params = []
        if user_id:
            query += " WHERE user_id = ?"
            params.append(user_id)
        query += " GROUP BY status"

        async with await self._get_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                stats = {row["status"]: row["count"] for row in rows}
                stats["total"] = sum(stats.values())
                return stats

    def _row_to_command(self, row) -> Command:
        from domain.entities.command import CommandStatus

        return Command(
            command_id=row["command_id"],
            user_id=row["user_id"],
            command=row["command"],
            status=CommandStatus(row["status"]),
            output=row["output"],
            error=row["error"],
            exit_code=row["exit_code"],
            execution_time=row["execution_time"],
            created_at=(
                datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            ),
            started_at=(
                datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
            ),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
        )


async def init_database(db_path: str = None):
    """Initialize database tables"""
    db_path = db_path or settings.database.url.replace("sqlite:///", "")
    import os

    os.makedirs(
        os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True
    )

    async with aiosqlite.connect(db_path) as db:
        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT,
                role TEXT NOT NULL DEFAULT 'user',
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT,
                last_command_at TEXT
            )
        """)

        # Sessions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                context TEXT,
                created_at TEXT,
                updated_at TEXT,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Session messages table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS session_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT,
                tool_use_id TEXT,
                tool_result TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
        """)

        # Commands table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS commands (
                command_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                output TEXT,
                error TEXT,
                exit_code INTEGER,
                execution_time REAL,
                created_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Scheduled tasks table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                task_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                command TEXT NOT NULL,
                schedule TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                last_run TEXT,
                next_run TEXT,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Notifications table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'normal',
                recipients TEXT,
                sent_at TEXT,
                created_at TEXT
            )
        """)

        # Indexes
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_commands_user ON commands(user_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_session_messages_session ON session_messages(session_id)"
        )

        await db.commit()
