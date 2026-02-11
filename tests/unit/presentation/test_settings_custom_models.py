"""Unit tests for custom model CRUD endpoints in settings API.

Tests add_custom_model (POST /settings/models/custom) and
delete_custom_model (DELETE /settings/models/custom).
"""

import json

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from presentation.api.routes.settings import add_custom_model, delete_custom_model
from presentation.api.schemas.settings import CustomModelRequest, CustomModelResponse


ANTHROPIC_BASE_MODELS = [
    "claude-opus-4-6",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
]

USER = {"user_id": 1}


@pytest.fixture
def mock_config():
    """Create a mock RuntimeConfigService with async get/set."""
    config = AsyncMock()
    config.get = AsyncMock(return_value=None)
    config.set = AsyncMock()
    return config


# ---------------------------------------------------------------------------
# POST /settings/models/custom — add_custom_model
# ---------------------------------------------------------------------------


class TestAddCustomModel:
    """Tests for the add_custom_model endpoint."""

    @pytest.mark.asyncio
    @patch("presentation.api.routes.settings.get_runtime_config")
    async def test_add_model_to_empty_list(self, mock_get_config, mock_config):
        """Adding a new model to an empty custom list succeeds."""
        mock_get_config.return_value = mock_config
        # config.get returns None => empty custom models list
        mock_config.get.return_value = None

        request = CustomModelRequest(provider="anthropic", model_id="my-custom-model")
        result = await add_custom_model(request=request, user=USER)

        assert isinstance(result, CustomModelResponse)
        assert result.provider == "anthropic"
        assert "my-custom-model" in result.custom_models
        assert "my-custom-model" in result.models
        # Base models should still be present
        for m in ANTHROPIC_BASE_MODELS:
            assert m in result.models

        # Verify config.set was called with the serialized list
        mock_config.set.assert_called_once_with(
            "settings.custom_models.anthropic",
            json.dumps(["my-custom-model"]),
        )

    @pytest.mark.asyncio
    @patch("presentation.api.routes.settings.get_runtime_config")
    async def test_add_duplicate_model_rejected(self, mock_get_config, mock_config):
        """Adding a model that already exists in custom list returns 400."""
        mock_get_config.return_value = mock_config
        mock_config.get.return_value = json.dumps(["my-custom-model"])

        request = CustomModelRequest(provider="anthropic", model_id="my-custom-model")

        with pytest.raises(HTTPException) as exc_info:
            await add_custom_model(request=request, user=USER)

        assert exc_info.value.status_code == 400
        assert "already exists in custom list" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("presentation.api.routes.settings.get_runtime_config")
    async def test_add_model_already_in_base_models_rejected(self, mock_get_config, mock_config):
        """Adding a model that exists in base models returns 400."""
        mock_get_config.return_value = mock_config
        mock_config.get.return_value = None

        request = CustomModelRequest(provider="anthropic", model_id="claude-opus-4-6")

        with pytest.raises(HTTPException) as exc_info:
            await add_custom_model(request=request, user=USER)

        assert exc_info.value.status_code == 400
        assert "already exists in base models" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("presentation.api.routes.settings.get_runtime_config")
    async def test_add_model_max_limit_rejected(self, mock_get_config, mock_config):
        """Adding a model when already at 20 custom models returns 400."""
        mock_get_config.return_value = mock_config
        existing = [f"custom-model-{i}" for i in range(20)]
        mock_config.get.return_value = json.dumps(existing)

        request = CustomModelRequest(provider="anthropic", model_id="one-too-many")

        with pytest.raises(HTTPException) as exc_info:
            await add_custom_model(request=request, user=USER)

        assert exc_info.value.status_code == 400
        assert "Maximum 20" in exc_info.value.detail


# ---------------------------------------------------------------------------
# DELETE /settings/models/custom — delete_custom_model
# ---------------------------------------------------------------------------


class TestDeleteCustomModel:
    """Tests for the delete_custom_model endpoint."""

    @pytest.mark.asyncio
    @patch("presentation.api.routes.settings.get_runtime_config")
    async def test_remove_model(self, mock_get_config, mock_config):
        """Removing an existing custom model succeeds."""
        mock_get_config.return_value = mock_config
        mock_config.get.side_effect = lambda key: {
            "settings.custom_models.anthropic": json.dumps(["model-a", "model-b"]),
            "settings.model": None,
        }.get(key)

        request = CustomModelRequest(provider="anthropic", model_id="model-a")
        result = await delete_custom_model(request=request, user=USER)

        assert isinstance(result, CustomModelResponse)
        assert result.provider == "anthropic"
        assert "model-a" not in result.custom_models
        assert "model-b" in result.custom_models
        # Base models should remain
        for m in ANTHROPIC_BASE_MODELS:
            assert m in result.models

        # Verify config.set was called with the updated list (model-a removed)
        mock_config.set.assert_any_call(
            "settings.custom_models.anthropic",
            json.dumps(["model-b"]),
        )

    @pytest.mark.asyncio
    @patch("presentation.api.routes.settings.get_runtime_config")
    async def test_remove_nonexistent_model_rejected(self, mock_get_config, mock_config):
        """Removing a model not in the custom list returns 404."""
        mock_get_config.return_value = mock_config
        mock_config.get.return_value = json.dumps(["model-a"])

        request = CustomModelRequest(provider="anthropic", model_id="does-not-exist")

        with pytest.raises(HTTPException) as exc_info:
            await delete_custom_model(request=request, user=USER)

        assert exc_info.value.status_code == 404
        assert "not found in custom list" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("presentation.api.routes.settings.get_runtime_config")
    async def test_remove_currently_selected_model_resets(self, mock_get_config, mock_config):
        """Removing the currently selected model resets selection to first available."""
        mock_get_config.return_value = mock_config
        mock_config.get.side_effect = lambda key: {
            "settings.custom_models.anthropic": json.dumps(["selected-model"]),
            "settings.model": "selected-model",
        }.get(key)

        request = CustomModelRequest(provider="anthropic", model_id="selected-model")
        result = await delete_custom_model(request=request, user=USER)

        assert "selected-model" not in result.custom_models
        assert "selected-model" not in result.models

        # Should have reset the active model to the first available (first base model)
        mock_config.set.assert_any_call("settings.model", ANTHROPIC_BASE_MODELS[0])
