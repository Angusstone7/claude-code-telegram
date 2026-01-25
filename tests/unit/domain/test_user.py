"""Unit tests for User entity."""

import pytest
from datetime import datetime
from domain.entities.user import User
from domain.value_objects.user_id import UserId
from domain.value_objects.role import Role, Permission


class TestUser:
    """Tests for User entity."""

    def test_create_user(self, user_id, user_role):
        """Test creating a user."""
        user = User(
            user_id=user_id,
            username="testuser",
            first_name="Test",
            last_name="User",
            role=user_role
        )

        assert user.user_id == user_id
        assert user.username == "testuser"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.role == user_role
        assert user.is_active is True
        assert user.created_at is not None
        assert user.last_command_at is None

    def test_user_created_at_auto_set(self, user_id, user_role):
        """Test that created_at is auto-set."""
        before = datetime.utcnow()
        user = User(
            user_id=user_id,
            username="test",
            first_name="Test",
            last_name=None,
            role=user_role
        )
        after = datetime.utcnow()

        assert before <= user.created_at <= after

    def test_user_can_execute_commands_active_user(self, user):
        """Test active user with execute permission can execute commands."""
        assert user.can_execute_commands() is True

    def test_user_cannot_execute_commands_when_inactive(self, user):
        """Test inactive user cannot execute commands."""
        user.deactivate()
        assert user.can_execute_commands() is False

    def test_user_cannot_execute_commands_readonly_role(self, user_id, readonly_role):
        """Test user with readonly role cannot execute commands."""
        user = User(
            user_id=user_id,
            username="readonly",
            first_name="Read",
            last_name="Only",
            role=readonly_role
        )
        assert user.can_execute_commands() is False

    def test_grant_role(self, user, admin_role):
        """Test granting a new role to user."""
        original_role = user.role
        user.grant_role(admin_role)

        assert user.role == admin_role
        assert user.role != original_role

    def test_deactivate_user(self, user):
        """Test deactivating a user."""
        assert user.is_active is True
        user.deactivate()
        assert user.is_active is False

    def test_activate_user(self, user):
        """Test activating a user."""
        user.deactivate()
        assert user.is_active is False
        user.activate()
        assert user.is_active is True

    def test_update_last_command(self, user):
        """Test updating last command timestamp."""
        assert user.last_command_at is None

        before = datetime.utcnow()
        user.update_last_command()
        after = datetime.utcnow()

        assert user.last_command_at is not None
        assert before <= user.last_command_at <= after

    def test_user_without_last_name(self, user_id, user_role):
        """Test creating user without last name."""
        user = User(
            user_id=user_id,
            username="noname",
            first_name="NoLast",
            last_name=None,
            role=user_role
        )
        assert user.last_name is None

    def test_user_without_username(self, user_id, user_role):
        """Test creating user without username."""
        user = User(
            user_id=user_id,
            username=None,
            first_name="NoUsername",
            last_name=None,
            role=user_role
        )
        assert user.username is None
