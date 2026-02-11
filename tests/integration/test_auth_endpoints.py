"""Integration tests for auth endpoints (T036).

Tests the FastAPI auth router with a real SQLite database and AuthService.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient

# Set env vars BEFORE importing app modules
os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("ALLOWED_USER_ID", "123456")
os.environ.setdefault("ADMIN_INITIAL_USERNAME", "admin")
os.environ.setdefault("ADMIN_INITIAL_PASSWORD", "adminpass123")

from fastapi import FastAPI
from presentation.api.routes import auth
from presentation.api.schemas.auth import LoginRequest
from application.services.auth_service import AuthService
from infrastructure.persistence.sqlite_web_user_repository import SQLiteWebUserRepository
from presentation.api.dependencies import set_container


class FakeContainer:
    """Minimal container that provides auth_service."""

    def __init__(self, auth_svc: AuthService):
        self._auth = auth_svc

    def auth_service(self) -> AuthService:
        return self._auth


@pytest.fixture
async def app():
    """Create a test FastAPI app with real auth service."""
    # Use temp database
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    repo = SQLiteWebUserRepository(db_path=db_path)
    auth_svc = AuthService(repository=repo)
    await auth_svc.init()

    container = FakeContainer(auth_svc)
    set_container(container)

    test_app = FastAPI()
    test_app.include_router(auth.router, prefix="/api/v1")

    yield test_app

    # Cleanup
    os.unlink(db_path)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestAuthLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"
        # Check refresh cookie
        cookies = resp.cookies
        assert "refresh_token" in cookies

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "somepassword"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_validation_error(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "ab", "password": "short"},
        )
        assert resp.status_code == 422


class TestAuthRefresh:
    @pytest.mark.asyncio
    async def test_refresh_success(self, client: AsyncClient):
        # Login first
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )
        assert login_resp.status_code == 200

        # Use refresh cookie
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    @pytest.mark.asyncio
    async def test_refresh_without_cookie(self, client: AsyncClient):
        # Create a fresh client without cookies
        transport = ASGITransport(app=client._transport.app)
        async with AsyncClient(transport=transport, base_url="http://test") as fresh:
            resp = await fresh.post("/api/v1/auth/refresh")
            assert resp.status_code == 401


class TestAuthLogout:
    @pytest.mark.asyncio
    async def test_logout_clears_cookie(self, client: AsyncClient):
        # Login
        await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )

        # Logout
        resp = await client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Logged out successfully"


class TestAuthMe:
    @pytest.mark.asyncio
    async def test_get_me(self, client: AsyncClient):
        # Login
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )
        token = login_resp.json()["access_token"]

        # Get profile
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "admin"

    @pytest.mark.asyncio
    async def test_get_me_unauthorized(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_update_me(self, client: AsyncClient):
        # Login
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )
        token = login_resp.json()["access_token"]

        # Update profile
        resp = await client.patch(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"display_name": "Super Admin", "telegram_id": 999},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["display_name"] == "Super Admin"
        assert data["telegram_id"] == 999


class TestAuthUsers:
    @pytest.mark.asyncio
    async def test_create_user(self, client: AsyncClient):
        # Login as admin
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )
        token = login_resp.json()["access_token"]

        # Create user
        resp = await client.post(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "username": "testuser",
                "password": "testpass123",
                "display_name": "Test User",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_create_duplicate_user(self, client: AsyncClient):
        # Login as admin
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create user
        await client.post(
            "/api/v1/auth/users",
            headers=headers,
            json={
                "username": "duplicate",
                "password": "testpass123",
                "display_name": "Dup",
            },
        )

        # Try again — should 409
        resp = await client.post(
            "/api/v1/auth/users",
            headers=headers,
            json={
                "username": "duplicate",
                "password": "testpass123",
                "display_name": "Dup2",
            },
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_list_users(self, client: AsyncClient):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        assert len(users) >= 1  # at least admin

    @pytest.mark.asyncio
    async def test_reset_password(self, client: AsyncClient):
        # Login as admin
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a user to reset
        create_resp = await client.post(
            "/api/v1/auth/users",
            headers=headers,
            json={
                "username": "resetme",
                "password": "oldpass12345",
                "display_name": "Reset Me",
            },
        )
        user_id = create_resp.json()["id"]

        # Reset password
        resp = await client.patch(
            f"/api/v1/auth/users/{user_id}/password",
            headers=headers,
            json={"new_password": "newpass12345"},
        )
        assert resp.status_code == 200

        # Verify new password works
        login2 = await client.post(
            "/api/v1/auth/login",
            json={"username": "resetme", "password": "newpass12345"},
        )
        assert login2.status_code == 200

    @pytest.mark.asyncio
    async def test_reset_password_nonexistent_user(self, client: AsyncClient):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.patch(
            "/api/v1/auth/users/nonexistent-id/password",
            headers={"Authorization": f"Bearer {token}"},
            json={"new_password": "newpass12345"},
        )
        assert resp.status_code == 404
