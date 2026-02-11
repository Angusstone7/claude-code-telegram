"""Unit tests for POST /settings/claude-account/credentials endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from presentation.api.routes.settings import upload_credentials
from presentation.api.schemas.settings import (
    CredentialsUploadRequest,
    CredentialsUploadResponse,
)


def _make_cred_info(
    subscription_type: str = "pro",
    rate_limit_tier: str = "tier_1",
    exists: bool = True,
    expires_at=None,
    scopes=None,
) -> MagicMock:
    """Create a mock credentials info object."""
    info = MagicMock()
    info.subscription_type = subscription_type
    info.rate_limit_tier = rate_limit_tier
    info.exists = exists
    info.expires_at = expires_at
    info.scopes = scopes or ["default"]
    return info


def _make_account_service(
    save_result: tuple = (True, "Credentials saved"),
    cred_info: MagicMock | None = None,
) -> MagicMock:
    """Create a mock AccountService with configurable behaviour."""
    svc = MagicMock()
    svc.save_credentials.return_value = save_result
    svc.get_credentials_info.return_value = cred_info or _make_cred_info()
    return svc


# -------------------------------------------------------------------------
# 1. Valid JSON credentials saved successfully
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_credentials_success():
    """Valid credentials JSON is saved and returns success=True with subscription info."""
    mock_service = _make_account_service(
        save_result=(True, "Credentials saved"),
        cred_info=_make_cred_info(subscription_type="pro", rate_limit_tier="tier_1"),
    )

    with patch("presentation.api.routes.settings.get_account_service", return_value=mock_service):
        request = CredentialsUploadRequest(
            credentials_json='{"accessToken": "tok_abc", "expiresAt": "2026-12-31"}'
        )
        response = await upload_credentials(request, user={"user_id": 1})

    assert isinstance(response, CredentialsUploadResponse)
    assert response.success is True
    assert response.subscription_type == "pro"
    assert response.rate_limit_tier == "tier_1"
    assert response.message == "Credentials saved"
    mock_service.save_credentials.assert_called_once_with(request.credentials_json)
    mock_service.get_credentials_info.assert_called_once()


# -------------------------------------------------------------------------
# 2. Invalid JSON format rejected with 422
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_credentials_invalid_json():
    """Invalid JSON string causes save_credentials to fail, resulting in HTTPException 422."""
    mock_service = _make_account_service(
        save_result=(False, "Invalid JSON format"),
    )

    with patch("presentation.api.routes.settings.get_account_service", return_value=mock_service):
        request = CredentialsUploadRequest(credentials_json="not valid json {{{")

        with pytest.raises(HTTPException) as exc_info:
            await upload_credentials(request, user={"user_id": 1})

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Invalid JSON format"
    mock_service.save_credentials.assert_called_once_with("not valid json {{{")
    mock_service.get_credentials_info.assert_not_called()


# -------------------------------------------------------------------------
# 3. save_credentials returns failure — raises HTTPException 422
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_credentials_save_failure():
    """When save_credentials returns (False, message), endpoint raises HTTPException 422."""
    mock_service = _make_account_service(
        save_result=(False, "Token expired or revoked"),
    )

    with patch("presentation.api.routes.settings.get_account_service", return_value=mock_service):
        request = CredentialsUploadRequest(
            credentials_json='{"accessToken": "expired_token"}'
        )

        with pytest.raises(HTTPException) as exc_info:
            await upload_credentials(request, user={"user_id": 1})

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Token expired or revoked"
    mock_service.get_credentials_info.assert_not_called()


# -------------------------------------------------------------------------
# 4. Subscription info is returned on success
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_credentials_returns_subscription_info():
    """Successful upload returns subscription_type and rate_limit_tier from get_credentials_info."""
    mock_service = _make_account_service(
        save_result=(True, "OK"),
        cred_info=_make_cred_info(
            subscription_type="team",
            rate_limit_tier="tier_4",
        ),
    )

    with patch("presentation.api.routes.settings.get_account_service", return_value=mock_service):
        request = CredentialsUploadRequest(
            credentials_json='{"accessToken": "tok_team", "subscriptionType": "team"}'
        )
        response = await upload_credentials(request, user={"user_id": 1})

    assert response.success is True
    assert response.subscription_type == "team"
    assert response.rate_limit_tier == "tier_4"
    assert response.message == "OK"


@pytest.mark.asyncio
async def test_upload_credentials_none_subscription_fields():
    """When credentials info has None subscription fields, response reflects that."""
    mock_service = _make_account_service(
        save_result=(True, "Saved"),
        cred_info=_make_cred_info(subscription_type=None, rate_limit_tier=None),
    )

    with patch("presentation.api.routes.settings.get_account_service", return_value=mock_service):
        request = CredentialsUploadRequest(
            credentials_json='{"accessToken": "tok_basic"}'
        )
        response = await upload_credentials(request, user={"user_id": 1})

    assert response.success is True
    assert response.subscription_type is None
    assert response.rate_limit_tier is None


# -------------------------------------------------------------------------
# 5. Empty credentials_json string
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_credentials_empty_string():
    """Empty credentials_json string is forwarded to save_credentials which rejects it."""
    mock_service = _make_account_service(
        save_result=(False, "Credentials JSON is empty"),
    )

    with patch("presentation.api.routes.settings.get_account_service", return_value=mock_service):
        request = CredentialsUploadRequest(credentials_json="")

        with pytest.raises(HTTPException) as exc_info:
            await upload_credentials(request, user={"user_id": 1})

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Credentials JSON is empty"
    mock_service.save_credentials.assert_called_once_with("")
    mock_service.get_credentials_info.assert_not_called()
