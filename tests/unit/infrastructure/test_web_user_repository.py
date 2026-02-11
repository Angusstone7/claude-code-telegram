"""Unit tests for SQLiteWebUserRepository."""

import os
import pytest
from datetime import datetime, timedelta

from domain.entities.web_user import WebUser
from infrastructure.persistence.sqlite_web_user_repository import SQLiteWebUserRepository


class TestSQLiteWebUserRepositoryInit:
    """Tests for repository initialization and table creation."""

    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self, tmp_path):
        """Test that init_db() creates all required tables."""
        db_path = str(tmp_path / "test.db")
        repo = SQLiteWebUserRepository(db_path=db_path)
        await repo.init_db()

        assert os.path.exists(db_path)

    @pytest.mark.asyncio
    async def test_init_db_idempotent(self, tmp_path):
        """Test that init_db() can be called multiple times safely."""
        db_path = str(tmp_path / "test.db")
        repo = SQLiteWebUserRepository(db_path=db_path)
        await repo.init_db()
        await repo.init_db()  # Should not raise


class TestWebUserCRUD:
    """Tests for WebUser CRUD operations."""

    @pytest.fixture
    async def repo(self, tmp_path):
        """Create a repository with initialized database."""
        db_path = str(tmp_path / "test.db")
        repo = SQLiteWebUserRepository(db_path=db_path)
        await repo.init_db()
        return repo

    @pytest.fixture
    def sample_user(self):
        """Create a sample WebUser for tests."""
        return WebUser.create(
            username="testuser",
            password_hash="hashed_pwd_123",
            display_name="Test User",
            telegram_id=123456789,
            role="admin",
            created_by="system",
        )

    @pytest.mark.asyncio
    async def test_save_and_find_by_id(self, repo, sample_user):
        """Test saving a user and retrieving by ID."""
        await repo.save(sample_user)

        found = await repo.find_by_id(sample_user.id)

        assert found is not None
        assert found.id == sample_user.id
        assert found.username == "testuser"
        assert found.password_hash == "hashed_pwd_123"
        assert found.display_name == "Test User"
        assert found.telegram_id == 123456789
        assert found.role == "admin"
        assert found.is_active is True
        assert found.created_by == "system"

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, repo):
        """Test that find_by_id returns None for non-existent user."""
        found = await repo.find_by_id("non-existent-id")
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_username(self, repo, sample_user):
        """Test finding a user by username."""
        await repo.save(sample_user)

        found = await repo.find_by_username("testuser")

        assert found is not None
        assert found.username == "testuser"
        assert found.id == sample_user.id

    @pytest.mark.asyncio
    async def test_find_by_username_not_found(self, repo):
        """Test that find_by_username returns None for non-existent username."""
        found = await repo.find_by_username("ghost")
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_telegram_id(self, repo, sample_user):
        """Test finding a user by telegram_id."""
        await repo.save(sample_user)

        found = await repo.find_by_telegram_id(123456789)

        assert found is not None
        assert found.telegram_id == 123456789
        assert found.id == sample_user.id

    @pytest.mark.asyncio
    async def test_find_by_telegram_id_not_found(self, repo):
        """Test that find_by_telegram_id returns None for non-existent telegram_id."""
        found = await repo.find_by_telegram_id(999999)
        assert found is None

    @pytest.mark.asyncio
    async def test_find_all_empty(self, repo):
        """Test find_all on empty database."""
        users = await repo.find_all()
        assert users == []

    @pytest.mark.asyncio
    async def test_find_all_multiple_users(self, repo):
        """Test find_all with multiple users."""
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
        await repo.save(user1)
        await repo.save(user2)

        users = await repo.find_all()

        assert len(users) == 2
        usernames = {u.username for u in users}
        assert usernames == {"user_one", "user_two"}

    @pytest.mark.asyncio
    async def test_update(self, repo, sample_user):
        """Test updating user fields."""
        await repo.save(sample_user)

        sample_user.display_name = "Updated Name"
        sample_user.deactivate()
        await repo.update(sample_user)

        found = await repo.find_by_id(sample_user.id)
        assert found is not None
        assert found.display_name == "Updated Name"
        assert found.is_active is False

    @pytest.mark.asyncio
    async def test_delete(self, repo, sample_user):
        """Test deleting a user."""
        await repo.save(sample_user)

        result = await repo.delete(sample_user.id)

        assert result is True
        found = await repo.find_by_id(sample_user.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_non_existent(self, repo):
        """Test deleting a non-existent user returns False."""
        result = await repo.delete("non-existent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_save_preserves_timestamps(self, repo, sample_user):
        """Test that save preserves created_at and updated_at from entity."""
        await repo.save(sample_user)

        found = await repo.find_by_id(sample_user.id)
        assert found is not None
        # ISO format round-trip: compare to second precision
        assert found.created_at.replace(microsecond=0) == sample_user.created_at.replace(microsecond=0)

    @pytest.mark.asyncio
    async def test_save_user_without_telegram_id(self, repo):
        """Test saving a user without telegram_id."""
        user = WebUser.create(
            username="notguser",
            password_hash="hash",
            display_name="No Telegram",
        )
        await repo.save(user)

        found = await repo.find_by_id(user.id)
        assert found is not None
        assert found.telegram_id is None


class TestRefreshTokenOperations:
    """Tests for refresh token CRUD operations."""

    @pytest.fixture
    async def repo(self, tmp_path):
        """Create a repository with initialized database."""
        db_path = str(tmp_path / "test.db")
        repo = SQLiteWebUserRepository(db_path=db_path)
        await repo.init_db()
        return repo

    @pytest.fixture
    async def saved_user(self, repo):
        """Create and save a user to use as token owner."""
        user = WebUser.create(
            username="tokenowner",
            password_hash="hash",
            display_name="Token Owner",
        )
        await repo.save(user)
        return user

    @pytest.mark.asyncio
    async def test_save_and_find_refresh_token(self, repo, saved_user):
        """Test saving a refresh token and finding it by hash."""
        token_hash = "abc123hash"
        expires_at = datetime.utcnow() + timedelta(days=30)

        await repo.save_refresh_token(
            token_id="token-001",
            user_id=saved_user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent="TestBrowser/1.0",
        )

        found = await repo.find_by_token_hash(token_hash)

        assert found is not None
        assert found["id"] == "token-001"
        assert found["user_id"] == saved_user.id
        assert found["token_hash"] == token_hash
        assert found["user_agent"] == "TestBrowser/1.0"
        assert found["revoked_at"] is None

    @pytest.mark.asyncio
    async def test_find_by_token_hash_not_found(self, repo):
        """Test that find_by_token_hash returns None for non-existent hash."""
        found = await repo.find_by_token_hash("non_existent_hash")
        assert found is None

    @pytest.mark.asyncio
    async def test_revoke_refresh_token(self, repo, saved_user):
        """Test revoking a refresh token makes it unfindable by hash."""
        token_hash = "revoke_test_hash"
        expires_at = datetime.utcnow() + timedelta(days=30)

        await repo.save_refresh_token(
            token_id="token-revoke",
            user_id=saved_user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        await repo.revoke("token-revoke")

        # Revoked tokens should not be found by find_by_token_hash
        found = await repo.find_by_token_hash(token_hash)
        assert found is None

    @pytest.mark.asyncio
    async def test_save_token_alias(self, repo, saved_user):
        """Test that save_token() is an alias for save_refresh_token()."""
        token_hash = "alias_hash"
        expires_at = datetime.utcnow() + timedelta(days=7)

        await repo.save_token(
            token_id="token-alias",
            user_id=saved_user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        found = await repo.find_by_token_hash(token_hash)
        assert found is not None
        assert found["id"] == "token-alias"


class TestLoginAttemptOperations:
    """Tests for login attempt recording and counting."""

    @pytest.fixture
    async def repo(self, tmp_path):
        """Create a repository with initialized database."""
        db_path = str(tmp_path / "test.db")
        repo = SQLiteWebUserRepository(db_path=db_path)
        await repo.init_db()
        return repo

    @pytest.mark.asyncio
    async def test_record_login_attempt(self, repo):
        """Test recording a login attempt does not raise."""
        await repo.record(
            username="testuser",
            ip_address="192.168.1.1",
            success=True,
        )
        # No error means success

    @pytest.mark.asyncio
    async def test_count_failed_recent_no_failures(self, repo):
        """Test count_failed_recent returns 0 when no failures exist."""
        since = datetime.utcnow() - timedelta(hours=1)
        count = await repo.count_failed_recent(
            username="testuser",
            ip_address="192.168.1.1",
            since=since,
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_failed_recent_with_failures(self, repo):
        """Test count_failed_recent counts only failed attempts."""
        # Record 3 failed and 1 successful attempt
        for _ in range(3):
            await repo.record("failuser", "10.0.0.1", success=False)
        await repo.record("failuser", "10.0.0.1", success=True)

        since = datetime.utcnow() - timedelta(hours=1)
        count = await repo.count_failed_recent("failuser", "10.0.0.1", since)

        assert count == 3

    @pytest.mark.asyncio
    async def test_count_failed_recent_filters_by_time(self, repo):
        """Test count_failed_recent only counts attempts after 'since'."""
        # Record a failure now
        await repo.record("timeuser", "10.0.0.1", success=False)

        # Query with 'since' set to the future
        since_future = datetime.utcnow() + timedelta(hours=1)
        count = await repo.count_failed_recent("timeuser", "10.0.0.1", since_future)

        assert count == 0

    @pytest.mark.asyncio
    async def test_count_failed_recent_filters_by_username_and_ip(self, repo):
        """Test count_failed_recent filters by both username and IP."""
        await repo.record("user_a", "10.0.0.1", success=False)
        await repo.record("user_a", "10.0.0.2", success=False)
        await repo.record("user_b", "10.0.0.1", success=False)

        since = datetime.utcnow() - timedelta(hours=1)

        count_a_ip1 = await repo.count_failed_recent("user_a", "10.0.0.1", since)
        count_a_ip2 = await repo.count_failed_recent("user_a", "10.0.0.2", since)
        count_b_ip1 = await repo.count_failed_recent("user_b", "10.0.0.1", since)

        assert count_a_ip1 == 1
        assert count_a_ip2 == 1
        assert count_b_ip1 == 1


class TestHashToken:
    """Tests for the static hash_token helper."""

    def test_hash_token_returns_sha256(self):
        """Test that hash_token returns a SHA-256 hex digest."""
        import hashlib

        token = "my_refresh_token"
        expected = hashlib.sha256(token.encode()).hexdigest()

        result = SQLiteWebUserRepository.hash_token(token)

        assert result == expected
        assert len(result) == 64  # SHA-256 hex length

    def test_hash_token_deterministic(self):
        """Test that hash_token returns same result for same input."""
        result1 = SQLiteWebUserRepository.hash_token("same_token")
        result2 = SQLiteWebUserRepository.hash_token("same_token")
        assert result1 == result2

    def test_hash_token_different_for_different_input(self):
        """Test that hash_token returns different results for different inputs."""
        result1 = SQLiteWebUserRepository.hash_token("token_a")
        result2 = SQLiteWebUserRepository.hash_token("token_b")
        assert result1 != result2
