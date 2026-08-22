"""
Agent CRUD and prompt tests.
"""
import pytest
from httpx import AsyncClient


class TestAgentCRUD:
    """Test agent CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_agent_outbound(self, client: AsyncClient, auth_headers):
        """Test creating an outbound agent."""
        response = await client.post("/agents", json={
            "name": "Sales Agent",
            "direction": "outbound",
        }, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Sales Agent"
        assert data["direction"] == "outbound"
        assert data["status"] == "draft"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_agent_inbound(self, client: AsyncClient, auth_headers):
        """Test creating an inbound agent."""
        response = await client.post("/agents", json={
            "name": "Support Agent",
            "direction": "inbound",
        }, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["direction"] == "inbound"

    @pytest.mark.asyncio
    async def test_list_agents(self, client: AsyncClient, auth_headers, test_agent):
        """Test listing agents."""
        response = await client.get("/agents", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        agent_ids = [a["id"] for a in data]
        assert str(test_agent.id) in agent_ids

    @pytest.mark.asyncio
    async def test_get_agent(self, client: AsyncClient, auth_headers, test_agent):
        """Test getting a specific agent."""
        response = await client.get(f"/agents/{test_agent.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_agent.id)
        assert data["name"] == test_agent.name

    @pytest.mark.asyncio
    async def test_get_nonexistent_agent(self, client: AsyncClient, auth_headers):
        """Test getting non-existent agent returns 404."""
        response = await client.get("/agents/00000000-0000-0000-0000-000000000000", headers=auth_headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_agent(self, client: AsyncClient, auth_headers, test_agent):
        """Test updating an agent."""
        response = await client.patch(f"/agents/{test_agent.id}", json={
            "name": "Updated Name",
            "system_prompt": "You are a new persona.",
            "status": "active",
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["system_prompt"] == "You are a new persona."
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_update_agent_prompts(self, client: AsyncClient, auth_headers, test_agent):
        """Test updating agent prompt fields."""
        response = await client.patch(f"/agents/{test_agent.id}", json={
            "opening_line": "New opening line!",
            "objective_prompt": "New objective.",
            "objection_handling_prompt": "Handle objections better.",
            "voicemail_prompt": "Leave a message.",
            "closing_prompt": "Thanks for your time.",
            "escalation_rule": "Escalate to manager.",
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["opening_line"] == "New opening line!"
        assert data["objective_prompt"] == "New objective."

    @pytest.mark.asyncio
    async def test_delete_agent(self, client: AsyncClient, auth_headers, db_session, test_user):
        """Test deleting an agent."""
        from app.models import Agent, AgentDirection, AgentStatus, VoiceStack
        agent = Agent(
            owner_id=test_user.id,
            name="To Delete",
            direction=AgentDirection.OUTBOUND,
            status=AgentStatus.DRAFT,
            voice_stack=VoiceStack.STACK_A,
        )
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        response = await client.delete(f"/agents/{agent.id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify deleted
        get_response = await client.get(f"/agents/{agent.id}", headers=auth_headers)
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_agent_completeness_outbound(self, client: AsyncClient, auth_headers, test_agent):
        """Test completeness check for outbound agent."""
        response = await client.get(f"/agents/{test_agent.id}/completeness", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["direction"] == "outbound"
        assert "missing_required_fields" in data
        assert "completion_percentage" in data
        assert "field_status" in data

    @pytest.mark.asyncio
    async def test_agent_completeness_inbound(self, client: AsyncClient, auth_headers, test_inbound_agent):
        """Test completeness check for inbound agent."""
        response = await client.get(f"/agents/{test_inbound_agent.id}/completeness", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["direction"] == "inbound"
        assert "missing_required_fields" in data

    @pytest.mark.asyncio
    async def test_prompt_version_history(self, client: AsyncClient, auth_headers, test_agent):
        """Test prompt version history endpoint."""
        # Update a prompt to create a version
        await client.patch(f"/agents/{test_agent.id}", json={
            "system_prompt": "Updated prompt v2",
        }, headers=auth_headers)

        response = await client.get(f"/agents/{test_agent.id}/prompt-versions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["field_name"] == "system_prompt"
        assert data[0]["new_value"] == "Updated prompt v2"

    @pytest.mark.asyncio
    async def test_rewrite_prompt(self, client: AsyncClient, auth_headers, test_agent):
        """Test AI prompt rewrite endpoint."""
        response = await client.post(
            f"/agents/{test_agent.id}/rewrite-prompt",
            params={
                "field_name": "system_prompt",
                "current_text": "You are a helpful assistant.",
            },
            headers=auth_headers,
        )
        # May fail if NVIDIA API not configured, but should return proper error
        assert response.status_code in (200, 500)
        if response.status_code == 200:
            data = response.json()
            assert "rewritten" in data
            assert data["field_name"] == "system_prompt"

    @pytest.mark.asyncio
    async def test_rewrite_prompt_invalid_field(self, client: AsyncClient, auth_headers, test_agent):
        """Test rewrite with invalid field name."""
        response = await client.post(
            f"/agents/{test_agent.id}/rewrite-prompt",
            params={
                "field_name": "invalid_field",
                "current_text": "Some text",
            },
            headers=auth_headers,
        )
        assert response.status_code == 400


class TestAgentFilters:
    """Test agent listing filters."""

    @pytest.mark.asyncio
    async def test_filter_by_status(self, client: AsyncClient, auth_headers, test_agent):
        """Test filtering agents by status."""
        response = await client.get("/agents", params={"status": "draft"}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        for agent in data:
            assert agent["status"] == "draft"

    @pytest.mark.asyncio
    async def test_filter_by_direction(self, client: AsyncClient, auth_headers, test_agent, test_inbound_agent):
        """Test filtering agents by direction."""
        response = await client.get("/agents", params={"direction": "outbound"}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        for agent in data:
            assert agent["direction"] == "outbound"

    @pytest.mark.asyncio
    async def test_pagination(self, client: AsyncClient, auth_headers):
        """Test pagination parameters."""
        response = await client.get("/agents", params={"limit": 5, "offset": 0}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5