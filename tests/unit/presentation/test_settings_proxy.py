"""
Unit tests for proxy settings save/apply logic.

Tests the proxy-related behaviour in presentation/api/routes/settings.py:
- Environment variable manipulation when proxy is enabled/disabled
- Proxy URL construction with and without authentication
- NO_PROXY preservation
- Password masking in _get_proxy_config responses
- RuntimeConfig storage of proxy settings
"""

import os
import pytest
from unittest.mock import AsyncMock, patch


# ---------------------------------------------------------------------------
# Helper: simulates the proxy-update logic extracted from update_settings()
# ---------------------------------------------------------------------------

async def _apply_proxy_update(px: dict, config: AsyncMock) -> None:
    """Reproduce the proxy block from update_settings() for isolated testing.

    ``px`` is the dict that would come from ``update_data["proxy"]`` after
    ``request.model_dump(exclude_unset=True)``.
    ``config`` is a mock RuntimeConfig with async ``get`` / ``set`` methods.
    """
    if not px:
        return

    for pk, pv in px.items():
        await config.set(f"settings.proxy.{pk}", pv)

    proxy_enabled = px.get("enabled")
    if proxy_enabled is None:
        proxy_enabled = await config.get("settings.proxy.enabled")

    if proxy_enabled:
        host = px.get("host") or await config.get("settings.proxy.host") or ""
        port = px.get("port") or await config.get("settings.proxy.port") or 0
        ptype = px.get("type") or await config.get("settings.proxy.type") or "http"
        username = px.get("username") or await config.get("settings.proxy.username") or ""
        password = px.get("password") or await config.get("settings.proxy.password") or ""
        no_proxy = (
            px.get("no_proxy")
            or await config.get("settings.proxy.no_proxy")
            or "localhost,127.0.0.1,192.168.0.0/16"
        )

        if host and port:
            if username and password:
                proxy_url = f"{ptype}://{username}:{password}@{host}:{port}"
            else:
                proxy_url = f"{ptype}://{host}:{port}"
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
            os.environ["http_proxy"] = proxy_url
            os.environ["https_proxy"] = proxy_url
            os.environ["NO_PROXY"] = no_proxy
            os.environ["no_proxy"] = no_proxy

    elif proxy_enabled is False:
        for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            os.environ.pop(var, None)


# ---------------------------------------------------------------------------
# Fixture: mock RuntimeConfig
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config():
    """Create a mock RuntimeConfig with async get/set backed by a dict."""
    store: dict[str, object] = {}
    config = AsyncMock()

    async def _get(key: str):
        return store.get(key)

    async def _set(key: str, value: object):
        store[key] = value

    config.get = AsyncMock(side_effect=_get)
    config.set = AsyncMock(side_effect=_set)
    config._store = store  # expose for assertions
    return config


# ---------------------------------------------------------------------------
# Fixture: clean proxy env vars before/after each test
# ---------------------------------------------------------------------------

PROXY_ENV_VARS = (
    "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
    "NO_PROXY", "no_proxy",
)


@pytest.fixture(autouse=True)
def _clean_proxy_env(monkeypatch):
    """Remove all proxy env vars before each test and restore after."""
    for var in PROXY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    yield
    # monkeypatch automatically restores the original env on teardown


# ===================================================================
# 1. Enable proxy sets HTTP_PROXY / HTTPS_PROXY correctly
# ===================================================================

class TestEnableProxySetsEnvVars:
    """Enabling the proxy must populate four env vars with the proxy URL."""

    @pytest.mark.asyncio
    async def test_basic_http_proxy(self, mock_config):
        px = {
            "enabled": True,
            "host": "proxy.example.com",
            "port": 3128,
        }
        await _apply_proxy_update(px, mock_config)

        expected = "http://proxy.example.com:3128"
        assert os.environ["HTTP_PROXY"] == expected
        assert os.environ["HTTPS_PROXY"] == expected
        assert os.environ["http_proxy"] == expected
        assert os.environ["https_proxy"] == expected

    @pytest.mark.asyncio
    async def test_socks5_proxy(self, mock_config):
        px = {
            "enabled": True,
            "type": "socks5",
            "host": "socks.internal",
            "port": 1080,
        }
        await _apply_proxy_update(px, mock_config)

        expected = "socks5://socks.internal:1080"
        assert os.environ["HTTP_PROXY"] == expected
        assert os.environ["HTTPS_PROXY"] == expected

    @pytest.mark.asyncio
    async def test_proxy_type_defaults_to_http(self, mock_config):
        """When type is not specified, 'http' is used."""
        px = {"enabled": True, "host": "px.lan", "port": 8080}
        await _apply_proxy_update(px, mock_config)
        assert os.environ["HTTP_PROXY"].startswith("http://")

    @pytest.mark.asyncio
    async def test_enable_without_host_does_not_set_env(self, mock_config):
        """If host is missing the env vars should NOT be set."""
        px = {"enabled": True, "port": 3128}
        await _apply_proxy_update(px, mock_config)
        assert "HTTP_PROXY" not in os.environ
        assert "HTTPS_PROXY" not in os.environ

    @pytest.mark.asyncio
    async def test_enable_without_port_does_not_set_env(self, mock_config):
        """If port is missing (0 / falsy) the env vars should NOT be set."""
        px = {"enabled": True, "host": "proxy.example.com"}
        await _apply_proxy_update(px, mock_config)
        assert "HTTP_PROXY" not in os.environ


# ===================================================================
# 2. Enable proxy with auth sets username:password in URL
# ===================================================================

class TestEnableProxyWithAuth:
    """Proxy URL must contain credentials when username + password given."""

    @pytest.mark.asyncio
    async def test_proxy_with_credentials(self, mock_config):
        px = {
            "enabled": True,
            "host": "proxy.corp.net",
            "port": 3128,
            "username": "user1",
            "password": "s3cret",
        }
        await _apply_proxy_update(px, mock_config)

        expected = "http://user1:s3cret@proxy.corp.net:3128"
        assert os.environ["HTTP_PROXY"] == expected
        assert os.environ["HTTPS_PROXY"] == expected
        assert os.environ["http_proxy"] == expected
        assert os.environ["https_proxy"] == expected

    @pytest.mark.asyncio
    async def test_proxy_with_custom_type_and_credentials(self, mock_config):
        px = {
            "enabled": True,
            "type": "socks5",
            "host": "socks.corp.net",
            "port": 1080,
            "username": "admin",
            "password": "pa$$word",
        }
        await _apply_proxy_update(px, mock_config)

        expected = "socks5://admin:pa$$word@socks.corp.net:1080"
        assert os.environ["HTTP_PROXY"] == expected

    @pytest.mark.asyncio
    async def test_proxy_username_only_no_password(self, mock_config):
        """Username without password should produce a URL without credentials."""
        px = {
            "enabled": True,
            "host": "proxy.example.com",
            "port": 3128,
            "username": "user1",
        }
        await _apply_proxy_update(px, mock_config)

        # Both username AND password are required; if either is missing
        # the code builds a plain URL without auth.
        expected = "http://proxy.example.com:3128"
        assert os.environ["HTTP_PROXY"] == expected

    @pytest.mark.asyncio
    async def test_proxy_password_only_no_username(self, mock_config):
        """Password without username should produce a URL without credentials."""
        px = {
            "enabled": True,
            "host": "proxy.example.com",
            "port": 3128,
            "password": "secret",
        }
        await _apply_proxy_update(px, mock_config)
        expected = "http://proxy.example.com:3128"
        assert os.environ["HTTP_PROXY"] == expected


# ===================================================================
# 3. Disable proxy unsets HTTP_PROXY / HTTPS_PROXY env vars
# ===================================================================

class TestDisableProxyUnsetsEnvVars:
    """Setting enabled=False must remove all four proxy env vars."""

    @pytest.mark.asyncio
    async def test_disable_removes_vars(self, mock_config):
        # Pre-populate env as if proxy was previously enabled
        os.environ["HTTP_PROXY"] = "http://old:1234"
        os.environ["HTTPS_PROXY"] = "http://old:1234"
        os.environ["http_proxy"] = "http://old:1234"
        os.environ["https_proxy"] = "http://old:1234"

        px = {"enabled": False}
        await _apply_proxy_update(px, mock_config)

        assert "HTTP_PROXY" not in os.environ
        assert "HTTPS_PROXY" not in os.environ
        assert "http_proxy" not in os.environ
        assert "https_proxy" not in os.environ

    @pytest.mark.asyncio
    async def test_disable_when_vars_not_set(self, mock_config):
        """Disabling when vars don't exist should not raise."""
        px = {"enabled": False}
        await _apply_proxy_update(px, mock_config)
        assert "HTTP_PROXY" not in os.environ

    @pytest.mark.asyncio
    async def test_disable_preserves_no_proxy(self, mock_config):
        """NO_PROXY / no_proxy should NOT be removed when proxy is disabled."""
        os.environ["NO_PROXY"] = "localhost,10.0.0.0/8"
        os.environ["no_proxy"] = "localhost,10.0.0.0/8"

        px = {"enabled": False}
        await _apply_proxy_update(px, mock_config)

        # The disable path only removes HTTP(S)_PROXY; NO_PROXY is kept.
        assert os.environ.get("NO_PROXY") == "localhost,10.0.0.0/8"
        assert os.environ.get("no_proxy") == "localhost,10.0.0.0/8"


# ===================================================================
# 4. NO_PROXY is preserved / set when proxy is enabled
# ===================================================================

class TestNoProxyHandling:
    """NO_PROXY env var handling."""

    @pytest.mark.asyncio
    async def test_custom_no_proxy(self, mock_config):
        px = {
            "enabled": True,
            "host": "proxy.lan",
            "port": 3128,
            "no_proxy": "localhost,10.0.0.0/8,172.16.0.0/12",
        }
        await _apply_proxy_update(px, mock_config)

        assert os.environ["NO_PROXY"] == "localhost,10.0.0.0/8,172.16.0.0/12"
        assert os.environ["no_proxy"] == "localhost,10.0.0.0/8,172.16.0.0/12"

    @pytest.mark.asyncio
    async def test_default_no_proxy(self, mock_config):
        """When no_proxy is not provided, the default value is used."""
        px = {
            "enabled": True,
            "host": "proxy.lan",
            "port": 3128,
        }
        await _apply_proxy_update(px, mock_config)

        assert os.environ["NO_PROXY"] == "localhost,127.0.0.1,192.168.0.0/16"
        assert os.environ["no_proxy"] == "localhost,127.0.0.1,192.168.0.0/16"

    @pytest.mark.asyncio
    async def test_no_proxy_from_runtime_config(self, mock_config):
        """no_proxy should fall back to RuntimeConfig if not in the request."""
        mock_config._store["settings.proxy.no_proxy"] = "internal.corp"

        px = {
            "enabled": True,
            "host": "proxy.lan",
            "port": 3128,
        }
        await _apply_proxy_update(px, mock_config)

        assert os.environ["NO_PROXY"] == "internal.corp"


# ===================================================================
# 5. Password is NOT returned in GET response (only password_set bool)
# ===================================================================

class TestGetProxyConfigPasswordMasking:
    """_get_proxy_config must never expose the actual password."""

    @pytest.mark.asyncio
    async def test_password_set_true_when_stored(self):
        from presentation.api.routes.settings import _get_proxy_config

        config = AsyncMock()
        store = {
            "settings.proxy.enabled": True,
            "settings.proxy.type": "http",
            "settings.proxy.host": "proxy.lan",
            "settings.proxy.port": "3128",
            "settings.proxy.username": "user1",
            "settings.proxy.password": "supersecret",
            "settings.proxy.no_proxy": "localhost",
        }
        config.get = AsyncMock(side_effect=lambda k: store.get(k))

        result = await _get_proxy_config(config)

        assert result["password_set"] is True
        assert "password" not in result, "Actual password must not be in the response"
        assert result["username"] == "user1"

    @pytest.mark.asyncio
    async def test_password_set_false_when_not_stored(self):
        from presentation.api.routes.settings import _get_proxy_config

        config = AsyncMock()
        store = {
            "settings.proxy.enabled": True,
            "settings.proxy.type": "http",
            "settings.proxy.host": "proxy.lan",
            "settings.proxy.port": "3128",
            "settings.proxy.username": "",
            "settings.proxy.password": "",
            "settings.proxy.no_proxy": None,
        }
        config.get = AsyncMock(side_effect=lambda k: store.get(k))

        result = await _get_proxy_config(config)

        assert result["password_set"] is False
        assert "password" not in result

    @pytest.mark.asyncio
    async def test_password_set_false_when_none(self):
        from presentation.api.routes.settings import _get_proxy_config

        config = AsyncMock()
        config.get = AsyncMock(return_value=None)

        result = await _get_proxy_config(config)

        assert result["password_set"] is False
        assert "password" not in result

    @pytest.mark.asyncio
    async def test_response_structure(self):
        """_get_proxy_config must return exactly the expected keys."""
        from presentation.api.routes.settings import _get_proxy_config

        config = AsyncMock()
        config.get = AsyncMock(return_value=None)

        result = await _get_proxy_config(config)

        expected_keys = {"enabled", "type", "host", "port", "username", "password_set", "no_proxy"}
        assert set(result.keys()) == expected_keys


# ===================================================================
# 6. Proxy config is stored in RuntimeConfig
# ===================================================================

class TestProxyConfigStoredInRuntimeConfig:
    """config.set() must be called for every field in the proxy dict."""

    @pytest.mark.asyncio
    async def test_all_fields_stored(self, mock_config):
        px = {
            "enabled": True,
            "type": "http",
            "host": "proxy.lan",
            "port": 3128,
            "username": "admin",
            "password": "secret",
            "no_proxy": "localhost",
        }
        await _apply_proxy_update(px, mock_config)

        assert mock_config._store["settings.proxy.enabled"] is True
        assert mock_config._store["settings.proxy.type"] == "http"
        assert mock_config._store["settings.proxy.host"] == "proxy.lan"
        assert mock_config._store["settings.proxy.port"] == 3128
        assert mock_config._store["settings.proxy.username"] == "admin"
        assert mock_config._store["settings.proxy.password"] == "secret"
        assert mock_config._store["settings.proxy.no_proxy"] == "localhost"

    @pytest.mark.asyncio
    async def test_partial_update_stores_only_provided(self, mock_config):
        """Only provided fields should be persisted."""
        px = {"host": "new-proxy.lan", "port": 9999}
        await _apply_proxy_update(px, mock_config)

        assert mock_config._store["settings.proxy.host"] == "new-proxy.lan"
        assert mock_config._store["settings.proxy.port"] == 9999
        # enabled, type, etc. should not be stored since they weren't provided
        assert "settings.proxy.enabled" not in mock_config._store
        assert "settings.proxy.type" not in mock_config._store

    @pytest.mark.asyncio
    async def test_disable_still_stores_enabled_false(self, mock_config):
        """enabled=False must be persisted so future reads know proxy is off."""
        px = {"enabled": False}
        await _apply_proxy_update(px, mock_config)

        assert mock_config._store["settings.proxy.enabled"] is False


# ===================================================================
# 7. Edge cases / integration-like scenarios
# ===================================================================

class TestProxyEdgeCases:
    """Edge cases and more complex scenarios."""

    @pytest.mark.asyncio
    async def test_update_host_inherits_enabled_from_config(self, mock_config):
        """When only host/port are changed, enabled is read from RuntimeConfig."""
        mock_config._store["settings.proxy.enabled"] = True

        px = {"host": "new-proxy.lan", "port": 8080}
        await _apply_proxy_update(px, mock_config)

        expected = "http://new-proxy.lan:8080"
        assert os.environ["HTTP_PROXY"] == expected

    @pytest.mark.asyncio
    async def test_update_host_uses_stored_credentials(self, mock_config):
        """When only host changes, username/password come from RuntimeConfig."""
        mock_config._store["settings.proxy.enabled"] = True
        mock_config._store["settings.proxy.username"] = "stored_user"
        mock_config._store["settings.proxy.password"] = "stored_pass"

        px = {"host": "new-proxy.lan", "port": 8080}
        await _apply_proxy_update(px, mock_config)

        expected = "http://stored_user:stored_pass@new-proxy.lan:8080"
        assert os.environ["HTTP_PROXY"] == expected

    @pytest.mark.asyncio
    async def test_empty_px_dict_does_nothing(self, mock_config):
        """An empty proxy dict should not modify env or config."""
        await _apply_proxy_update({}, mock_config)
        assert "HTTP_PROXY" not in os.environ
        mock_config.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_px_does_nothing(self, mock_config):
        """None proxy value should not modify env or config."""
        await _apply_proxy_update(None, mock_config)
        assert "HTTP_PROXY" not in os.environ
        mock_config.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_proxy_config_enabled_from_env_fallback(self):
        """_get_proxy_config should detect enabled from HTTP_PROXY env var."""
        from presentation.api.routes.settings import _get_proxy_config

        os.environ["HTTP_PROXY"] = "http://auto-detected:3128"

        config = AsyncMock()
        config.get = AsyncMock(return_value=None)

        result = await _get_proxy_config(config)
        assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_get_proxy_config_disabled_by_default(self):
        """_get_proxy_config should return enabled=False when nothing is set."""
        from presentation.api.routes.settings import _get_proxy_config

        config = AsyncMock()
        config.get = AsyncMock(return_value=None)

        result = await _get_proxy_config(config)
        assert result["enabled"] is False

    @pytest.mark.asyncio
    async def test_get_proxy_config_enabled_string_true(self):
        """_get_proxy_config handles string 'true' from RuntimeConfig."""
        from presentation.api.routes.settings import _get_proxy_config

        config = AsyncMock()
        store = {"settings.proxy.enabled": "true"}
        config.get = AsyncMock(side_effect=lambda k: store.get(k))

        result = await _get_proxy_config(config)
        assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_get_proxy_config_port_as_string(self):
        """_get_proxy_config should cast port from string to int."""
        from presentation.api.routes.settings import _get_proxy_config

        config = AsyncMock()
        store = {
            "settings.proxy.enabled": True,
            "settings.proxy.type": "http",
            "settings.proxy.host": "proxy.lan",
            "settings.proxy.port": "8080",
            "settings.proxy.username": None,
            "settings.proxy.password": None,
            "settings.proxy.no_proxy": None,
        }
        config.get = AsyncMock(side_effect=lambda k: store.get(k))

        result = await _get_proxy_config(config)
        assert result["port"] == 8080
        assert isinstance(result["port"], int)
