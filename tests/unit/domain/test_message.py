"""Unit tests for Message entity."""

import pytest
from datetime import datetime
from domain.entities.message import Message, MessageRole


class TestMessage:
    """Tests for Message entity."""

    def test_create_message(self):
        """Test creating a message."""
        msg = Message(
            role=MessageRole.USER,
            content="Hello, world!"
        )

        assert msg.role == MessageRole.USER
        assert msg.content == "Hello, world!"
        assert msg.timestamp is not None
        assert msg.tool_use_id is None
        assert msg.tool_result is None

    def test_message_timestamp_auto_set(self):
        """Test that timestamp is auto-set."""
        before = datetime.utcnow()
        msg = Message(role=MessageRole.USER, content="Test")
        after = datetime.utcnow()

        assert before <= msg.timestamp <= after

    def test_create_assistant_message(self):
        """Test creating an assistant message."""
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="Hello! How can I help?"
        )

        assert msg.role == MessageRole.ASSISTANT

    def test_create_system_message(self):
        """Test creating a system message."""
        msg = Message(
            role=MessageRole.SYSTEM,
            content="You are a helpful assistant."
        )

        assert msg.role == MessageRole.SYSTEM

    def test_message_with_tool_use_id(self):
        """Test message with tool use ID."""
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="",
            tool_use_id="tool-123"
        )

        assert msg.tool_use_id == "tool-123"

    def test_message_with_tool_result(self):
        """Test message with tool result."""
        msg = Message(
            role=MessageRole.USER,
            content="",
            tool_use_id="tool-123",
            tool_result='{"output": "success"}'
        )

        assert msg.tool_result == '{"output": "success"}'


class TestMessageSerialization:
    """Tests for Message serialization methods."""

    def test_to_dict_basic(self, message):
        """Test converting basic message to dict."""
        result = message.to_dict()

        assert result["role"] == "user"
        assert result["content"] == message.content
        assert "tool_use_id" not in result
        assert "tool_result" not in result

    def test_to_dict_with_tool_use_id(self):
        """Test to_dict includes tool_use_id when present."""
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="Using tool",
            tool_use_id="tool-456"
        )

        result = msg.to_dict()

        assert result["tool_use_id"] == "tool-456"

    def test_to_dict_with_tool_result(self):
        """Test to_dict includes tool_result when present."""
        msg = Message(
            role=MessageRole.USER,
            content="Result",
            tool_use_id="tool-789",
            tool_result="output here"
        )

        result = msg.to_dict()

        assert result["tool_use_id"] == "tool-789"
        assert result["tool_result"] == "output here"

    def test_from_dict_basic(self):
        """Test creating message from dict."""
        data = {"role": "user", "content": "Hello"}

        msg = Message.from_dict(data)

        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"

    def test_from_dict_assistant(self):
        """Test creating assistant message from dict."""
        data = {"role": "assistant", "content": "Hi there!"}

        msg = Message.from_dict(data)

        assert msg.role == MessageRole.ASSISTANT

    def test_from_dict_with_tool_fields(self):
        """Test creating message from dict with tool fields."""
        data = {
            "role": "assistant",
            "content": "",
            "tool_use_id": "tool-abc",
            "tool_result": "result data"
        }

        msg = Message.from_dict(data)

        assert msg.tool_use_id == "tool-abc"
        assert msg.tool_result == "result data"

    def test_roundtrip_serialization(self, message):
        """Test message survives roundtrip serialization."""
        data = message.to_dict()
        restored = Message.from_dict(data)

        assert restored.role == message.role
        assert restored.content == message.content


class TestMessageRole:
    """Tests for MessageRole enum."""

    def test_all_roles_exist(self):
        """Test all expected roles exist."""
        assert hasattr(MessageRole, "USER")
        assert hasattr(MessageRole, "ASSISTANT")
        assert hasattr(MessageRole, "SYSTEM")

    def test_role_values(self):
        """Test role enum values."""
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.SYSTEM.value == "system"

    def test_role_from_value(self):
        """Test creating role from string value."""
        assert MessageRole("user") == MessageRole.USER
        assert MessageRole("assistant") == MessageRole.ASSISTANT
        assert MessageRole("system") == MessageRole.SYSTEM
