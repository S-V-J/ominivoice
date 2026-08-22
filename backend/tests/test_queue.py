"""
Cold Call Queue tests.
"""
import pytest
import io
import csv
from httpx import AsyncClient


class TestQueueImport:
    """Test cold call queue import functionality."""

    @pytest.mark.asyncio
    async def test_import_csv(self, client: AsyncClient, auth_headers, test_agent):
        """Test importing queue entries via CSV."""
        csv_content = """contact_name,phone_number,email,company
John Doe,+15551234567,john@example.com,Acme Corp
Jane Smith,+15559876543,jane@example.com,Globex Inc
Bob Wilson,+15552468135,bob@example.com,Initech"""

        file = io.BytesIO(csv_content.encode('utf-8'))
        files = {"file": ("contacts.csv", file, "text/csv")}

        response = await client.post(
            f"/agents/{test_agent.id}/cold-call-queue/import",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 3
        assert data["skipped_duplicates"] == 0

    @pytest.mark.asyncio
    async def test_import_csv_dedupe(self, client: AsyncClient, auth_headers, test_agent):
        """Test that duplicate phone numbers are skipped."""
        csv_content = """contact_name,phone_number
John Doe,+15551234567
Jane Smith,+15559876543"""

        file = io.BytesIO(csv_content.encode('utf-8'))
        files = {"file": ("contacts.csv", file, "text/csv")}

        # First import
        await client.post(
            f"/agents/{test_agent.id}/cold-call-queue/import",
            files=files,
            headers=auth_headers,
        )

        # Second import with same numbers
        file = io.BytesIO(csv_content.encode('utf-8'))
        files = {"file": ("contacts.csv", file, "text/csv")}

        response = await client.post(
            f"/agents/{test_agent.id}/cold-call-queue/import",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 0
        assert data["skipped_duplicates"] == 2

    @pytest.mark.asyncio
    async def test_import_json(self, client: AsyncClient, auth_headers, test_agent):
        """Test importing queue entries via JSON."""
        entries = [
            {"contact_name": "Alice Brown", "phone_number": "+15551112222", "payload": {"lead_source": "web"}},
            {"contact_name": "Charlie Green", "phone_number": "+15553334444", "payload": {}},
        ]

        response = await client.post(
            f"/agents/{test_agent.id}/cold-call-queue/import",
            json=entries,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 2

    @pytest.mark.asyncio
    async def test_import_invalid_phone(self, client: AsyncClient, auth_headers, test_agent):
        """Test that invalid phone numbers are skipped."""
        csv_content = """contact_name,phone_number
Valid User,+15551234567
Invalid User,not-a-phone-number
Another Valid,+15559876543"""

        file = io.BytesIO(csv_content.encode('utf-8'))
        files = {"file": ("contacts.csv", file, "text/csv")}

        response = await client.post(
            f"/agents/{test_agent.id}/cold-call-queue/import",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 2
        assert data["errors"] == 0  # Invalid ones just skipped


class TestQueueList:
    """Test queue listing and filtering."""

    @pytest.mark.asyncio
    async def test_list_queue_entries(self, client: AsyncClient, auth_headers, test_agent):
        """Test listing queue entries."""
        # First add some entries
        csv_content = """contact_name,phone_number
User One,+15551111111
User Two,+15552222222"""
        file = io.BytesIO(csv_content.encode('utf-8'))
        files = {"file": ("contacts.csv", file, "text/csv")}
        await client.post(
            f"/agents/{test_agent.id}/cold-call-queue/import",
            files=files,
            headers=auth_headers,
        )

        response = await client.get(f"/agents/{test_agent.id}/cold-call-queue", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    @pytest.mark.asyncio
    async def test_filter_by_status(self, client: AsyncClient, auth_headers, test_agent):
        """Test filtering queue by status."""
        response = await client.get(
            f"/agents/{test_agent.id}/cold-call-queue",
            params={"status": "pending"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        for entry in data:
            assert entry["status"] == "pending"

    @pytest.mark.asyncio
    async def test_pagination(self, client: AsyncClient, auth_headers, test_agent):
        """Test pagination."""
        response = await client.get(
            f"/agents/{test_agent.id}/cold-call-queue",
            params={"limit": 1, "offset": 0},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 1

    @pytest.mark.asyncio
    async def test_sorting(self, client: AsyncClient, auth_headers, test_agent):
        """Test sorting options."""
        for sort_by in ["created_at", "contact_name", "status", "scheduled_at"]:
            for sort_order in ["asc", "desc"]:
                response = await client.get(
                    f"/agents/{test_agent.id}/cold-call-queue",
                    params={"sort_by": sort_by, "sort_order": sort_order},
                    headers=auth_headers,
                )
                assert response.status_code == 200


class TestQueueStats:
    """Test queue statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self, client: AsyncClient, auth_headers, test_agent):
        """Test getting queue statistics."""
        response = await client.get(f"/agents/{test_agent.id}/cold-call-queue/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "agent_id" in data
        assert "total" in data
        assert "pending" in data
        assert "queued" in data
        assert "completed" in data
        assert "failed" in data


class TestQueueUpdate:
    """Test queue entry updates."""

    @pytest.mark.asyncio
    async def test_update_entry_status(self, client: AsyncClient, auth_headers, test_agent):
        """Test updating queue entry status."""
        # Add entry
        csv_content = "contact_name,phone_number\nTest User,+15551234567"
        file = io.BytesIO(csv_content.encode('utf-8'))
        files = {"file": ("contacts.csv", file, "text/csv")}
        import_resp = await client.post(
            f"/agents/{test_agent.id}/cold-call-queue/import",
            files=files,
            headers=auth_headers,
        )

        # Get the entry ID
        list_resp = await client.get(f"/agents/{test_agent.id}/cold-call-queue", headers=auth_headers)
        entry = list_resp.json()[0]
        entry_id = entry["id"]

        # Update status
        response = await client.patch(
            f"/agents/{test_agent.id}/cold-call-queue/{entry_id}",
            json={"status": "queued"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_retry_failed(self, client: AsyncClient, auth_headers, test_agent, db_session):
        """Test retrying failed entries."""
        from app.models import ColdCallQueueEntry, QueueEntryStatus
        from uuid import uuid4

        # Create a failed entry
        entry = ColdCallQueueEntry(
            agent_id=test_agent.id,
            contact_name="Failed User",
            phone_number="+15559999999",
            status=QueueEntryStatus.FAILED,
            attempts=1,
            error_message="Test error",
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)

        response = await client.post(
            f"/agents/{test_agent.id}/cold-call-queue/retry-failed",
            params={"max_retries": 3},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["retried"] >= 1


class TestQueueDelete:
    """Test queue entry deletion."""

    @pytest.mark.asyncio
    async def test_delete_pending_entry(self, client: AsyncClient, auth_headers, test_agent):
        """Test deleting a pending entry."""
        csv_content = "contact_name,phone_number\nDelete Me,+15558888888"
        file = io.BytesIO(csv_content.encode('utf-8'))
        files = {"file": ("contacts.csv", file, "text/csv")}
        import_resp = await client.post(
            f"/agents/{test_agent.id}/cold-call-queue/import",
            files=files,
            headers=auth_headers,
        )

        list_resp = await client.get(f"/agents/{test_agent.id}/cold-call-queue", headers=auth_headers)
        entry = list_resp.json()[0]

        response = await client.delete(
            f"/agents/{test_agent.id}/cold-call-queue/{entry['id']}",
            headers=auth_headers,
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_cannot_delete_queued(self, client: AsyncClient, auth_headers, test_agent, db_session):
        """Test that queued entries cannot be deleted."""
        from app.models import ColdCallQueueEntry, QueueEntryStatus

        entry = ColdCallQueueEntry(
            agent_id=test_agent.id,
            contact_name="Queued User",
            phone_number="+15557777777",
            status=QueueEntryStatus.QUEUED,
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)

        response = await client.delete(
            f"/agents/{test_agent.id}/cold-call-queue/{entry.id}",
            headers=auth_headers,
        )
        assert response.status_code == 400