"""Tests for User entity actions"""
import pytest
from datetime import datetime
from domain.entities.user import User
from domain.value_objects.user_id import UserId
from domain.value_objects.role import Role


def test_user_deactivation():
    """Test that user can be deactivated"""
    user_id = UserId(12345)
    role = Role.admin()
    user = User(
        user_id=user_id,
        username="testuser",
        first_name="Test",
        last_name="User",
        role=role,
        is_active=True
    )

    assert user.is_active is True

    user.deactivate()

    assert user.is_active is False
    assert user.can_execute_commands() is False


def test_user_activation():
    """Test that user can be activated"""
    user_id = UserId(12345)
    role = Role.user()
    user = User(
        user_id=user_id,
        username="testuser",
        first_name="Test",
        last_name="User",
        role=role,
        is_active=False
    )

    assert user.is_active is False

    user.activate()

    assert user.is_active is True


def test_update_last_command():
    """Test that last_command_at is updated"""
    user_id = UserId(12345)
    role = Role.user()
    user = User(
        user_id=user_id,
        username="testuser",
        first_name="Test",
        last_name="User",
        role=role
    )

    assert user.last_command_at is None

    user.update_last_command()

    assert user.last_command_at is not None
    assert isinstance(user.last_command_at, datetime)


def test_grant_role():
    """Test granting a new role to user"""
    user_id = UserId(12345)
    user = User(
        user_id=user_id,
        username="testuser",
        first_name="Test",
        last_name="User",
        role=Role.user()
    )

    assert user.role == Role.user()

    user.grant_role(Role.admin())

    assert user.role == Role.admin()
