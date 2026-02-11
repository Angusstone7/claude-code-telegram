"""Unit tests for AuthService — JWT authentication, user management, rate limiting."""

import hashlib
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import jwt
import pytest
from argon2 import PasswordHasher

from application.services.auth_service import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    LOGIN_WINDOW_MINUTES,
    MAX_LOGIN_ATTEMPTS,
    REFRESH_TOKEN_EXPIRE_DAYS,
    AuthService,
)
from domain.entities.web_user import WebUser
from domain.value_objects.web_auth import Credentials, JWTClaims, TokenPair

ph = PasswordHasher()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASSWORD = "securePassword123"
PASSWORD_HASH = ph.hash(PASSWORD)


def _make_user(
    user_id: str | None = None,
    username: str = "testuser",
    password: str = PASSWORD,
    display_name: str = "Test User",
    role: str = "admin",
    telegram_id: int | None = None,
    is_active: bool = True,
    created_by: str | None = None,
) -> WebUser:
    """Create a WebUser with a real argon2 password hash."""
    uid = user_id or str(uuid.uuid4())
    now = datetime.utcnow()
    return WebUser(
        id=uid,
        username=username,
        password_hash=ph.hash(password),
        display_name=display_name,
        role=role,
        telegram_id=telegram_id,
        is_active=is_active,
        created_at=now,
        updated_at=now,
        created_by=created_by,
    )


def _make_mock_repo() -> Mock:
    """Create a fully mocked SQLiteWebUserRepository."""
    repo = Mock()
    repo.init_db = AsyncMock()
    repo.save = AsyncMock()
    repo.update = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=None)
    repo.find_by_username = AsyncMock(return_value=None)
    repo.find_by_telegram_id = AsyncMock(return_value=None)
    repo.find_all = AsyncMock(return_value=[])
    repo.record = AsyncMock()
    repo.count_failed_recent = AsyncMock(return_value=0)
    repo.save_refresh_token = AsyncMock()
    repo.find_by_token_hash = AsyncMock(return_value=None)
    repo.revoke = AsyncMock()
    return repo


# ===========================================================================
# Login flow
# ===========================================================================


class TestAuthServiceLogin:
    """Tests for the login flow."""

    @pytest.fixture
    def repo(self):
        return _make_mock_repo()

    @pytest.fixture
    def service(self, repo):
        return AuthService(repository=repo)

    @pytest.mark.asyncio
    async def test_login_success_returns_token_pair(self, service, repo):
        """Successful login returns a TokenPair with access and refresh tokens."""
        user = _make_user()
        repo.find_by_username.return_value = user
        repo.count_failed_recent.return_value = 0

        creds = Credentials(username="testuser", password=PASSWORD)
        result = await service.login(creds, ip_address="127.0.0.1")

        assert result is not None
        assert isinstance(result, TokenPair)
        assert result.access_token
        assert result.refresh_token
        assert result.expires_in == ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert result.token_type == "bearer"

        # Record successful attempt
        repo.record.assert_called_once_with("testuser", "127.0.0.1", True)
        # Refresh token stored
        repo.save_refresh_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_wrong_password_returns_none(self, service, repo):
        """Login with wrong password returns None and records failure."""
        user = _make_user()
        repo.find_by_username.return_value = user

        creds = Credentials(username="testuser", password="wrongPassword1")
        result = await service.login(creds, ip_address="127.0.0.1")

        assert result is None
        repo.record.assert_called_once_with("testuser", "127.0.0.1", False)
        repo.save_refresh_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_nonexistent_user_returns_none(self, service, repo):
        """Login with unknown username returns None."""
        repo.find_by_username.return_value = None

        creds = Credentials(username="nouser", password="somePassword1")
        result = await service.login(creds, ip_address="127.0.0.1")

        assert result is None
        repo.record.assert_called_once_with("nouser", "127.0.0.1", False)

    @pytest.mark.asyncio
    async def test_login_inactive_user_returns_none(self, service, repo):
        """Login for inactive user returns None."""
        user = _make_user(is_active=False)
        repo.find_by_username.return_value = user

        creds = Credentials(username="testuser", password=PASSWORD)
        result = await service.login(creds, ip_address="127.0.0.1")

        assert result is None
        repo.record.assert_called_once_with("testuser", "127.0.0.1", False)

    @pytest.mark.asyncio
    async def test_login_stores_user_agent(self, service, repo):
        """Login stores user_agent when provided."""
        user = _make_user()
        repo.find_by_username.return_value = user

        creds = Credentials(username="testuser", password=PASSWORD)
        await service.login(creds, ip_address="127.0.0.1", user_agent="Mozilla/5.0")

        call_kwargs = repo.save_refresh_token.call_args
        assert call_kwargs[1]["user_agent"] == "Mozilla/5.0" or \
               (call_kwargs[0] if call_kwargs[0] else False)


# ===========================================================================
# Rate limiting
# ===========================================================================


class TestAuthServiceRateLimiting:
    """Tests for login rate limiting."""

    @pytest.fixture
    def repo(self):
        return _make_mock_repo()

    @pytest.fixture
    def service(self, repo):
        return AuthService(repository=repo)

    @pytest.mark.asyncio
    async def test_rate_limited_after_max_attempts(self, service, repo):
        """After MAX_LOGIN_ATTEMPTS failed attempts, login is blocked."""
        user = _make_user()
        repo.find_by_username.return_value = user
        repo.count_failed_recent.return_value = MAX_LOGIN_ATTEMPTS  # already at limit

        creds = Credentials(username="testuser", password=PASSWORD)
        result = await service.login(creds, ip_address="10.0.0.1")

        assert result is None
        # Should not even attempt password verification or record attempt
        repo.record.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_rate_limited_below_max(self, service, repo):
        """Login proceeds when failed attempts are below the limit."""
        user = _make_user()
        repo.find_by_username.return_value = user
        repo.count_failed_recent.return_value = MAX_LOGIN_ATTEMPTS - 1

        creds = Credentials(username="testuser", password=PASSWORD)
        result = await service.login(creds, ip_address="10.0.0.1")

        assert result is not None
        repo.record.assert_called_once_with("testuser", "10.0.0.1", True)

    @pytest.mark.asyncio
    async def test_is_rate_limited_public_method(self, service, repo):
        """Public is_rate_limited method delegates correctly."""
        repo.count_failed_recent.return_value = MAX_LOGIN_ATTEMPTS

        result = await service.is_rate_limited("testuser", "10.0.0.1")

        assert result is True
        repo.count_failed_recent.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_not_rate_limited_public_method(self, service, repo):
        """Public is_rate_limited returns False when under limit."""
        repo.count_failed_recent.return_value = 0

        result = await service.is_rate_limited("testuser", "10.0.0.1")

        assert result is False


# ===========================================================================
# Token generation / verification
# ===========================================================================


class TestAuthServiceTokenVerification:
    """Tests for access token generation and verification."""

    @pytest.fixture
    def repo(self):
        return _make_mock_repo()

    @pytest.fixture
    def service(self, repo):
        return AuthService(repository=repo)

    @pytest.mark.asyncio
    async def test_verify_valid_access_token(self, service, repo):
        """verify_access_token returns JWTClaims for a valid token."""
        user = _make_user(user_id="user-uuid-123")
        repo.find_by_username.return_value = user

        creds = Credentials(username="testuser", password=PASSWORD)
        token_pair = await service.login(creds, ip_address="127.0.0.1")

        claims = service.verify_access_token(token_pair.access_token)

        assert claims is not None
        assert isinstance(claims, JWTClaims)
        assert claims.sub == "user-uuid-123"
        assert claims.username == "testuser"
        assert claims.role == "admin"
        assert claims.exp > datetime.utcnow()

    def test_verify_expired_token_returns_none(self, service):
        """verify_access_token returns None for an expired token."""
        payload = {
            "sub": "user-123",
            "username": "testuser",
            "role": "admin",
            "iat": datetime.utcnow() - timedelta(hours=2),
            "exp": datetime.utcnow() - timedelta(hours=1),
        }
        expired_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        result = service.verify_access_token(expired_token)

        assert result is None

    def test_verify_invalid_token_returns_none(self, service):
        """verify_access_token returns None for a malformed token."""
        result = service.verify_access_token("this.is.not.a.valid.token")

        assert result is None

    def test_verify_token_wrong_secret_returns_none(self, service):
        """verify_access_token returns None for a token signed with different key."""
        payload = {
            "sub": "user-123",
            "username": "testuser",
            "role": "admin",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        wrong_key_token = jwt.encode(payload, "wrong-secret-key", algorithm=JWT_ALGORITHM)

        result = service.verify_access_token(wrong_key_token)

        assert result is None

    @pytest.mark.asyncio
    async def test_token_pair_contains_correct_expiry(self, service, repo):
        """TokenPair expires_in matches ACCESS_TOKEN_EXPIRE_MINUTES."""
        user = _make_user()
        repo.find_by_username.return_value = user

        creds = Credentials(username="testuser", password=PASSWORD)
        token_pair = await service.login(creds, ip_address="127.0.0.1")

        assert token_pair.expires_in == ACCESS_TOKEN_EXPIRE_MINUTES * 60


# ===========================================================================
# Token refresh
# ===========================================================================


class TestAuthServiceRefresh:
    """Tests for token refresh."""

    @pytest.fixture
    def repo(self):
        return _make_mock_repo()

    @pytest.fixture
    def service(self, repo):
        return AuthService(repository=repo)

    @pytest.mark.asyncio
    async def test_refresh_success_returns_new_pair(self, service, repo):
        """Successful refresh returns new TokenPair and revokes old token."""
        user = _make_user(user_id="user-123")
        old_refresh = "old-refresh-token-value"
        old_hash = hashlib.sha256(old_refresh.encode()).hexdigest()

        repo.find_by_token_hash.return_value = {
            "id": "token-id-1",
            "user_id": "user-123",
            "token_hash": old_hash,
            "expires_at": datetime.utcnow() + timedelta(days=7),
            "created_at": datetime.utcnow(),
            "revoked_at": None,
            "user_agent": None,
        }
        repo.find_by_id.return_value = user

        result = await service.refresh(old_refresh)

        assert result is not None
        assert isinstance(result, TokenPair)
        assert result.access_token
        assert result.refresh_token
        # Old token revoked
        repo.revoke.assert_called_once_with("token-id-1")
        # New refresh token stored
        repo.save_refresh_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_expired_token_returns_none(self, service, repo):
        """Expired refresh token returns None and is revoked."""
        old_refresh = "expired-refresh-token"
        old_hash = hashlib.sha256(old_refresh.encode()).hexdigest()

        repo.find_by_token_hash.return_value = {
            "id": "token-id-2",
            "user_id": "user-456",
            "token_hash": old_hash,
            "expires_at": datetime.utcnow() - timedelta(days=1),  # expired
            "created_at": datetime.utcnow() - timedelta(days=8),
            "revoked_at": None,
            "user_agent": None,
        }

        result = await service.refresh(old_refresh)

        assert result is None
        repo.revoke.assert_called_once_with("token-id-2")

    @pytest.mark.asyncio
    async def test_refresh_unknown_token_returns_none(self, service, repo):
        """Unknown refresh token returns None."""
        repo.find_by_token_hash.return_value = None

        result = await service.refresh("completely-unknown-token")

        assert result is None
        repo.revoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_inactive_user_returns_none(self, service, repo):
        """Refresh for an inactive user returns None and revokes the token."""
        inactive_user = _make_user(user_id="user-789", is_active=False)
        old_refresh = "some-refresh-token"
        old_hash = hashlib.sha256(old_refresh.encode()).hexdigest()

        repo.find_by_token_hash.return_value = {
            "id": "token-id-3",
            "user_id": "user-789",
            "token_hash": old_hash,
            "expires_at": datetime.utcnow() + timedelta(days=7),
            "created_at": datetime.utcnow(),
            "revoked_at": None,
            "user_agent": None,
        }
        repo.find_by_id.return_value = inactive_user

        result = await service.refresh(old_refresh)

        assert result is None
        repo.revoke.assert_called_once_with("token-id-3")

    @pytest.mark.asyncio
    async def test_refresh_user_not_found_returns_none(self, service, repo):
        """Refresh when user no longer exists returns None and revokes token."""
        old_refresh = "orphaned-refresh-token"
        old_hash = hashlib.sha256(old_refresh.encode()).hexdigest()

        repo.find_by_token_hash.return_value = {
            "id": "token-id-4",
            "user_id": "deleted-user-id",
            "token_hash": old_hash,
            "expires_at": datetime.utcnow() + timedelta(days=7),
            "created_at": datetime.utcnow(),
            "revoked_at": None,
            "user_agent": None,
        }
        repo.find_by_id.return_value = None  # user deleted

        result = await service.refresh(old_refresh)

        assert result is None
        repo.revoke.assert_called_once_with("token-id-4")


# ===========================================================================
# Logout
# ===========================================================================


class TestAuthServiceLogout:
    """Tests for logout (refresh token revocation)."""

    @pytest.fixture
    def repo(self):
        return _make_mock_repo()

    @pytest.fixture
    def service(self, repo):
        return AuthService(repository=repo)

    @pytest.mark.asyncio
    async def test_logout_revokes_refresh_token(self, service, repo):
        """Logout revokes the refresh token and returns True."""
        refresh = "active-refresh-token"
        token_hash = hashlib.sha256(refresh.encode()).hexdigest()

        repo.find_by_token_hash.return_value = {
            "id": "token-id-99",
            "user_id": "user-id",
            "token_hash": token_hash,
            "expires_at": datetime.utcnow() + timedelta(days=7),
            "created_at": datetime.utcnow(),
            "revoked_at": None,
            "user_agent": None,
        }

        result = await service.logout(refresh)

        assert result is True
        repo.revoke.assert_called_once_with("token-id-99")

    @pytest.mark.asyncio
    async def test_logout_unknown_token_returns_false(self, service, repo):
        """Logout with unknown token returns False."""
        repo.find_by_token_hash.return_value = None

        result = await service.logout("unknown-refresh-token")

        assert result is False
        repo.revoke.assert_not_called()


# ===========================================================================
# User CRUD
# ===========================================================================


class TestAuthServiceCreateUser:
    """Tests for create_user."""

    @pytest.fixture
    def repo(self):
        return _make_mock_repo()

    @pytest.fixture
    def service(self, repo):
        return AuthService(repository=repo)

    @pytest.mark.asyncio
    async def test_create_user_success(self, service, repo):
        """create_user creates a user and saves it."""
        repo.find_by_username.return_value = None
        repo.find_by_telegram_id.return_value = None

        user = await service.create_user(
            username="newuser",
            password="strongPassword1",
            display_name="New User",
            telegram_id=12345,
            created_by="admin-id",
        )

        assert isinstance(user, WebUser)
        assert user.username == "newuser"
        assert user.display_name == "New User"
        assert user.telegram_id == 12345
        assert user.created_by == "admin-id"
        assert user.is_active is True
        # Password should be hashed, not plaintext
        assert user.password_hash != "strongPassword1"
        ph.verify(user.password_hash, "strongPassword1")  # should not raise
        repo.save.assert_called_once_with(user)

    @pytest.mark.asyncio
    async def test_create_user_without_telegram_id(self, service, repo):
        """create_user works without telegram_id."""
        repo.find_by_username.return_value = None

        user = await service.create_user(
            username="noteluser",
            password="strongPassword1",
            display_name="No Telegram",
        )

        assert user.telegram_id is None
        repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username_raises(self, service, repo):
        """create_user raises ValueError if username already exists."""
        repo.find_by_username.return_value = _make_user(username="existing")

        with pytest.raises(ValueError, match="already exists"):
            await service.create_user(
                username="existing",
                password="strongPassword1",
                display_name="Duplicate",
            )

        repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_telegram_id_raises(self, service, repo):
        """create_user raises ValueError if telegram_id is already linked."""
        repo.find_by_username.return_value = None
        repo.find_by_telegram_id.return_value = _make_user(telegram_id=99999)

        with pytest.raises(ValueError, match="Telegram ID.*already linked"):
            await service.create_user(
                username="uniqueuser",
                password="strongPassword1",
                display_name="Telegram Conflict",
                telegram_id=99999,
            )

        repo.save.assert_not_called()


# ===========================================================================
# Update profile
# ===========================================================================


class TestAuthServiceUpdateProfile:
    """Tests for update_profile."""

    @pytest.fixture
    def repo(self):
        return _make_mock_repo()

    @pytest.fixture
    def service(self, repo):
        return AuthService(repository=repo)

    @pytest.mark.asyncio
    async def test_update_display_name(self, service, repo):
        """update_profile changes display_name."""
        user = _make_user(user_id="user-abc")
        repo.find_by_id.return_value = user

        result = await service.update_profile("user-abc", display_name="New Name")

        assert result is not None
        assert result.display_name == "New Name"
        repo.update.assert_called_once_with(user)

    @pytest.mark.asyncio
    async def test_update_telegram_id(self, service, repo):
        """update_profile changes telegram_id."""
        user = _make_user(user_id="user-abc")
        repo.find_by_id.return_value = user
        repo.find_by_telegram_id.return_value = None

        result = await service.update_profile("user-abc", telegram_id=55555)

        assert result is not None
        assert result.telegram_id == 55555
        repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_telegram_id_conflict_raises(self, service, repo):
        """update_profile raises ValueError if telegram_id belongs to another user."""
        user = _make_user(user_id="user-abc")
        conflicting_user = _make_user(user_id="other-user", telegram_id=77777)

        repo.find_by_id.return_value = user
        repo.find_by_telegram_id.return_value = conflicting_user

        with pytest.raises(ValueError, match="Telegram ID.*already linked"):
            await service.update_profile("user-abc", telegram_id=77777)

        repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_profile_same_user_telegram_id_ok(self, service, repo):
        """update_profile allows setting same telegram_id if it belongs to same user."""
        user = _make_user(user_id="user-abc", telegram_id=88888)
        repo.find_by_id.return_value = user
        repo.find_by_telegram_id.return_value = user  # same user

        result = await service.update_profile("user-abc", telegram_id=88888)

        assert result is not None
        repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_profile_user_not_found(self, service, repo):
        """update_profile returns None when user is not found."""
        repo.find_by_id.return_value = None

        result = await service.update_profile("nonexistent-id", display_name="X")

        assert result is None
        repo.update.assert_not_called()


# ===========================================================================
# Change password
# ===========================================================================


class TestAuthServiceChangePassword:
    """Tests for change_password."""

    @pytest.fixture
    def repo(self):
        return _make_mock_repo()

    @pytest.fixture
    def service(self, repo):
        return AuthService(repository=repo)

    @pytest.mark.asyncio
    async def test_change_password_success(self, service, repo):
        """change_password updates the password hash."""
        user = _make_user(user_id="user-pw")
        old_hash = user.password_hash
        repo.find_by_id.return_value = user

        result = await service.change_password("user-pw", "newSecurePassword1")

        assert result is True
        assert user.password_hash != old_hash
        # New password should verify
        ph.verify(user.password_hash, "newSecurePassword1")
        repo.update.assert_called_once_with(user)

    @pytest.mark.asyncio
    async def test_change_password_user_not_found(self, service, repo):
        """change_password returns False for nonexistent user."""
        repo.find_by_id.return_value = None

        result = await service.change_password("nonexistent-id", "newPassword1")

        assert result is False
        repo.update.assert_not_called()


# ===========================================================================
# Get user / Get all users
# ===========================================================================


class TestAuthServiceGetUsers:
    """Tests for get_user and get_all_users."""

    @pytest.fixture
    def repo(self):
        return _make_mock_repo()

    @pytest.fixture
    def service(self, repo):
        return AuthService(repository=repo)

    @pytest.mark.asyncio
    async def test_get_user_found(self, service, repo):
        """get_user returns user when found."""
        user = _make_user(user_id="found-user")
        repo.find_by_id.return_value = user

        result = await service.get_user("found-user")

        assert result is user
        repo.find_by_id.assert_called_once_with("found-user")

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, service, repo):
        """get_user returns None when not found."""
        repo.find_by_id.return_value = None

        result = await service.get_user("missing-user")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_users(self, service, repo):
        """get_all_users returns list from repository."""
        users = [_make_user(username="usr1"), _make_user(username="usr2")]
        repo.find_all.return_value = users

        result = await service.get_all_users()

        assert result == users
        assert len(result) == 2
        repo.find_all.assert_called_once()


# ===========================================================================
# Initial admin creation
# ===========================================================================


class TestAuthServiceInitialAdmin:
    """Tests for init() and _create_initial_admin."""

    @pytest.fixture
    def repo(self):
        return _make_mock_repo()

    @pytest.fixture
    def service(self, repo):
        return AuthService(repository=repo)

    @pytest.mark.asyncio
    async def test_init_creates_admin_from_env(self, service, repo):
        """init() creates admin user when env vars are set and user doesn't exist."""
        repo.find_by_username.return_value = None

        with patch.dict(
            "os.environ",
            {
                "ADMIN_INITIAL_USERNAME": "superadmin",
                "ADMIN_INITIAL_PASSWORD": "adminPass123",
            },
        ):
            await service.init()

        repo.init_db.assert_called_once()
        repo.find_by_username.assert_called_once_with("superadmin")
        repo.save.assert_called_once()

        saved_user = repo.save.call_args[0][0]
        assert isinstance(saved_user, WebUser)
        assert saved_user.username == "superadmin"
        assert saved_user.display_name == "Administrator"
        assert saved_user.role == "admin"
        # Password hash should verify against the original password
        ph.verify(saved_user.password_hash, "adminPass123")

    @pytest.mark.asyncio
    async def test_init_skips_admin_if_already_exists(self, service, repo):
        """init() does not create admin if username already exists."""
        existing_admin = _make_user(username="superadmin")
        repo.find_by_username.return_value = existing_admin

        with patch.dict(
            "os.environ",
            {
                "ADMIN_INITIAL_USERNAME": "superadmin",
                "ADMIN_INITIAL_PASSWORD": "adminPass123",
            },
        ):
            await service.init()

        repo.init_db.assert_called_once()
        repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_init_skips_admin_if_no_env_vars(self, service, repo):
        """init() skips admin creation when env vars are not set."""
        with patch.dict(
            "os.environ",
            {
                "ADMIN_INITIAL_USERNAME": "",
                "ADMIN_INITIAL_PASSWORD": "",
            },
        ):
            await service.init()

        repo.init_db.assert_called_once()
        repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_init_skips_admin_if_only_username_set(self, service, repo):
        """init() skips admin creation when only username is set."""
        env_patch = {"ADMIN_INITIAL_USERNAME": "admin"}
        # Remove password if it exists
        with patch.dict("os.environ", env_patch):
            with patch.dict("os.environ", {"ADMIN_INITIAL_PASSWORD": ""}):
                await service.init()

        repo.init_db.assert_called_once()
        repo.save.assert_not_called()


# ===========================================================================
# Password rehash on login
# ===========================================================================


class TestAuthServicePasswordRehash:
    """Tests for password rehash on login."""

    @pytest.fixture
    def repo(self):
        return _make_mock_repo()

    @pytest.fixture
    def service(self, repo):
        return AuthService(repository=repo)

    @pytest.mark.asyncio
    async def test_login_rehashes_password_if_needed(self, service, repo):
        """Login rehashes the password when argon2 parameters have changed."""
        user = _make_user()
        repo.find_by_username.return_value = user

        with patch("application.services.auth_service.ph") as mock_ph:
            mock_ph.verify.return_value = True  # password matches
            mock_ph.check_needs_rehash.return_value = True
            mock_ph.hash.return_value = "new-rehashed-hash"

            creds = Credentials(username="testuser", password=PASSWORD)
            result = await service.login(creds, ip_address="127.0.0.1")

        assert result is not None
        mock_ph.hash.assert_called()
        repo.update.assert_called_once_with(user)


# ===========================================================================
# Integration-like: full login -> verify -> refresh -> logout flow
# ===========================================================================


class TestAuthServiceFullFlow:
    """Integration-like test for the full auth lifecycle."""

    @pytest.fixture
    def repo(self):
        return _make_mock_repo()

    @pytest.fixture
    def service(self, repo):
        return AuthService(repository=repo)

    @pytest.mark.asyncio
    async def test_full_login_verify_refresh_logout(self, service, repo):
        """End-to-end: login -> verify token -> refresh -> logout."""
        user = _make_user(user_id="flow-user-123")
        repo.find_by_username.return_value = user

        # --- Step 1: Login ---
        creds = Credentials(username="testuser", password=PASSWORD)
        pair = await service.login(creds, ip_address="127.0.0.1")
        assert pair is not None

        # --- Step 2: Verify access token ---
        claims = service.verify_access_token(pair.access_token)
        assert claims is not None
        assert claims.sub == "flow-user-123"

        # --- Step 3: Refresh ---
        refresh_hash = hashlib.sha256(pair.refresh_token.encode()).hexdigest()
        repo.find_by_token_hash.return_value = {
            "id": "token-flow-1",
            "user_id": "flow-user-123",
            "token_hash": refresh_hash,
            "expires_at": datetime.utcnow() + timedelta(days=7),
            "created_at": datetime.utcnow(),
            "revoked_at": None,
            "user_agent": None,
        }
        repo.find_by_id.return_value = user

        new_pair = await service.refresh(pair.refresh_token)
        assert new_pair is not None
        # Refresh tokens are always unique (secrets.token_urlsafe)
        assert new_pair.refresh_token != pair.refresh_token
        # New access token should be a valid JWT
        assert new_pair.access_token

        # --- Step 4: Verify new access token ---
        new_claims = service.verify_access_token(new_pair.access_token)
        assert new_claims is not None
        assert new_claims.sub == "flow-user-123"

        # --- Step 5: Logout ---
        new_refresh_hash = hashlib.sha256(new_pair.refresh_token.encode()).hexdigest()
        repo.find_by_token_hash.return_value = {
            "id": "token-flow-2",
            "user_id": "flow-user-123",
            "token_hash": new_refresh_hash,
            "expires_at": datetime.utcnow() + timedelta(days=7),
            "created_at": datetime.utcnow(),
            "revoked_at": None,
            "user_agent": None,
        }

        logged_out = await service.logout(new_pair.refresh_token)
        assert logged_out is True
