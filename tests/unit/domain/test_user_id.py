"""Unit tests for UserId value object."""

import pytest
from domain.value_objects.user_id import UserId


class TestUserId:
    """Tests for UserId value object."""

    def test_create_user_id(self):
        """Test creating a valid UserId."""
        user_id = UserId(123456789)

        assert user_id.value == 123456789

    def test_user_id_is_frozen(self):
        """Test that UserId is immutable."""
        user_id = UserId(123)

        with pytest.raises(Exception):  # FrozenInstanceError
            user_id.value = 456

    def test_create_user_id_zero_raises_error(self):
        """Test that zero UserId raises ValueError."""
        with pytest.raises(ValueError, match="positive integer"):
            UserId(0)

    def test_create_user_id_negative_raises_error(self):
        """Test that negative UserId raises ValueError."""
        with pytest.raises(ValueError, match="positive integer"):
            UserId(-1)

    def test_from_int(self):
        """Test creating UserId from int."""
        user_id = UserId.from_int(123456)

        assert user_id.value == 123456

    def test_from_str_valid(self):
        """Test creating UserId from valid string."""
        user_id = UserId.from_str("789012")

        assert user_id.value == 789012

    def test_from_str_invalid_raises_error(self):
        """Test creating UserId from invalid string raises error."""
        with pytest.raises(ValueError, match="Invalid UserId string"):
            UserId.from_str("not_a_number")

    def test_from_str_empty_raises_error(self):
        """Test creating UserId from empty string raises error."""
        with pytest.raises(ValueError):
            UserId.from_str("")

    def test_int_conversion(self):
        """Test converting UserId to int."""
        user_id = UserId(12345)

        assert int(user_id) == 12345

    def test_str_conversion(self):
        """Test converting UserId to string."""
        user_id = UserId(67890)

        assert str(user_id) == "67890"

    def test_equality(self):
        """Test UserId equality."""
        id1 = UserId(123)
        id2 = UserId(123)
        id3 = UserId(456)

        assert id1 == id2
        assert id1 != id3

    def test_hash(self):
        """Test UserId can be used in sets/dicts."""
        id1 = UserId(123)
        id2 = UserId(123)

        user_set = {id1}
        assert id2 in user_set

        user_dict = {id1: "user1"}
        assert user_dict[id2] == "user1"

    def test_large_user_id(self):
        """Test UserId with large Telegram-like ID."""
        large_id = 9876543210123
        user_id = UserId(large_id)

        assert user_id.value == large_id
        assert int(user_id) == large_id
