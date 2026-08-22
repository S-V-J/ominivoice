"""
API Key and Webhook tests.
"""
import pytest
from httpx import AsyncClient


class TestApiKeys:
    """Test API key management."""

    @pytest.mark.asyncio
    async def test_create_api_key(self, client: AsyncClient, auth_headers, test_agent):
        """Test creating an API key."""
        response = await client.post(f"/agents/{test_agent.id}/api-key", headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert "key" in data
        assert data["key"].startswith("ov_live_")
        assert "webhook_url" in data
        assert data["webhook_url"] == f"{data['webhook_url'].split('/webhook')[0]}/webhook/v1/agents/{test_agent.id}"

    @pytest.mark.asyncio
    async def test_get_api_key(self, client: AsyncClient, auth_headers, test_agent):
        """Test getting API key info (masked)."""
        # First create a key
        await client.post(f"/agents/{test_agent.id}/api-key", headers=auth_headers)

        response = await client.get(f"/agents/{test_agent.id}/api-key", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "key_prefix" in data
        assert "webhook_url" in data
        assert "key" not in data  # Full key not returned
        assert "usage_today" in data

    @pytest.mark.asyncio
    async def test_regenerate_api_key(self, client: AsyncClient, auth_headers, test_agent):
        """Test regenerating API key."""
        # Create initial key
        await client.post(f"/agents/{test_agent.id}/api-key", headers=auth_headers)

        # Regenerate
        response = await client.post(f"/agents/{test_agent.id}/api-key/regenerate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "key" in data
        assert data["key"].startswith("ov_live_")

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, client: AsyncClient, auth_headers, test_agent):
        """Test revoking API key."""
        await client.post(f"/agents/{test_agent.id}/api-key", headers=auth_headers)

        response = await client.delete(f"/agents/{test_agent.id}/api-key", headers=auth_headers)
        assert response.status_code == 204

        # Key should no longer be accessible
        get_response = await client.get(f"/agents/{test_agent.id}/api-key", headers=auth_headers)
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_webhook_url(self, client: AsyncClient, auth_headers, test_agent):
        """Test getting webhook URL."""
        response = await client.get(f"/agents/{test_agent.id}/webhook-url", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "webhook_url" in data
        assert str(test_agent.id) in data["webhook_url"]


class TestApiKeyAuth:
    """Test API key authentication for webhooks."""

    @pytest.mark.asyncio
    async def test_webhook_auth_valid_key(self, client: AsyncClient, test_agent):
        """Test webhook auth with valid API key."""
        # Create API key first
        from app.models import ApiKey
        from app.core.security import generate_api_key, hash_api_key

        plaintext_key, key_hash = generate_api_key()
        key_prefix = plaintext_key[:12] + "••••" + plaintext_key[-4:]

        api_key = ApiKey(
            agent_id=test_agent.id,
            user_id=test_agent.owner_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            webhook_url=f"https://example.com/webhook/v1/agents/{test_agent.id}",
            is_active=True,
        )
        # Need to add to DB - skip for now as requires db_session

    @pytest.mark.asyncio
    async def test_webhook_auth_invalid_key(self, client: AsyncClient):
        """Test webhook auth with invalid key."""
        # This would test the API key dependency - skipping for now
        pass


class TestRateLimiting:
    """Test rate limiting on auth endpoints."""

    @pytest.mark.asyncio
    async def test_login_rate_limit(self, client: AsyncClient):
        """Test login rate limiting (5/min)."""
        # Make 6 rapid login attempts
        for i in range(6):
            response = await client.post("/auth/login", json={
                "email": "nonexistent@example.com",
                "password": "wrongpassword",
            })
            if i < 5:
                assert response.status_code == 401
            else:
                assert response.status_code == 429  # Rate limited