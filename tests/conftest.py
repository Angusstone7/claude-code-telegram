"""
Pytest configuration and shared fixtures for the test suite.
"""

import os
import pytest
import asyncio
from datetime import datetime
from typing import Generator
from unittest.mock import Mock, AsyncMock

# Set required environment variables BEFORE any application imports
os.environ.setdefault("TELEGRAM_TOKEN", "test-telegram-token-12345")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-api-key-12345")
os.environ.setdefault("ALLOWED_USER_ID", "123456789")

# Domain entities
from domain.entities.user import User
from domain.entities.session import Session
from domain.entities.command import Command, CommandStatus
from domain.entities.message import Message, MessageRole

# Value objects
from domain.value_objects.user_id import UserId
from domain.value_objects.role import Role, Permission
from domain.value_objects.ai_provider_config import AIProviderConfig, AIProviderType, AIModelConfig


# ============================================================================
# Pytest configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Value Object Fixtures
# ============================================================================

@pytest.fixture
def user_id() -> UserId:
    """Create a test UserId."""
    return UserId(123456789)


@pytest.fixture
def admin_role() -> Role:
    """Create admin role."""
    return Role.admin()


@pytest.fixture
def user_role() -> Role:
    """Create user role."""
    return Role.user()


@pytest.fixture
def readonly_role() -> Role:
    """Create readonly role."""
    return Role.readonly()


@pytest.fixture
def devops_role() -> Role:
    """Create devops role."""
    return Role.devops()


@pytest.fixture
def ai_config() -> AIProviderConfig:
    """Create a test AI provider config."""
    return AIProviderConfig(
        provider_type=AIProviderType.ANTHROPIC,
        api_key="test-api-key-12345"
    )


# ============================================================================
# Entity Fixtures
# ============================================================================

@pytest.fixture
def user(user_id: UserId, user_role: Role) -> User:
    """Create a test user."""
    return User(
        user_id=user_id,
        username="testuser",
        first_name="Test",
        last_name="User",
        role=user_role,
        is_active=True
    )


@pytest.fixture
def admin_user(user_id: UserId, admin_role: Role) -> User:
    """Create a test admin user."""
    return User(
        user_id=UserId(987654321),
        username="admin",
        first_name="Admin",
        last_name="User",
        role=admin_role,
        is_active=True
    )


@pytest.fixture
def session(user_id: UserId) -> Session:
    """Create a test session."""
    return Session(
        session_id="test-session-123",
        user_id=user_id,
        messages=[],
        context={}
    )


@pytest.fixture
def message() -> Message:
    """Create a test message."""
    return Message(
        role=MessageRole.USER,
        content="Hello, this is a test message"
    )


@pytest.fixture
def assistant_message() -> Message:
    """Create a test assistant message."""
    return Message(
        role=MessageRole.ASSISTANT,
        content="Hello! How can I help you?"
    )


@pytest.fixture
def command() -> Command:
    """Create a test command."""
    return Command(
        command_id="cmd-123",
        user_id=123456789,
        command="ls -la",
        status=CommandStatus.PENDING
    )


@pytest.fixture
def approved_command() -> Command:
    """Create an approved command."""
    cmd = Command(
        command_id="cmd-456",
        user_id=123456789,
        command="echo hello",
        status=CommandStatus.PENDING
    )
    cmd.approve()
    return cmd


@pytest.fixture
def dangerous_command() -> Command:
    """Create a dangerous command for testing."""
    return Command(
        command_id="cmd-danger",
        user_id=123456789,
        command="rm -rf /",
        status=CommandStatus.PENDING
    )


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_bot() -> Mock:
    """Create a mock Telegram bot."""
    bot = Mock()
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    return bot


@pytest.fixture
def mock_user_repository() -> Mock:
    """Create a mock user repository."""
    repo = Mock()
    repo.find_by_id = AsyncMock()
    repo.save = AsyncMock()
    repo.delete = AsyncMock()
    repo.find_all = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_session_repository() -> Mock:
    """Create a mock session repository."""
    repo = Mock()
    repo.find_by_id = AsyncMock()
    repo.find_active_by_user = AsyncMock()
    repo.save = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_command_repository() -> Mock:
    """Create a mock command repository."""
    repo = Mock()
    repo.find_by_id = AsyncMock()
    repo.save = AsyncMock()
    repo.find_pending = AsyncMock(return_value=[])
    repo.get_statistics = AsyncMock(return_value={})
    return repo


@pytest.fixture
def mock_ai_service() -> Mock:
    """Create a mock AI service."""
    service = Mock()
    service.chat_with_session = AsyncMock(return_value=Mock(
        content="Test response",
        tool_calls=[]
    ))
    return service


@pytest.fixture
def mock_command_executor() -> Mock:
    """Create a mock command executor."""
    executor = Mock()
    executor.execute = AsyncMock(return_value=Mock(
        output="command output",
        exit_code=0,
        error=None
    ))
    return executor
