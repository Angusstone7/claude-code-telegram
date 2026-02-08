import logging
import uuid
from typing import Optional, List, Dict
from datetime import datetime
from domain.entities.user import User
from domain.entities.session import Session
from domain.entities.command import Command, CommandStatus
from domain.entities.message import Message, MessageRole
from domain.value_objects.user_id import UserId
from domain.repositories.user_repository import UserRepository
from domain.repositories.session_repository import SessionRepository
from domain.repositories.command_repository import CommandRepository
from domain.services.command_execution_service import ICommandExecutionService, CommandExecutionResult
from domain.services.ai_service import IAIService, AIResponse
from domain.services.system_monitor_service import ISystemMonitor
from domain.services.system_prompts import SystemPrompts
from shared.config.settings import settings

logger = logging.getLogger(__name__)


class BotService:
    """Application service for bot operations"""

    def __init__(
        self,
        user_repository: UserRepository,
        session_repository: SessionRepository,
        command_repository: CommandRepository,
        ai_service: IAIService = None,
        command_executor: ICommandExecutionService = None,
        system_monitor: ISystemMonitor = None,
    ):
        self.user_repository = user_repository
        self.session_repository = session_repository
        self.command_repository = command_repository
        self.ai_service = ai_service  # Now optional - Claude Code proxy handles main AI interactions
        self.command_executor = command_executor
        self._system_monitor = system_monitor

    # User management
    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is in the whitelist (ALLOWED_USER_ID)"""
        allowed_ids = settings.telegram.allowed_user_ids
        # If whitelist is empty, allow everyone (with warning logged at startup)
        if not allowed_ids:
            return True
        return user_id in allowed_ids

    def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin (first user in ALLOWED_USER_ID)"""
        allowed_ids = settings.telegram.allowed_user_ids
        if not allowed_ids:
            return False
        return user_id == allowed_ids[0]

    async def get_or_create_user(self, user_id: int, username: str, first_name: str, last_name: str = None) -> Optional[User]:
        """Get existing user or create new one.

        Returns None if user is not in the whitelist (ALLOWED_USER_ID).
        First user in ALLOWED_USER_ID gets admin role.
        """
        # Check whitelist first
        if not self.is_user_allowed(user_id):
            logger.warning(f"Access denied for user {user_id} (@{username}) - not in ALLOWED_USER_ID whitelist")
            return None

        user_id_vo = UserId.from_int(user_id)
        user = await self.user_repository.find_by_id(user_id_vo)

        if user is None:
            from domain.value_objects.role import Role
            # First user in whitelist gets admin role
            role = Role.admin() if self.is_admin(user_id) else Role.user()
            user = User(
                user_id=user_id_vo,
                username=username,
                first_name=first_name,
                last_name=last_name,
                role=role
            )
            await self.user_repository.save(user)
            role_name = "admin" if self.is_admin(user_id) else "user"
            logger.info(f"Created new {role_name}: {user_id} (@{username})")

        return user

    async def authorize_user(self, user_id: int) -> Optional[User]:
        """Check if user is authorized to use the bot"""
        user = await self.user_repository.find_by_id(UserId.from_int(user_id))
        if user and user.is_active and user.can_execute_commands():
            return user
        return None

    # Session management
    async def get_or_create_session(self, user_id: int) -> Session:
        """Get active session or create new one"""
        user_id_vo = UserId.from_int(user_id)
        session = await self.session_repository.find_active_by_user(user_id_vo)

        if session is None:
            session_id = str(uuid.uuid4())
            session = Session(
                session_id=session_id,
                user_id=user_id_vo
            )
            await self.session_repository.save(session)
            logger.info(f"Created new session: {session_id} for user: {user_id}")

        return session

    async def clear_session(self, user_id: int) -> None:
        """Clear user's session history"""
        session = await self.get_or_create_session(user_id)
        session.clear_messages()
        await self.session_repository.save(session)

    # AI Chat (Legacy - now handled by Claude Code proxy)
    async def chat(
        self,
        user_id: int,
        message: str,
        system_prompt: str = None,
        enable_tools: bool = True
    ) -> tuple[str, List[Dict]]:
        """Process user message with AI (Legacy method - use Claude Code proxy instead)"""
        if not self.ai_service:
            raise RuntimeError("AI service not configured. Use Claude Code proxy for AI interactions.")
        session = await self.get_or_create_session(user_id)

        # Define available tools
        tools = []
        if enable_tools:
            tools = [
                {
                    "name": "bash",
                    "description": "Execute a bash command on the remote server via SSH. "
                                   "You have full access to manage the server, read files, "
                                   "install packages, work with docker, etc.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The bash command to execute"
                            }
                        },
                        "required": ["command"]
                    }
                },
                {
                    "name": "get_metrics",
                    "description": "Get current system metrics (CPU, memory, disk usage)",
                    "input_schema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "list_containers",
                    "description": "List all Docker containers with their status",
                    "input_schema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            ]

        # Get AI response
        system_prompt = system_prompt or SystemPrompts.DEVOPS
        response = await self.ai_service.chat_with_session(
            session=session,
            user_message=message,
            tools=tools,
            system_prompt=system_prompt
        )

        await self.session_repository.save(session)

        return response.content, response.tool_calls

    async def handle_tool_result(
        self,
        user_id: int,
        tool_id: str,
        result: str
    ) -> tuple[str, List[Dict]]:
        """Handle tool execution result and get follow-up from AI (Legacy method)"""
        if not self.ai_service:
            raise RuntimeError("AI service not configured. Use Claude Code proxy for AI interactions.")
        session = await self.get_or_create_session(user_id)

        # Add tool result to session
        from domain.entities.message import Message, MessageRole
        session.add_message(Message(
            role=MessageRole.USER,
            content=[{
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result
            }]
        ))

        # Get follow-up response
        response = await self.ai_service.chat_with_session(
            session=session,
            user_message="",  # Empty message since we just added tool result
            system_prompt=SystemPrompts.DEVOPS
        )

        await self.session_repository.save(session)

        return response.content, response.tool_calls

    # Command execution
    async def create_pending_command(self, user_id: int, command: str) -> Command:
        """Create a pending command for approval"""
        cmd = Command(
            command_id=str(uuid.uuid4()),
            user_id=user_id,
            command=command
        )
        await self.command_repository.save(cmd)
        return cmd

    async def execute_command(self, command_id: str) -> Optional[CommandExecutionResult]:
        """Execute approved command. Returns None if execution failed."""
        command = await self.command_repository.find_by_id(command_id)
        if not command:
            raise ValueError(f"Command not found: {command_id}")

        command.start_execution()
        await self.command_repository.save(command)

        result = None
        try:
            result = await self.command_executor.execute(command.command)
            command.complete(
                output=result.full_output,
                exit_code=result.exit_code
            )
        except Exception as e:
            command.fail(str(e))

        await self.command_repository.save(command)
        return result

    async def reject_command(self, command_id: str, reason: str = None) -> None:
        """Reject pending command"""
        command = await self.command_repository.find_by_id(command_id)
        if not command:
            raise ValueError(f"Command not found: {command_id}")

        command.reject(reason)
        await self.command_repository.save(command)

    # System info
    async def get_system_info(self) -> Dict:
        """Get system information"""
        if not self._system_monitor:
            raise RuntimeError("System monitor not configured")

        metrics = await self._system_monitor.get_metrics()
        return {
            "metrics": metrics.to_dict(),
            "top_processes": await self._system_monitor.get_top_processes(limit=5),
            "alerts": await self._system_monitor.check_alerts(metrics)
        }

    async def get_user_stats(self, user_id: int) -> Dict:
        """
        Get user statistics.

        Uses UserStats value object to encapsulate stats calculation
        (fixes Feature Envy - service no longer formats user's own data).
        """
        from domain.value_objects.user_stats import UserStats

        user = await self.user_repository.find_by_id(UserId.from_int(user_id))
        if not user:
            return {}

        commands = await self.command_repository.find_by_user(user_id, limit=1000)
        sessions = await self.session_repository.find_by_user(UserId.from_int(user_id))

        # Delegate stats calculation to the value object
        stats = UserStats.from_user(user, commands, sessions)
        return stats.to_dict()

    async def cleanup_old_data(self) -> Dict[str, int]:
        """Clean up old data"""
        old_commands = await self.command_repository.delete_old_commands(days=30)
        old_sessions = await self.session_repository.delete_old_sessions(days=7)

        return {
            "commands_deleted": old_commands,
            "sessions_deleted": old_sessions
        }
