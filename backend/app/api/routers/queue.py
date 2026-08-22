"""
Cold Call Queue API routes.
Handles CSV/JSON import, listing, filtering, and statistics for outbound call queues.
"""
import csv
import io
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile, status
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_owned_agent, get_db
from app.models import Agent, ColdCallQueueEntry, QueueEntryStatus, User
from app.schemas.schemas import (
    ColdCallQueueEntryCreate,
    ColdCallQueueEntryBulkCreate,
    ColdCallQueueEntryUpdate,
    ColdCallQueueEntryResponse,
    ColdCallQueueStatsResponse,
)
from app.tasks.queue_tasks import retry_failed_queue_entries

router = APIRouter()


@router.post(
    "/agents/{agent_id}/cold-call-queue/import",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
async def import_cold_call_queue(
    agent: Agent = Depends(get_owned_agent),
    file: Optional[UploadFile] = File(None, description="CSV file with contact_name,phone_number columns"),
    json_data: Optional[List[ColdCallQueueEntryCreate]] = None,
    source: str = Query("csv_upload", description="Source identifier for the import"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Import cold call queue entries via CSV upload or JSON array.

    CSV format: contact_name,phone_number,[extra columns...]
    JSON format: Array of {contact_name, phone_number, payload}

    Validates phone numbers and deduplicates on (agent_id, phone_number).
    """
    entries_to_create = []

    if file:
        # Parse CSV
        if not file.filename.endswith(".csv"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a CSV",
            )

        content = await file.read()
        try:
            decoded = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV must be UTF-8 encoded",
            )

        reader = csv.DictReader(io.StringIO(decoded))
        required_columns = {"contact_name", "phone_number"}
        if not required_columns.issubset(set(reader.fieldnames or [])):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV must contain columns: {', '.join(required_columns)}",
            )

        for row in reader:
            contact_name = row.get("contact_name", "").strip()
            phone_number = row.get("phone_number", "").strip()

            if not contact_name or not phone_number:
                continue

            # Validate phone number
            try:
                import phonenumbers
                parsed = phonenumbers.parse(phone_number, None)
                if not phonenumbers.is_valid_number(parsed):
                    continue
                phone_number = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            except Exception:
                continue

            # Extra columns go to payload
            payload = {k: v for k, v in row.items() if k not in required_columns and v}

            entries_to_create.append(
                ColdCallQueueEntryCreate(
                    contact_name=contact_name,
                    phone_number=phone_number,
                    payload=payload or {},
                )
            )

    elif json_data:
        for entry in json_data:
            phone_number = entry.phone_number.strip()
            try:
                import phonenumbers
                parsed = phonenumbers.parse(phone_number, None)
                if not phonenumbers.is_valid_number(parsed):
                    continue
                phone_number = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            except Exception:
                continue

            entries_to_create.append(
                ColdCallQueueEntryCreate(
                    contact_name=entry.contact_name.strip(),
                    phone_number=phone_number,
                    payload=entry.payload or {},
                )
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either CSV file or JSON data must be provided",
        )

    if not entries_to_create:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid entries found in import",
        )

    # Insert entries with dedupe on (agent_id, phone_number)
    created = 0
    skipped = 0
    errors = []

    for entry_data in entries_to_create:
        try:
            # Check for existing entry
            result = await db.execute(
                select(ColdCallQueueEntry).where(
                    ColdCallQueueEntry.agent_id == agent.id,
                    ColdCallQueueEntry.phone_number == entry_data.phone_number,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            entry = ColdCallQueueEntry(
                agent_id=agent.id,
                contact_name=entry_data.contact_name,
                phone_number=entry_data.phone_number,
                source=source,
                payload=entry_data.payload,
                status=QueueEntryStatus.PENDING,
            )
            db.add(entry)
            created += 1

        except Exception as e:
            errors.append({"phone_number": entry_data.phone_number, "error": str(e)})

    await db.commit()

    return {
        "agent_id": str(agent.id),
        "created": created,
        "skipped_duplicates": skipped,
        "errors": len(errors),
        "error_details": errors[:10] if errors else [],
    }


@router.get(
    "/agents/{agent_id}/cold-call-queue",
    response_model=List[ColdCallQueueEntryResponse],
)
async def list_queue_entries(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[QueueEntryStatus] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at", regex="^(created_at|scheduled_at|contact_name|status)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
) -> List[ColdCallQueueEntryResponse]:
    """
    List cold call queue entries for an agent with filtering and pagination.
    """
    query = select(ColdCallQueueEntry).where(ColdCallQueueEntry.agent_id == agent.id)

    if status_filter:
        query = query.where(ColdCallQueueEntry.status == status_filter)

    # Sorting
    sort_column = getattr(ColdCallQueueEntry, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    entries = result.scalars().all()

    return [
        ColdCallQueueEntryResponse(
            id=str(e.id),
            agent_id=str(e.agent_id),
            contact_name=e.contact_name,
            phone_number=e.phone_number,
            source=e.source,
            status=e.status,
            payload=e.payload or {},
            call_log_id=str(e.call_log_id) if e.call_log_id else None,
            created_at=e.created_at,
            updated_at=e.updated_at,
        )
        for e in entries
    ]


@router.get(
    "/agents/{agent_id}/cold-call-queue/stats",
    response_model=ColdCallQueueStatsResponse,
)
async def get_queue_stats(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
) -> ColdCallQueueStatsResponse:
    """
    Get queue statistics (counts by status) for an agent.
    """
    result = await db.execute(
        select(
            ColdCallQueueEntry.status,
            func.count(ColdCallQueueEntry.id),
        )
        .where(ColdCallQueueEntry.agent_id == agent.id)
        .group_by(ColdCallQueueEntry.status)
    )
    counts = {row[0]: row[1] for row in result.all()}

    return ColdCallQueueStatsResponse(
        agent_id=str(agent.id),
        total=sum(counts.values()),
        pending=counts.get(QueueEntryStatus.PENDING, 0),
        queued=counts.get(QueueEntryStatus.QUEUED, 0),
        in_progress=counts.get(QueueEntryStatus.IN_PROGRESS, 0),
        completed=counts.get(QueueEntryStatus.COMPLETED, 0),
        failed=counts.get(QueueEntryStatus.FAILED, 0),
    )


@router.patch(
    "/agents/{agent_id}/cold-call-queue/{entry_id}",
    response_model=ColdCallQueueEntryResponse,
)
async def update_queue_entry(
    agent: Agent = Depends(get_owned_agent),
    entry_id: UUID = Path(..., description="Queue entry ID"),
    update_data: ColdCallQueueEntryUpdate = ...,
    db: AsyncSession = Depends(get_db),
) -> ColdCallQueueEntryResponse:
    """
    Update a queue entry (contact_name, phone_number, status, payload).
    """
    result = await db.execute(
        select(ColdCallQueueEntry).where(
            ColdCallQueueEntry.id == entry_id,
            ColdCallQueueEntry.agent_id == agent.id,
        )
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue entry not found",
        )

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if value is not None:
            setattr(entry, field, value)

    entry.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entry)

    return ColdCallQueueEntryResponse(
        id=str(entry.id),
        agent_id=str(entry.agent_id),
        contact_name=entry.contact_name,
        phone_number=entry.phone_number,
        source=entry.source,
        status=entry.status,
        payload=entry.payload or {},
        call_log_id=str(entry.call_log_id) if entry.call_log_id else None,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.post(
    "/agents/{agent_id}/cold-call-queue/retry-failed",
    response_model=dict,
)
async def retry_failed_entries(
    agent: Agent = Depends(get_owned_agent),
    max_retries: int = Query(3, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Retry failed queue entries by resetting them to pending.
    Triggers the Celery task to process them.
    """
    task = retry_failed_queue_entries.delay(str(agent.id), max_retries)
    result = task.get(timeout=30)  # Wait for task completion

    return {
        "agent_id": str(agent.id),
        "retried": result.get("retried", 0),
        "task_id": task.id,
    }


@router.delete(
    "/agents/{agent_id}/cold-call-queue/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_queue_entry(
    agent: Agent = Depends(get_owned_agent),
    entry_id: UUID = Path(..., description="Queue entry ID"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a queue entry (only if pending or failed).
    """
    result = await db.execute(
        select(ColdCallQueueEntry).where(
            ColdCallQueueEntry.id == entry_id,
            ColdCallQueueEntry.agent_id == agent.id,
        )
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue entry not found",
        )

    if entry.status not in (QueueEntryStatus.PENDING, QueueEntryStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete pending or failed entries",
        )

    await db.delete(entry)
    await db.commit()