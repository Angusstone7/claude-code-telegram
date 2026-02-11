"""Unit tests for WebUser entity."""

import pytest
from datetime import datetime

from domain.entities.web_user import WebUser


class TestWebUserCreate:
    """Tests for WebUser.create() factory method."""

    def test_create_with_valid_data(self):
        """Test creating a WebUser with all valid fields."""
        user = WebUser.create(
            username="admin_user",
            password_hash="hashed_password_123",
            display_name="Admin User",
            telegram_id=123456789,
            role="admin",
            created_by="system",
        )

        assert user.username == "admin_user"
        assert user.password_hash == "hashed_password_123"
        assert user.display_name == "Admin User"
        assert user.telegram_id == 123456789
        assert user.role == "admin"
        assert user.is_active is True
        assert user.created_by == "system"
        assert user.id is not None
        assert len(user.id) == 36  # UUID format

    def test_create_with_minimal_data(self):
        """Test creating a WebUser with only required fields."""
        user = WebUser.create(
            username="testuser",
            password_hash="hash123",
            display_name="Test",
        )

        assert user.username == "testuser"
        assert user.telegram_id is None
        assert user.role == "admin"
        assert user.created_by is None
        assert user.is_active is True

    def test_create_sets_timestamps(self):
        """Test that create() sets created_at and updated_at."""
        before = datetime.utcnow()
        user = WebUser.create(
            username="timeuser",
            password_hash="hash",
            display_name="Time User",
        )
        after = datetime.utcnow()

        assert before <= user.created_at <= after
        assert before <= user.updated_at <= after
        assert user.created_at == user.updated_at

    def test_create_generates_unique_ids(self):
        """Test that create() generates unique IDs for each user."""
        user1 = WebUser.create(
            username="user_one",
            password_hash="hash1",
            display_name="User One",
        )
        user2 = WebUser.create(
            username="user_two",
            password_hash="hash2",
            display_name="User Two",
        )

        assert user1.id != user2.id

    def test_create_with_custom_role(self):
        """Test creating a WebUser with a non-default role."""
        user = WebUser.create(
            username="viewer",
            password_hash="hash",
            display_name="Viewer User",
            role="viewer",
        )

        assert user.role == "viewer"


class TestWebUserCreateValidation:
    """Tests for WebUser.create() validation."""

    def test_create_with_username_too_short(self):
        """Test that username shorter than 3 characters is rejected."""
        with pytest.raises(ValueError, match="username must be 3-50 characters"):
            WebUser.create(
                username="ab",
                password_hash="hash",
                display_name="Short",
            )

    def test_create_with_username_one_char(self):
        """Test that single-character username is rejected."""
        with pytest.raises(ValueError, match="username must be 3-50 characters"):
            WebUser.create(
                username="a",
                password_hash="hash",
                display_name="Single",
            )

    def test_create_with_empty_username(self):
        """Test that empty username is rejected."""
        with pytest.raises(ValueError, match="username must be 3-50 characters"):
            WebUser.create(
                username="",
                password_hash="hash",
                display_name="Empty",
            )

    def test_create_with_invalid_chars_in_username(self):
        """Test that username with special characters is rejected."""
        with pytest.raises(ValueError, match="username must be 3-50 characters"):
            WebUser.create(
                username="user@name",
                password_hash="hash",
                display_name="Special",
            )

    def test_create_with_spaces_in_username(self):
        """Test that username with spaces is rejected."""
        with pytest.raises(ValueError, match="username must be 3-50 characters"):
            WebUser.create(
                username="user name",
                password_hash="hash",
                display_name="Spaced",
            )

    def test_create_with_valid_username_chars(self):
        """Test that username with allowed chars [a-zA-Z0-9_-] works."""
        user = WebUser.create(
            username="Valid_User-123",
            password_hash="hash",
            display_name="Valid",
        )
        assert user.username == "Valid_User-123"

    def test_create_with_negative_telegram_id(self):
        """Test that negative telegram_id is rejected."""
        with pytest.raises(ValueError, match="telegram_id must be positive"):
            WebUser.create(
                username="neguser",
                password_hash="hash",
                display_name="Negative",
                telegram_id=-1,
            )

    def test_create_with_zero_telegram_id(self):
        """Test that zero telegram_id is rejected."""
        with pytest.raises(ValueError, match="telegram_id must be positive"):
            WebUser.create(
                username="zerouser",
                password_hash="hash",
                display_name="Zero",
                telegram_id=0,
            )

    def test_create_with_display_name_too_long(self):
        """Test that display_name over 100 characters is rejected."""
        long_name = "A" * 101
        with pytest.raises(ValueError, match="display_name must be 100 characters or less"):
            WebUser.create(
                username="longname",
                password_hash="hash",
                display_name=long_name,
            )

    def test_create_with_display_name_exactly_100(self):
        """Test that display_name of exactly 100 characters is accepted."""
        name_100 = "A" * 100
        user = WebUser.create(
            username="exact100",
            password_hash="hash",
            display_name=name_100,
        )
        assert len(user.display_name) == 100


class TestWebUserUpdateProfile:
    """Tests for WebUser.update_profile() method."""

    def test_update_display_name(self):
        """Test updating display_name."""
        user = WebUser.create(
            username="updater",
            password_hash="hash",
            display_name="Original Name",
        )
        original_updated = user.updated_at

        user.update_profile(display_name="New Name")

        assert user.display_name == "New Name"
        assert user.updated_at >= original_updated

    def test_update_telegram_id(self):
        """Test updating telegram_id."""
        user = WebUser.create(
            username="teluser",
            password_hash="hash",
            display_name="Tel User",
        )

        user.update_profile(telegram_id=99999)

        assert user.telegram_id == 99999

    def test_update_both_fields(self):
        """Test updating both display_name and telegram_id simultaneously."""
        user = WebUser.create(
            username="bothuser",
            password_hash="hash",
            display_name="Both User",
        )

        user.update_profile(display_name="Updated Both", telegram_id=55555)

        assert user.display_name == "Updated Both"
        assert user.telegram_id == 55555

    def test_update_profile_invalid_display_name_empty(self):
        """Test that empty display_name is rejected."""
        user = WebUser.create(
            username="emptydn",
            password_hash="hash",
            display_name="Valid Name",
        )

        with pytest.raises(ValueError, match="display_name must be 1-100 characters"):
            user.update_profile(display_name="")

    def test_update_profile_invalid_display_name_too_long(self):
        """Test that display_name over 100 characters is rejected in update."""
        user = WebUser.create(
            username="longdn",
            password_hash="hash",
            display_name="Valid Name",
        )

        with pytest.raises(ValueError, match="display_name must be 1-100 characters"):
            user.update_profile(display_name="X" * 101)

    def test_update_profile_invalid_telegram_id_negative(self):
        """Test that negative telegram_id is rejected in update."""
        user = WebUser.create(
            username="negtid",
            password_hash="hash",
            display_name="Neg Tid",
        )

        with pytest.raises(ValueError, match="telegram_id must be positive"):
            user.update_profile(telegram_id=-5)

    def test_update_profile_invalid_telegram_id_zero(self):
        """Test that zero telegram_id is rejected in update."""
        user = WebUser.create(
            username="zerotid",
            password_hash="hash",
            display_name="Zero Tid",
        )

        with pytest.raises(ValueError, match="telegram_id must be positive"):
            user.update_profile(telegram_id=0)

    def test_update_profile_no_args_still_updates_timestamp(self):
        """Test that calling update_profile() with no args still updates updated_at."""
        user = WebUser.create(
            username="noargs",
            password_hash="hash",
            display_name="No Args",
        )
        old_updated = user.updated_at

        user.update_profile()

        assert user.updated_at >= old_updated


class TestWebUserChangePassword:
    """Tests for WebUser.change_password() method."""

    def test_change_password(self):
        """Test changing the password hash."""
        user = WebUser.create(
            username="pwduser",
            password_hash="old_hash",
            display_name="Pwd User",
        )

        user.change_password("new_hash_value")

        assert user.password_hash == "new_hash_value"

    def test_change_password_updates_timestamp(self):
        """Test that change_password updates updated_at."""
        user = WebUser.create(
            username="pwdtime",
            password_hash="old_hash",
            display_name="Pwd Time",
        )
        old_updated = user.updated_at

        user.change_password("new_hash")

        assert user.updated_at >= old_updated


class TestWebUserActivation:
    """Tests for WebUser.deactivate() and activate() methods."""

    def test_deactivate(self):
        """Test deactivating a user."""
        user = WebUser.create(
            username="deactuser",
            password_hash="hash",
            display_name="Deact User",
        )
        assert user.is_active is True

        user.deactivate()

        assert user.is_active is False

    def test_activate(self):
        """Test activating a previously deactivated user."""
        user = WebUser.create(
            username="actuser",
            password_hash="hash",
            display_name="Act User",
        )
        user.deactivate()
        assert user.is_active is False

        user.activate()

        assert user.is_active is True

    def test_deactivate_updates_timestamp(self):
        """Test that deactivate() updates updated_at."""
        user = WebUser.create(
            username="deactts",
            password_hash="hash",
            display_name="Deact TS",
        )
        old_updated = user.updated_at

        user.deactivate()

        assert user.updated_at >= old_updated

    def test_activate_updates_timestamp(self):
        """Test that activate() updates updated_at."""
        user = WebUser.create(
            username="actts",
            password_hash="hash",
            display_name="Act TS",
        )
        user.deactivate()
        old_updated = user.updated_at

        user.activate()

        assert user.updated_at >= old_updated

    def test_double_deactivate(self):
        """Test that deactivating an already deactivated user works without error."""
        user = WebUser.create(
            username="dbldeact",
            password_hash="hash",
            display_name="Dbl Deact",
        )
        user.deactivate()
        user.deactivate()

        assert user.is_active is False

    def test_double_activate(self):
        """Test that activating an already active user works without error."""
        user = WebUser.create(
            username="dblact",
            password_hash="hash",
            display_name="Dbl Act",
        )
        user.activate()

        assert user.is_active is True


class TestWebUserIsAdmin:
    """Tests for WebUser.is_admin property."""

    def test_is_admin_with_admin_role(self):
        """Test is_admin returns True for admin role."""
        user = WebUser.create(
            username="adminrole",
            password_hash="hash",
            display_name="Admin Role",
            role="admin",
        )

        assert user.is_admin is True

    def test_is_admin_with_default_role(self):
        """Test is_admin returns True for default role (admin)."""
        user = WebUser.create(
            username="defaultrole",
            password_hash="hash",
            display_name="Default Role",
        )

        assert user.is_admin is True

    def test_is_not_admin_with_viewer_role(self):
        """Test is_admin returns False for viewer role."""
        user = WebUser.create(
            username="viewerrole",
            password_hash="hash",
            display_name="Viewer Role",
            role="viewer",
        )

        assert user.is_admin is False

    def test_is_not_admin_with_user_role(self):
        """Test is_admin returns False for user role."""
        user = WebUser.create(
            username="userrole",
            password_hash="hash",
            display_name="User Role",
            role="user",
        )

        assert user.is_admin is False
