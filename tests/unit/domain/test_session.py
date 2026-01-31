"""Unit tests for Session entity."""

import pytest
from datetime import datetime
from domain.entities.session import Session
from domain.entities.message import Message, MessageRole
from domain.value_objects.user_id import UserId


class TestSession:
    """Tests for Session entity."""

    def test_create_session(self, user_id):
        """Test creating a session."""
        session = Session(
            session_id="test-123",
            user_id=user_id
        )

        assert session.session_id == "test-123"
        assert session.user_id == user_id
        assert session.messages == []
        assert session.context == {}
        assert session.is_active is True
        assert session.created_at is not None
        assert session.updated_at is not None

    def test_session_timestamps_auto_set(self, user_id):
        """Test that timestamps are auto-set."""
        before = datetime.utcnow()
        session = Session(session_id="test", user_id=user_id)
        after = datetime.utcnow()

        assert before <= session.created_at <= after
        assert before <= session.updated_at <= after

    def test_add_message(self, session, message):
        """Test adding a message to session."""
        initial_count = session.message_count
        old_updated = session.updated_at

        session.add_message(message)

        assert session.message_count == initial_count + 1
        assert message in session.messages
        assert session.updated_at >= old_updated

    def test_add_multiple_messages(self, session):
        """Test adding multiple messages."""
        msg1 = Message(role=MessageRole.USER, content="Hello")
        msg2 = Message(role=MessageRole.ASSISTANT, content="Hi there!")
        msg3 = Message(role=MessageRole.USER, content="How are you?")

        session.add_message(msg1)
        session.add_message(msg2)
        session.add_message(msg3)

        assert session.message_count == 3
        assert session.messages[0] == msg1
        assert session.messages[1] == msg2
        assert session.messages[2] == msg3

    def test_get_messages_no_limit(self, session, message, assistant_message):
        """Test getting all messages without limit."""
        session.add_message(message)
        session.add_message(assistant_message)

        messages = session.get_messages()

        assert len(messages) == 2
        assert messages[0] == message
        assert messages[1] == assistant_message

    def test_get_messages_with_limit(self, session):
        """Test getting messages with limit."""
        for i in range(5):
            session.add_message(Message(role=MessageRole.USER, content=f"Message {i}"))

        messages = session.get_messages(limit=2)

        assert len(messages) == 2
        assert messages[0].content == "Message 3"
        assert messages[1].content == "Message 4"

    def test_clear_messages(self, session, message, assistant_message):
        """Test clearing all messages."""
        session.add_message(message)
        session.add_message(assistant_message)
        assert session.message_count == 2

        old_updated = session.updated_at
        session.clear_messages()

        assert session.message_count == 0
        assert session.messages == []
        assert session.updated_at >= old_updated

    def test_set_context(self, session):
        """Test setting context value."""
        old_updated = session.updated_at

        session.set_context("working_dir", "/home/user")

        assert session.context["working_dir"] == "/home/user"
        assert session.updated_at >= old_updated

    def test_get_context_existing(self, session):
        """Test getting existing context value."""
        session.set_context("key", "value")

        result = session.get_context("key")

        assert result == "value"

    def test_get_context_with_default(self, session):
        """Test getting non-existent context with default."""
        result = session.get_context("nonexistent", default="default_value")

        assert result == "default_value"

    def test_get_context_none_default(self, session):
        """Test getting non-existent context returns None by default."""
        result = session.get_context("nonexistent")

        assert result is None

    def test_close_session(self, session):
        """Test closing a session."""
        assert session.is_active is True
        old_updated = session.updated_at

        session.close()

        assert session.is_active is False
        assert session.updated_at >= old_updated

    def test_reopen_session(self, session):
        """Test reopening a closed session."""
        session.close()
        assert session.is_active is False
        old_updated = session.updated_at

        session.reopen()

        assert session.is_active is True
        assert session.updated_at >= old_updated

    def test_message_count_property(self, session):
        """Test message_count property."""
        assert session.message_count == 0

        session.add_message(Message(role=MessageRole.USER, content="Test"))
        assert session.message_count == 1

        session.add_message(Message(role=MessageRole.ASSISTANT, content="Reply"))
        assert session.message_count == 2

    def test_get_conversation_history(self, session):
        """Test getting conversation history in API format."""
        session.add_message(Message(role=MessageRole.USER, content="Hello"))
        session.add_message(Message(role=MessageRole.ASSISTANT, content="Hi!"))

        history = session.get_conversation_history()

        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hello"}
        assert history[1] == {"role": "assistant", "content": "Hi!"}
