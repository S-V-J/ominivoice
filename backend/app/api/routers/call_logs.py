"""
Call Logs API routes.
Handles call log retrieval and audio file access.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_owned_agent, get_db
from app.models import CallLog, CallStatus, CallDirection, Agent, User
from app.schemas.schemas import CallLogResponse

router = APIRouter()


@router.get(
    "/agents/{agent_id}/calls",
    response_model=List[CallLogResponse],
)
async def list_call_logs(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[CallStatus] = Query(None, alias="status"),
    direction_filter: Optional[CallDirection] = Query(None, alias="direction"),
    start_date: Optional[datetime] = Query(None, alias="start_date"),
    end_date: Optional[datetime] = Query(None, alias="end_date"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[CallLogResponse]:
    """
    List call logs for an agent with filtering and pagination.
    """
    query = select(CallLog).where(CallLog.agent_id == agent.id)

    if status_filter:
        query = query.where(CallLog.status == status_filter)
    if direction_filter:
        query = query.where(CallLog.direction == direction_filter)
    if start_date:
        query = query.where(CallLog.started_at >= start_date)
    if end_date:
        query = query.where(CallLog.started_at <= end_date)

    query = query.order_by(desc(CallLog.started_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        CallLogResponse(
            id=str(log.id),
            agent_id=str(log.agent_id),
            direction=log.direction,
            caller_ref=log.caller_ref,
            transcript=log.transcript or [],
            duration_s=log.duration_s,
            status=log.status,
            started_at=log.started_at,
            ended_at=log.ended_at,
            error_message=log.error_message,
        )
        for log in logs
    ]


@router.get(
    "/agents/{agent_id}/calls/{call_id}",
    response_model=CallLogResponse,
)
async def get_call_log(
    agent: Agent = Depends(get_owned_agent),
    call_id: UUID = None,
    db: AsyncSession = Depends(get_db),
) -> CallLogResponse:
    """
    Get a specific call log with full transcript.
    """
    result = await db.execute(
        select(CallLog).where(CallLog.id == call_id, CallLog.agent_id == agent.id)
    )
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call log not found",
        )

    return CallLogResponse(
        id=str(log.id),
        agent_id=str(log.agent_id),
        direction=log.direction,
        caller_ref=log.caller_ref,
        transcript=log.transcript or [],
        duration_s=log.duration_s,
        status=log.status,
        started_at=log.started_at,
        ended_at=log.ended_at,
        error_message=log.error_message,
    )


@router.get(
    "/agents/{agent_id}/calls/stats",
)
async def get_call_stats(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
    start_date: Optional[datetime] = Query(None, alias="start_date"),
    end_date: Optional[datetime] = Query(None, alias="end_date"),
) -> dict:
    """
    Get call statistics for an agent.
    """
    query = select(CallLog).where(CallLog.agent_id == agent.id)

    if start_date:
        query = query.where(CallLog.started_at >= start_date)
    if end_date:
        query = query.where(CallLog.started_at <= end_date)

    result = await db.execute(query)
    logs = result.scalars().all()

    total = len(logs)
    completed = sum(1 for l in logs if l.status == CallStatus.COMPLETED)
    failed = sum(1 for l in logs if l.status == CallStatus.FAILED)
    inbound = sum(1 for l in logs if l.direction == CallDirection.INBOUND)
    outbound = sum(1 for l in logs if l.direction == CallDirection.OUTBOUND)
    total_duration = sum(l.duration_s or 0 for l in logs)
    avg_duration = total_duration / completed if completed > 0 else 0

    return {
        "total_calls": total,
        "completed": completed,
        "failed": failed,
        "inbound": inbound,
        "outbound": outbound,
        "total_duration_seconds": total_duration,
        "average_duration_seconds": round(avg_duration, 1),
        "success_rate": round(completed / total * 100, 1) if total > 0 else 0,
    }