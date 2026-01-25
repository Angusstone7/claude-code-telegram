"""Unit tests for Role value object."""

import pytest
from domain.value_objects.role import Role, Permission


class TestRole:
    """Tests for Role value object."""

    def test_create_role(self):
        """Test creating a role with permissions."""
        role = Role(
            name="custom",
            permissions={Permission.EXECUTE_COMMANDS, Permission.VIEW_LOGS}
        )

        assert role.name == "custom"
        assert Permission.EXECUTE_COMMANDS in role.permissions
        assert Permission.VIEW_LOGS in role.permissions

    def test_role_is_frozen(self):
        """Test that role is immutable."""
        role = Role.user()

        with pytest.raises(Exception):  # FrozenInstanceError
            role.name = "hacked"

    def test_has_permission_true(self, user_role):
        """Test has_permission returns True for granted permissions."""
        assert user_role.has_permission(Permission.EXECUTE_COMMANDS) is True
        assert user_role.has_permission(Permission.VIEW_LOGS) is True

    def test_has_permission_false(self, user_role):
        """Test has_permission returns False for non-granted permissions."""
        assert user_role.has_permission(Permission.MANAGE_USERS) is False
        assert user_role.has_permission(Permission.MANAGE_DOCKER) is False

    def test_can_execute_with_permission(self, user_role):
        """Test can_execute returns True when has EXECUTE_COMMANDS."""
        assert user_role.can_execute() is True

    def test_can_execute_without_permission(self, readonly_role):
        """Test can_execute returns False without EXECUTE_COMMANDS."""
        assert readonly_role.can_execute() is False


class TestRoleFactoryMethods:
    """Tests for Role factory methods."""

    def test_admin_role(self, admin_role):
        """Test admin role has all permissions."""
        assert admin_role.name == "admin"
        # Admin should have all permissions
        for permission in Permission:
            assert admin_role.has_permission(permission) is True

    def test_user_role(self, user_role):
        """Test user role has correct permissions."""
        assert user_role.name == "user"
        assert user_role.has_permission(Permission.EXECUTE_COMMANDS) is True
        assert user_role.has_permission(Permission.VIEW_LOGS) is True
        assert user_role.has_permission(Permission.MANAGE_SESSIONS) is True
        assert user_role.has_permission(Permission.VIEW_METRICS) is True
        # Should not have admin permissions
        assert user_role.has_permission(Permission.MANAGE_USERS) is False
        assert user_role.has_permission(Permission.MANAGE_DOCKER) is False

    def test_readonly_role(self, readonly_role):
        """Test readonly role has limited permissions."""
        assert readonly_role.name == "readonly"
        assert readonly_role.has_permission(Permission.VIEW_LOGS) is True
        assert readonly_role.has_permission(Permission.VIEW_METRICS) is True
        # Should not have execution permissions
        assert readonly_role.has_permission(Permission.EXECUTE_COMMANDS) is False
        assert readonly_role.has_permission(Permission.MANAGE_SESSIONS) is False

    def test_devops_role(self, devops_role):
        """Test devops role has appropriate permissions."""
        assert devops_role.name == "devops"
        assert devops_role.has_permission(Permission.EXECUTE_COMMANDS) is True
        assert devops_role.has_permission(Permission.MANAGE_DOCKER) is True
        assert devops_role.has_permission(Permission.MANAGE_GITLAB) is True
        assert devops_role.has_permission(Permission.SCHEDULE_TASKS) is True
        # Should not have user management
        assert devops_role.has_permission(Permission.MANAGE_USERS) is False


class TestPermission:
    """Tests for Permission enum."""

    def test_all_permissions_exist(self):
        """Test all expected permissions exist."""
        expected = [
            "EXECUTE_COMMANDS",
            "VIEW_LOGS",
            "MANAGE_SESSIONS",
            "MANAGE_USERS",
            "MANAGE_DOCKER",
            "MANAGE_GITLAB",
            "VIEW_METRICS",
            "SCHEDULE_TASKS",
        ]
        for perm_name in expected:
            assert hasattr(Permission, perm_name)

    def test_permission_values(self):
        """Test permission enum values."""
        assert Permission.EXECUTE_COMMANDS.value == "execute_commands"
        assert Permission.VIEW_LOGS.value == "view_logs"
        assert Permission.MANAGE_USERS.value == "manage_users"
