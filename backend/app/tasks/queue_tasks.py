"""
Cold call queue processing Celery tasks.
"""
import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import async_session_maker
from app.models import Agent, ColdCallQueueEntry, QueueEntryStatus, CallLog, CallStatus, CallDirection

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.queue_tasks.process_cold_call_queue")
def process_cold_call_queue() -> dict:
    """
    Process pending cold call queue entries for all agents.
    Runs every 5 minutes via Celery beat.

    For each agent, pulls pending entries up to daily_call_cap,
    marks them as queued, and creates CallLog stubs for external dialer pickup.

    Returns:
        Dict with processing statistics
    """
    import asyncio

    async def _process():
        async with async_session_maker() as session:
            # Get all active agents with queue entries
            result = await session.execute(
                select(Agent).where(Agent.status.in_(["active", "draft"]))
            )
            agents = result.scalars().all()

            total_processed = 0
            total_queued = 0
            errors = []

            for agent in agents:
                try:
                    processed, queued = await _process_agent_queue(session, agent)
                    total_processed += processed
                    total_queued += queued
                except Exception as e:
                    logger.error(f"Error processing queue for agent {agent.id}: {e}")
                    errors.append({"agent_id": str(agent.id), "error": str(e)})

            await session.commit()

            return {
                "agents_processed": len(agents),
                "entries_processed": total_processed,
                "entries_queued": total_queued,
                "errors": errors,
            }

    return asyncio.run(_process())


async def _process_agent_queue(session: AsyncSession, agent: Agent) -> tuple[int, int]:
    """Process queue for a single agent. Returns (processed, queued) counts."""
    # Count today's queued/completed calls for daily cap check
    from sqlalchemy import func
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    result = await session.execute(
        select(func.count(CallLog.id)).where(
            CallLog.agent_id == agent.id,
            CallLog.started_at >= today_start,
            CallLog.status.in_([CallStatus.QUEUED_FOR_EXTERNAL_DIALER, CallStatus.COMPLETED])
        )
    )
    calls_today = result.scalar() or 0

    remaining_cap = max(0, agent.daily_call_cap - calls_today)
    if remaining_cap <= 0:
        return 0, 0

    # Get pending entries up to remaining cap
    result = await session.execute(
        select(ColdCallQueueEntry).where(
            ColdCallQueueEntry.agent_id == agent.id,
            ColdCallQueueEntry.status == QueueEntryStatus.PENDING
        ).order_by(ColdCallQueueEntry.created_at).limit(remaining_cap)
    )
    entries = result.scalars().all()

    if not entries:
        return 0, 0

    queued_count = 0
    for entry in entries:
        # Update entry status to queued
        entry.status = QueueEntryStatus.QUEUED
        entry.scheduled_at = datetime.now(timezone.utc)

        # Create CallLog stub for external dialer
        call_log = CallLog(
            agent_id=agent.id,
            direction=CallDirection.OUTBOUND,
            caller_ref=entry.phone_number,
            status=CallStatus.QUEUED_FOR_EXTERNAL_DIALER,
            metadata={
                "queue_entry_id": str(entry.id),
                "contact_name": entry.contact_name,
                "source": entry.source,
            }
        )
        session.add(call_log)
        await session.flush()

        # Link queue entry to call log
        entry.call_log_id = call_log.id
        queued_count += 1

        logger.info(f"Queued cold call for agent {agent.id}: {entry.contact_name} ({entry.phone_number})")

    return len(entries), queued_count


@celery_app.task(name="app.tasks.queue_tasks.retry_failed_queue_entries")
def retry_failed_queue_entries(agent_id: str, max_retries: int = 3) -> dict:
    """
    Retry failed queue entries for a specific agent.
    Can be triggered manually or via API.

    Args:
        agent_id: Agent UUID
        max_retries: Maximum retry attempts

    Returns:
        Dict with retry statistics
    """
    import asyncio
    from uuid import UUID

    async def _retry():
        async with async_session_maker() as session:
            result = await session.execute(
                select(ColdCallQueueEntry).where(
                    ColdCallQueueEntry.agent_id == UUID(agent_id),
                    ColdCallQueueEntry.status == QueueEntryStatus.FAILED,
                    ColdCallQueueEntry.attempts < max_retries
                )
            )
            entries = result.scalars().all()

            retried = 0
            for entry in entries:
                entry.status = QueueEntryStatus.PENDING
                entry.attempts += 1
                entry.last_attempt_at = datetime.now(timezone.utc)
                entry.error_message = None
                retried += 1

            await session.commit()

            return {
                "agent_id": agent_id,
                "retried": retried,
            }

    return asyncio.run(_retry())