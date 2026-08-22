"""
Authentication integration tests.
"""
import pytest
from httpx import AsyncClient


class TestAuth:
    """Test authentication endpoints."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Test successful user registration."""
        response = await client.post("/auth/register", json={
            "email": "newuser@example.com",
            "password": "securepassword123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["plan"] == "free"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        """Test registration with duplicate email fails."""
        response = await client.post("/auth/register", json={
            "email": test_user.email,
            "password": "anotherpassword123",
        })
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email."""
        response = await client.post("/auth/register", json={
            "email": "not-an-email",
            "password": "password123",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Test registration with too short password."""
        response = await client.post("/auth/register", json={
            "email": "user@example.com",
            "password": "short",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user):
        """Test successful login."""
        response = await client.post("/auth/login", json={
            "email": test_user.email,
            "password": "testpassword123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        """Test login with wrong password."""
        response = await client.post("/auth/login", json={
            "email": test_user.email,
            "password": "wrongpassword",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent user."""
        response = await client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "password123",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token(self, client: AsyncClient, auth_headers):
        """Test token refresh."""
        # Get refresh token from login
        login_response = await client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "testpassword123",
        })
        refresh_token = login_response.json()["refresh_token"]

        response = await client.post("/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Test refresh with invalid token."""
        response = await client.post("/auth/refresh", json={
            "refresh_token": "invalid-token",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me(self, client: AsyncClient, auth_headers, test_user):
        """Test getting current user info."""
        response = await client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["id"] == str(test_user.id)

    @pytest.mark.asyncio
    async def test_logout(self, client: AsyncClient, auth_headers):
        """Test logout."""
        response = await client.post("/auth/logout", headers=auth_headers)
        assert response.status_code == 204


class TestTenantIsolation:
    """Test multi-tenant isolation."""

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_users_agent(
        self, client: AsyncClient, test_user, test_user2, test_agent
    ):
        """Test that user A cannot access user B's agent."""
        # Login as user 2
        login_response = await client.post("/auth/login", json={
            "email": test_user2.email,
            "password": "testpassword123",
        })
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        # Try to access user 1's agent
        response = await client.get(f"/agents/{test_agent.id}", headers=headers)
        assert response.status_code == 404  # Not 403 to avoid leaking existence

    @pytest.mark.asyncio
    async def test_user_cannot_list_other_users_agents(
        self, client: AsyncClient, test_user, test_user2, test_agent
    ):
        """Test that user A cannot see user B's agents in list."""
        # Login as user 2
        login_response = await client.post("/auth/login", json={
            "email": test_user2.email,
            "password": "testpassword123",
        })
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = await client.get("/agents", headers=headers)
        assert response.status_code == 200
        agents = response.json()
        # Should not see user 1's agent
        agent_ids = [a["id"] for a in agents]
        assert str(test_agent.id) not in agent_ids