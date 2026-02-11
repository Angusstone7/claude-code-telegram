"""Unit tests for the POST /settings/provider/validate endpoint.

Tests cover all provider types (anthropic, zai, local, unknown),
success and failure paths, timeout/connection errors, and model parsing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from presentation.api.routes.settings import validate_provider
from presentation.api.schemas.settings import (
    ProviderValidateRequest,
    ProviderValidateResponse,
)

USER = {"user_id": 1}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(status_code: int, json_data=None) -> httpx.Response:
    """Build a fake httpx.Response with the given status and JSON body."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = Exception("No JSON body")
    return resp


# ===========================================================================
# 1. Anthropic provider -- valid key
# ===========================================================================


class TestAnthropicProviderValid:
    """Anthropic provider returns valid=True with model list on 200."""

    @pytest.mark.asyncio
    async def test_valid_key_returns_models(self):
        """Valid API key returns valid=True and parsed model IDs."""
        models_data = {
            "data": [
                {"id": "claude-sonnet-4-5-20250929", "type": "model"},
                {"id": "claude-haiku-4-5-20251001", "type": "model"},
            ]
        }
        mock_resp = _make_response(200, json_data=models_data)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(provider="anthropic", api_key="sk-ant-valid-key")
            result = await validate_provider(request, user=USER)

        assert isinstance(result, ProviderValidateResponse)
        assert result.valid is True
        assert result.message == "API key is valid"
        assert "claude-sonnet-4-5-20250929" in result.models
        assert "claude-haiku-4-5-20251001" in result.models
        assert len(result.models) == 2

        # Verify correct URL and headers were used
        mock_client.get.assert_called_once_with(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": "sk-ant-valid-key",
                "anthropic-version": "2023-06-01",
            },
        )

    @pytest.mark.asyncio
    async def test_valid_key_with_list_response_format(self):
        """Handle model response as a plain list (non-dict format)."""
        models_data = [
            {"id": "model-a"},
            {"id": "model-b"},
        ]
        mock_resp = _make_response(200, json_data=models_data)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(provider="anthropic", api_key="sk-ant-key")
            result = await validate_provider(request, user=USER)

        assert result.valid is True
        assert result.models == ["model-a", "model-b"]

    @pytest.mark.asyncio
    async def test_valid_key_with_malformed_json(self):
        """When JSON parsing fails, return valid=True with empty models."""
        mock_resp = _make_response(200)
        mock_resp.json.side_effect = ValueError("bad json")

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(provider="anthropic", api_key="sk-ant-key")
            result = await validate_provider(request, user=USER)

        assert result.valid is True
        assert result.models == []
        assert result.message == "API key is valid"


# ===========================================================================
# 2. Anthropic provider -- invalid key (401)
# ===========================================================================


class TestAnthropicProviderInvalid:
    """Anthropic provider returns valid=False on non-success status."""

    @pytest.mark.asyncio
    async def test_invalid_key_returns_status_401(self):
        """Invalid API key (401) returns valid=False with status message."""
        mock_resp = _make_response(401)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(provider="anthropic", api_key="sk-ant-invalid")
            result = await validate_provider(request, user=USER)

        assert isinstance(result, ProviderValidateResponse)
        assert result.valid is False
        assert result.models == []
        assert "401" in result.message

    @pytest.mark.asyncio
    async def test_invalid_key_returns_status_403(self):
        """Forbidden (403) returns valid=False."""
        mock_resp = _make_response(403)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(provider="anthropic", api_key="sk-ant-forbidden")
            result = await validate_provider(request, user=USER)

        assert result.valid is False
        assert "403" in result.message


# ===========================================================================
# 3. Local provider -- fallback to /health when /v1/models returns 404
# ===========================================================================


class TestLocalProviderFallbackHealth:
    """Local provider falls back to /health when /v1/models returns 404."""

    @pytest.mark.asyncio
    async def test_models_404_health_ok(self):
        """When /v1/models returns 404 but /health returns 200, valid=True with health message."""
        models_resp = _make_response(404)
        health_resp = _make_response(200)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=[models_resp, health_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(
                provider="local",
                api_key="unused",
                base_url="http://localhost:8080",
            )
            result = await validate_provider(request, user=USER)

        assert result.valid is True
        assert result.models == []
        assert "health OK" in result.message
        assert "/v1/models not available" in result.message

        # Verify two GET requests were made
        assert mock_client.get.call_count == 2
        calls = mock_client.get.call_args_list
        assert calls[0][0][0] == "http://localhost:8080/v1/models"
        assert calls[1][0][0] == "http://localhost:8080/health"

    @pytest.mark.asyncio
    async def test_models_404_health_also_fails(self):
        """When both /v1/models (404) and /health (500) fail, valid=False."""
        models_resp = _make_response(404)
        health_resp = _make_response(500)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=[models_resp, health_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(
                provider="local",
                api_key="unused",
                base_url="http://localhost:8080",
            )
            result = await validate_provider(request, user=USER)

        # /health returned 500 (is_success=False), so we fall through
        # to the general resp.is_success check on the health resp
        # Actually, after health fails, resp is still the health_resp (500),
        # and the code falls through to the general is_success check
        assert result.valid is False
        assert "500" in result.message

    @pytest.mark.asyncio
    async def test_models_200_returns_models(self):
        """When /v1/models returns 200, parse models normally."""
        models_data = {"data": [{"id": "local-model-1"}, {"id": "local-model-2"}]}
        models_resp = _make_response(200, json_data=models_data)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=models_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(
                provider="local",
                api_key="unused",
                base_url="http://localhost:8080/",
            )
            result = await validate_provider(request, user=USER)

        assert result.valid is True
        assert result.models == ["local-model-1", "local-model-2"]
        assert result.message == "API key is valid"

        # base_url trailing slash should be stripped
        mock_client.get.assert_called_once_with("http://localhost:8080/v1/models")


# ===========================================================================
# 4. Timeout handling
# ===========================================================================


class TestTimeoutHandling:
    """Timeout exceptions return connection timed out message."""

    @pytest.mark.asyncio
    async def test_timeout_returns_timed_out_message(self):
        """httpx.TimeoutException produces valid=False with timeout message."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("read timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(provider="anthropic", api_key="sk-ant-key")
            result = await validate_provider(request, user=USER)

        assert isinstance(result, ProviderValidateResponse)
        assert result.valid is False
        assert result.models == []
        assert result.message == "Connection timed out"

    @pytest.mark.asyncio
    async def test_connect_error_returns_connection_error_message(self):
        """httpx.ConnectError produces valid=False with connection error message."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(provider="anthropic", api_key="sk-ant-key")
            result = await validate_provider(request, user=USER)

        assert result.valid is False
        assert result.models == []
        assert result.message == "Connection error: unable to reach server"

    @pytest.mark.asyncio
    async def test_generic_exception_returns_validation_failed(self):
        """Unexpected exception produces valid=False with details."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=RuntimeError("something broke"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(provider="anthropic", api_key="sk-ant-key")
            result = await validate_provider(request, user=USER)

        assert result.valid is False
        assert result.models == []
        assert "Validation failed" in result.message
        assert "something broke" in result.message


# ===========================================================================
# 5. ZAI provider with custom base_url
# ===========================================================================


class TestZaiProvider:
    """ZAI provider uses correct base URL and Authorization header."""

    @pytest.mark.asyncio
    async def test_zai_with_custom_base_url(self):
        """ZAI with custom base_url uses it instead of the default."""
        models_data = {"data": [{"id": "zai-model-1"}]}
        mock_resp = _make_response(200, json_data=models_data)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(
                provider="zai",
                api_key="zai-test-key-123",
                base_url="https://custom-zai.example.com/api",
            )
            result = await validate_provider(request, user=USER)

        assert result.valid is True
        assert result.models == ["zai-model-1"]

        mock_client.get.assert_called_once_with(
            "https://custom-zai.example.com/api/v1/models",
            headers={"Authorization": "Bearer zai-test-key-123"},
        )

    @pytest.mark.asyncio
    async def test_zai_with_default_base_url(self):
        """ZAI without custom base_url uses the default ZAI_BASE_URL."""
        models_data = {"data": [{"id": "claude-sonnet-4-5-20250929"}]}
        mock_resp = _make_response(200, json_data=models_data)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(
                provider="zai",
                api_key="zai-key",
            )
            result = await validate_provider(request, user=USER)

        assert result.valid is True

        # Should use the default ZAI base URL
        call_args = mock_client.get.call_args
        assert "open.bigmodel.cn" in call_args[0][0]
        assert call_args[0][0].endswith("/v1/models")

    @pytest.mark.asyncio
    async def test_zai_trailing_slash_stripped(self):
        """ZAI base_url trailing slash is stripped before appending path."""
        mock_resp = _make_response(200, json_data={"data": []})

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("presentation.api.routes.settings.httpx.AsyncClient", return_value=mock_client):
            request = ProviderValidateRequest(
                provider="zai",
                api_key="zai-key",
                base_url="https://example.com/api/",
            )
            result = await validate_provider(request, user=USER)

        assert result.valid is True
        called_url = mock_client.get.call_args[0][0]
        assert called_url == "https://example.com/api/v1/models"
        assert "//" not in called_url.split("://")[1]


# ===========================================================================
# 6. Local provider without base_url
# ===========================================================================


class TestLocalProviderNoBaseUrl:
    """Local provider without base_url returns error immediately."""

    @pytest.mark.asyncio
    async def test_local_without_base_url_returns_error(self):
        """Local provider requires base_url; missing it returns valid=False."""
        request = ProviderValidateRequest(
            provider="local",
            api_key="unused-key",
        )
        result = await validate_provider(request, user=USER)

        assert isinstance(result, ProviderValidateResponse)
        assert result.valid is False
        assert result.models == []
        assert "base_url is required" in result.message


# ===========================================================================
# 7. Unknown provider
# ===========================================================================


class TestUnknownProvider:
    """Unknown provider type returns error immediately."""

    @pytest.mark.asyncio
    async def test_unknown_provider_returns_error(self):
        """Unknown provider returns valid=False with provider name in message."""
        request = ProviderValidateRequest(
            provider="openai",
            api_key="sk-openai-key",
        )
        result = await validate_provider(request, user=USER)

        assert isinstance(result, ProviderValidateResponse)
        assert result.valid is False
        assert result.models == []
        assert "Unknown provider" in result.message
        assert "openai" in result.message

    @pytest.mark.asyncio
    async def test_empty_provider_returns_error(self):
        """Empty string provider returns valid=False."""
        request = ProviderValidateRequest(
            provider="",
            api_key="some-key",
        )
        result = await validate_provider(request, user=USER)

        assert result.valid is False
        assert "Unknown provider" in result.message
