"""Unit tests for BotService application service."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import uuid

from application.services.bot_service import BotService
from domain.entities.user import User
from domain.entities.session import Session
from domain.entities.command import Command, CommandStatus
from domain.entities.message import Message, MessageRole
from domain.value_objects.user_id import UserId
from domain.value_objects.role import Role
from domain.services.command_execution_service import CommandExecutionResult


@pytest.fixture(autouse=True)
def mock_bot_service_settings():
    """Mock settings for all BotService tests."""
    with patch("application.services.bot_service.settings") as mock_settings:
        mock_settings.telegram.allowed_user_ids = [123456789, 999999, 111111, 123456]
        yield mock_settings


class TestBotServiceUserManagement:
    """Tests for BotService user management methods."""

    @pytest.fixture
    def bot_service(self, mock_user_repository, mock_session_repository, mock_command_repository):
        """Create BotService with mocked dependencies."""
        return BotService(
            user_repository=mock_user_repository,
            session_repository=mock_session_repository,
            command_repository=mock_command_repository
        )

    @pytest.mark.asyncio
    async def test_get_or_create_user_existing(self, bot_service, mock_user_repository, user):
        """Test getting existing user."""
        mock_user_repository.find_by_id.return_value = user

        result = await bot_service.get_or_create_user(
            user_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User"
        )

        assert result == user
        mock_user_repository.find_by_id.assert_called_once()
        mock_user_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_user_new(self, bot_service, mock_user_repository):
        """Test creating new user when not exists."""
        mock_user_repository.find_by_id.return_value = None

        result = await bot_service.get_or_create_user(
            user_id=999999,
            username="newuser",
            first_name="New",
            last_name="User"
        )

        assert result.user_id == UserId(999999)
        assert result.username == "newuser"
        assert result.first_name == "New"
        assert result.last_name == "User"
        assert result.role.name == "user"  # Default role
        mock_user_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_user_no_last_name(self, bot_service, mock_user_repository):
        """Test creating user without last name."""
        mock_user_repository.find_by_id.return_value = None

        result = await bot_service.get_or_create_user(
            user_id=111111,
            username="noname",
            first_name="Single"
        )

        assert result.last_name is None
        mock_user_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_authorize_user_valid(self, bot_service, mock_user_repository, user):
        """Test authorizing valid active user."""
        mock_user_repository.find_by_id.return_value = user

        result = await bot_service.authorize_user(123456789)

        assert result == user

    @pytest.mark.asyncio
    async def test_authorize_user_not_found(self, bot_service, mock_user_repository):
        """Test authorizing non-existent user."""
        mock_user_repository.find_by_id.return_value = None

        result = await bot_service.authorize_user(999999)

        assert result is None

    @pytest.mark.asyncio
    async def test_authorize_user_inactive(self, bot_service, mock_user_repository, user):
        """Test authorizing inactive user."""
        user.deactivate()
        mock_user_repository.find_by_id.return_value = user

        result = await bot_service.authorize_user(123456789)

        assert result is None

    @pytest.mark.asyncio
    async def test_authorize_user_readonly_role(self, bot_service, mock_user_repository, user_id, readonly_role):
        """Test authorizing user with readonly role."""
        readonly_user = User(
            user_id=user_id,
            username="readonly",
            first_name="Read",
            last_name=None,
            role=readonly_role,
            is_active=True
        )
        mock_user_repository.find_by_id.return_value = readonly_user

        result = await bot_service.authorize_user(123456789)

        assert result is None  # Cannot execute commands


class TestBotServiceSessionManagement:
    """Tests for BotService session management methods."""

    @pytest.fixture
    def bot_service(self, mock_user_repository, mock_session_repository, mock_command_repository):
        """Create BotService with mocked dependencies."""
        return BotService(
            user_repository=mock_user_repository,
            session_repository=mock_session_repository,
            command_repository=mock_command_repository
        )

    @pytest.mark.asyncio
    async def test_get_or_create_session_existing(self, bot_service, mock_session_repository, session):
        """Test getting existing active session."""
        mock_session_repository.find_active_by_user.return_value = session

        result = await bot_service.get_or_create_session(123456789)

        assert result == session
        mock_session_repository.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_session_new(self, bot_service, mock_session_repository):
        """Test creating new session when no active exists."""
        mock_session_repository.find_active_by_user.return_value = None

        result = await bot_service.get_or_create_session(123456789)

        assert result.user_id == UserId(123456789)
        assert result.is_active is True
        assert result.messages == []
        mock_session_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_session(self, bot_service, mock_session_repository, user_id):
        """Test clearing session messages."""
        session = Session(session_id="test-123", user_id=user_id)
        session.add_message(Message(role=MessageRole.USER, content="Hello"))
        session.add_message(Message(role=MessageRole.ASSISTANT, content="Hi!"))
        mock_session_repository.find_active_by_user.return_value = session

        await bot_service.clear_session(123456789)

        assert session.message_count == 0
        mock_session_repository.save.assert_called_once()


class TestBotServiceCommandManagement:
    """Tests for BotService command management methods."""

    @pytest.fixture
    def bot_service(self, mock_user_repository, mock_session_repository, mock_command_repository, mock_command_executor):
        """Create BotService with mocked dependencies."""
        return BotService(
            user_repository=mock_user_repository,
            session_repository=mock_session_repository,
            command_repository=mock_command_repository,
            command_executor=mock_command_executor
        )

    @pytest.mark.asyncio
    async def test_create_pending_command(self, bot_service, mock_command_repository):
        """Test creating a pending command."""
        result = await bot_service.create_pending_command(
            user_id=123456,
            command="ls -la"
        )

        assert result.user_id == 123456
        assert result.command == "ls -la"
        assert result.status == CommandStatus.PENDING
        mock_command_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_pending_command_generates_uuid(self, bot_service, mock_command_repository):
        """Test that create_pending_command generates unique command_id."""
        result1 = await bot_service.create_pending_command(123, "cmd1")
        result2 = await bot_service.create_pending_command(123, "cmd2")

        assert result1.command_id != result2.command_id
        # Both should be valid UUIDs
        uuid.UUID(result1.command_id)
        uuid.UUID(result2.command_id)

    @pytest.mark.asyncio
    async def test_execute_command_success(self, bot_service, mock_command_repository, mock_command_executor, approved_command):
        """Test executing an approved command successfully."""
        mock_command_repository.find_by_id.return_value = approved_command
        mock_command_executor.execute.return_value = Mock(
            full_output="command output",
            exit_code=0,
            error=None
        )

        result = await bot_service.execute_command(approved_command.command_id)

        assert result.full_output == "command output"
        assert result.exit_code == 0
        assert approved_command.status == CommandStatus.COMPLETED
        assert approved_command.output == "command output"

    @pytest.mark.asyncio
    async def test_execute_command_failure(self, bot_service, mock_command_repository, mock_command_executor, approved_command):
        """Test executing a command that fails."""
        mock_command_repository.find_by_id.return_value = approved_command
        mock_command_executor.execute.side_effect = Exception("Connection refused")

        result = await bot_service.execute_command(approved_command.command_id)

        assert result is None  # Returns None on failure
        assert approved_command.status == CommandStatus.FAILED
        assert approved_command.error == "Connection refused"

    @pytest.mark.asyncio
    async def test_execute_command_not_found(self, bot_service, mock_command_repository):
        """Test executing non-existent command."""
        mock_command_repository.find_by_id.return_value = None

        with pytest.raises(ValueError, match="Command not found"):
            await bot_service.execute_command("nonexistent-id")

    @pytest.mark.asyncio
    async def test_reject_command(self, bot_service, mock_command_repository, command):
        """Test rejecting a pending command."""
        mock_command_repository.find_by_id.return_value = command

        await bot_service.reject_command(command.command_id, "Not allowed")

        assert command.status == CommandStatus.REJECTED
        assert command.error == "Not allowed"
        mock_command_repository.save.assert_called()

    @pytest.mark.asyncio
    async def test_reject_command_default_reason(self, bot_service, mock_command_repository, command):
        """Test rejecting a command with default reason."""
        mock_command_repository.find_by_id.return_value = command

        await bot_service.reject_command(command.command_id)

        assert command.status == CommandStatus.REJECTED
        assert command.error == "Command rejected by user"

    @pytest.mark.asyncio
    async def test_reject_command_not_found(self, bot_service, mock_command_repository):
        """Test rejecting non-existent command."""
        mock_command_repository.find_by_id.return_value = None

        with pytest.raises(ValueError, match="Command not found"):
            await bot_service.reject_command("nonexistent-id")


class TestBotServiceAI:
    """Tests for BotService AI-related methods."""

    @pytest.fixture
    def bot_service_with_ai(self, mock_user_repository, mock_session_repository, mock_command_repository, mock_ai_service):
        """Create BotService with AI service."""
        return BotService(
            user_repository=mock_user_repository,
            session_repository=mock_session_repository,
            command_repository=mock_command_repository,
            ai_service=mock_ai_service
        )

    @pytest.fixture
    def bot_service_no_ai(self, mock_user_repository, mock_session_repository, mock_command_repository):
        """Create BotService without AI service."""
        return BotService(
            user_repository=mock_user_repository,
            session_repository=mock_session_repository,
            command_repository=mock_command_repository
        )

    @pytest.mark.asyncio
    async def test_chat_without_ai_service_raises_error(self, bot_service_no_ai):
        """Test that chat without AI service raises error."""
        with pytest.raises(RuntimeError, match="AI service not configured"):
            await bot_service_no_ai.chat(123456, "Hello")

    @pytest.mark.asyncio
    async def test_chat_with_ai_service(self, bot_service_with_ai, mock_session_repository, mock_ai_service, user_id):
        """Test chat with AI service configured."""
        session = Session(session_id="test", user_id=user_id)
        mock_session_repository.find_active_by_user.return_value = session
        mock_ai_service.chat_with_session.return_value = Mock(
            content="AI response",
            tool_calls=[]
        )

        content, tool_calls = await bot_service_with_ai.chat(123456789, "Hello")

        assert content == "AI response"
        assert tool_calls == []
        mock_ai_service.chat_with_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_tool_result_without_ai_raises_error(self, bot_service_no_ai):
        """Test that handle_tool_result without AI raises error."""
        with pytest.raises(RuntimeError, match="AI service not configured"):
            await bot_service_no_ai.handle_tool_result(123456, "tool-id", "result")


class TestBotServiceStatistics:
    """Tests for BotService statistics methods."""

    @pytest.fixture
    def bot_service(self, mock_user_repository, mock_session_repository, mock_command_repository):
        """Create BotService with mocked dependencies."""
        return BotService(
            user_repository=mock_user_repository,
            session_repository=mock_session_repository,
            command_repository=mock_command_repository
        )

    @pytest.mark.asyncio
    async def test_get_user_stats(self, bot_service, mock_user_repository, mock_session_repository, mock_command_repository, user, user_id, session):
        """Test getting user statistics."""
        from unittest.mock import MagicMock
        from domain.entities.command import CommandStatus

        # Create mock commands with different statuses
        mock_commands = []
        for _ in range(5):
            cmd = MagicMock()
            cmd.status = CommandStatus.COMPLETED
            mock_commands.append(cmd)
        failed_cmd = MagicMock()
        failed_cmd.status = CommandStatus.FAILED
        mock_commands.append(failed_cmd)

        mock_user_repository.find_by_id.return_value = user
        mock_command_repository.find_by_user = AsyncMock(return_value=mock_commands)
        mock_session_repository.find_by_user = AsyncMock(return_value=[session])

        result = await bot_service.get_user_stats(123456789)

        assert result["user"]["username"] == "testuser"
        assert result["user"]["role"] == "user"
        assert result["commands"]["by_status"]["completed"] == 5
        assert result["commands"]["by_status"]["failed"] == 1
        assert result["commands"]["total"] == 6
        assert result["sessions"]["total"] == 1

    @pytest.mark.asyncio
    async def test_get_user_stats_not_found(self, bot_service, mock_user_repository):
        """Test getting stats for non-existent user."""
        mock_user_repository.find_by_id.return_value = None

        result = await bot_service.get_user_stats(999999)

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_system_info(self, mock_user_repository, mock_session_repository, mock_command_repository):
        """Test getting system information."""
        mock_monitor = Mock()
        mock_metrics = Mock()
        mock_metrics.to_dict.return_value = {"cpu": 25.5, "memory": 60.0}
        mock_monitor.get_metrics = AsyncMock(return_value=mock_metrics)
        mock_monitor.get_top_processes = AsyncMock(return_value=[{"name": "python", "cpu": 10}])
        mock_monitor.check_alerts = AsyncMock(return_value=[])

        service = BotService(
            user_repository=mock_user_repository,
            session_repository=mock_session_repository,
            command_repository=mock_command_repository,
            system_monitor=mock_monitor,
        )

        result = await service.get_system_info()

        assert result["metrics"] == {"cpu": 25.5, "memory": 60.0}
        assert len(result["top_processes"]) == 1
        assert result["alerts"] == []


class TestBotServiceCleanup:
    """Tests for BotService cleanup methods."""

    @pytest.fixture
    def bot_service(self, mock_user_repository, mock_session_repository, mock_command_repository):
        """Create BotService with mocked dependencies."""
        return BotService(
            user_repository=mock_user_repository,
            session_repository=mock_session_repository,
            command_repository=mock_command_repository
        )

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, bot_service, mock_command_repository, mock_session_repository):
        """Test cleaning up old data."""
        mock_command_repository.delete_old_commands = AsyncMock(return_value=10)
        mock_session_repository.delete_old_sessions = AsyncMock(return_value=5)

        result = await bot_service.cleanup_old_data()

        assert result["commands_deleted"] == 10
        assert result["sessions_deleted"] == 5
