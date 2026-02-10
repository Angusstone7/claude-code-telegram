"""Unit tests for RuntimeConfigService — backend mode methods."""

import pytest
from unittest.mock import AsyncMock

from application.services.runtime_config_service import RuntimeConfigService
from domain.value_objects.backend_mode import BackendMode


@pytest.fixture
def mock_repo():
    """Create mock config repository."""
    repo = AsyncMock()
    repo.get_all = AsyncMock(return_value={})
    repo.set = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def config_service(mock_repo):
    """Create RuntimeConfigService with mock repo."""
    return RuntimeConfigService(repository=mock_repo)


class TestBackendMode:
    """Tests for BackendMode enum."""

    def test_sdk_value(self):
        assert BackendMode.SDK.value == "sdk"

    def test_cli_value(self):
        assert BackendMode.CLI.value == "cli"

    def test_from_string_sdk(self):
        assert BackendMode("sdk") == BackendMode.SDK

    def test_from_string_cli(self):
        assert BackendMode("cli") == BackendMode.CLI

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            BackendMode("invalid")

    def test_label_key_sdk(self):
        assert BackendMode.SDK.label_key == "settings.backend_sdk"

    def test_label_key_cli(self):
        assert BackendMode.CLI.label_key == "settings.backend_cli"

    def test_description_key_sdk(self):
        assert BackendMode.SDK.description_key == "settings.backend_sdk_desc"

    def test_description_key_cli(self):
        assert BackendMode.CLI.description_key == "settings.backend_cli_desc"

    def test_is_str_enum(self):
        """BackendMode is a str enum, so it can be compared to strings."""
        assert BackendMode.SDK == "sdk"
        assert BackendMode.CLI == "cli"


class TestRuntimeConfigGetUserBackend:
    """Tests for get_user_backend method."""

    @pytest.mark.asyncio
    async def test_default_is_sdk(self, config_service):
        """When no backend set, default is SDK."""
        result = await config_service.get_user_backend(12345)
        assert result == BackendMode.SDK

    @pytest.mark.asyncio
    async def test_returns_sdk_when_stored(self, config_service, mock_repo):
        """Returns SDK when stored in DB."""
        mock_repo.get_all = AsyncMock(return_value={"user.12345.backend": "sdk"})
        result = await config_service.get_user_backend(12345)
        assert result == BackendMode.SDK

    @pytest.mark.asyncio
    async def test_returns_cli_when_stored(self, config_service, mock_repo):
        """Returns CLI when stored in DB."""
        mock_repo.get_all = AsyncMock(return_value={"user.12345.backend": "cli"})
        result = await config_service.get_user_backend(12345)
        assert result == BackendMode.CLI

    @pytest.mark.asyncio
    async def test_invalid_value_returns_sdk(self, config_service, mock_repo):
        """Invalid stored value falls back to SDK."""
        mock_repo.get_all = AsyncMock(return_value={"user.12345.backend": "garbage"})
        result = await config_service.get_user_backend(12345)
        assert result == BackendMode.SDK

    @pytest.mark.asyncio
    async def test_different_users_independent(self, config_service, mock_repo):
        """Different users have independent backend settings."""
        mock_repo.get_all = AsyncMock(return_value={
            "user.111.backend": "cli",
            "user.222.backend": "sdk",
        })
        result_111 = await config_service.get_user_backend(111)
        assert result_111 == BackendMode.CLI

        result_222 = await config_service.get_user_backend(222)
        assert result_222 == BackendMode.SDK


class TestRuntimeConfigSetUserBackend:
    """Tests for set_user_backend method."""

    @pytest.mark.asyncio
    async def test_set_sdk(self, config_service, mock_repo):
        """Set backend to SDK."""
        await config_service.set_user_backend(12345, BackendMode.SDK)
        mock_repo.set.assert_called_with("user.12345.backend", "sdk")

    @pytest.mark.asyncio
    async def test_set_cli(self, config_service, mock_repo):
        """Set backend to CLI."""
        await config_service.set_user_backend(12345, BackendMode.CLI)
        mock_repo.set.assert_called_with("user.12345.backend", "cli")

    @pytest.mark.asyncio
    async def test_set_string_sdk_auto_converts(self, config_service, mock_repo):
        """String 'sdk' is auto-converted to BackendMode."""
        await config_service.set_user_backend(12345, "sdk")
        mock_repo.set.assert_called_with("user.12345.backend", "sdk")

    @pytest.mark.asyncio
    async def test_set_string_cli_auto_converts(self, config_service, mock_repo):
        """String 'cli' is auto-converted to BackendMode."""
        await config_service.set_user_backend(12345, "cli")
        mock_repo.set.assert_called_with("user.12345.backend", "cli")

    @pytest.mark.asyncio
    async def test_set_invalid_raises_value_error(self, config_service):
        """Invalid backend value raises ValueError."""
        with pytest.raises(ValueError):
            await config_service.set_user_backend(12345, "invalid")

    @pytest.mark.asyncio
    async def test_set_updates_cache(self, config_service, mock_repo):
        """Setting backend updates the cache."""
        # First ensure cache is loaded (empty)
        result_before = await config_service.get_user_backend(12345)
        assert result_before == BackendMode.SDK

        # Now set CLI — this should update the cache
        await config_service.set_user_backend(12345, BackendMode.CLI)

        # Read back — should come from updated cache, not from repo again
        result = await config_service.get_user_backend(12345)
        assert result == BackendMode.CLI
