"""
Admin API routes for OminiVoice.
Requires admin authentication and IP restriction.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis_client
from app.core.config import settings
from app.models import User, Agent, CallLog, ColdCallQueueEntry, Subscription, Account, AuditLog, UserRole
from app.schemas.schemas import AdminStatsResponse, AdminUserResponse, AdminAgentResponse

router = APIRouter(prefix="/admin", tags=["Admin"])


async def require_admin(current_user: User = Depends(get_current_user), request: Request = None) -> User:
    """Dependency that requires admin role."""
    # Check if user is admin of any account
    from sqlalchemy import select
    from app.models import AccountMember

    db: AsyncSession = request.state.db if request else None
    if not db:
        from app.core.database import async_session_maker
        async with async_session_maker() as session:
            result = await session.execute(
                select(AccountMember).where(
                    AccountMember.user_id == current_user.id,
                    AccountMember.role.in_([UserRole.OWNER, UserRole.ADMIN]),
                    AccountMember.accepted_at.isnot(None)
                )
            )
            membership = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(AccountMember).where(
                AccountMember.user_id == current_user.id,
                AccountMember.role.in_([UserRole.OWNER, UserRole.ADMIN]),
                AccountMember.accepted_at.isnot(None)
            )
        )
        membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return current_user


def check_admin_ip(request: Request) -> None:
    """Check if request IP is allowed for admin access."""
    allowed_ips = settings.ADMIN_ALLOWED_IPS
    if not allowed_ips:
        return  # No restriction configured

    client_ip = request.client.host if request.client else "unknown"
    # Check against allowed IPs (supports CIDR notation)
    import ipaddress
    try:
        client_ip_obj = ipaddress.ip_address(client_ip)
        allowed = any(client_ip_obj in ipaddress.ip_network(allowed_ip, strict=False) for allowed_ip in allowed_ips)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: IP not in allowed list"
            )
    except ValueError:
        # Invalid IP, deny
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Invalid IP"
        )


@router.get("/stats", response_model=AdminStatsResponse)
async def get_platform_stats(
    current_user: User = Depends(require_admin),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> AdminStatsResponse:
    """Get platform-wide statistics."""
    check_admin_ip(request)

    # Total users
    total_users = await db.execute(select(func.count(User.id)))
    total_users = total_users.scalar() or 0

    # Active users (logged in last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    # Note: We'd need a last_login_at field for this
    active_users = total_users  # Placeholder

    # Total agents
    total_agents = await db.execute(select(func.count(Agent.id)))
    total_agents = total_agents.scalar() or 0

    # Total calls (last 30 days)
    total_calls = await db.execute(
        select(func.count(CallLog.id)).where(CallLog.started_at >= thirty_days_ago)
    )
    total_calls = total_calls.scalar() or 0

    # Calls per minute (avg over last hour)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_calls = await db.execute(
        select(func.count(CallLog.id)).where(CallLog.started_at >= one_hour_ago)
    )
    calls_per_minute = (recent_calls.scalar() or 0) / 60

    # Queue depth (pending + queued)
    queue_depth = await db.execute(
        select(func.count(ColdCallQueueEntry.id)).where(
            ColdCallQueueEntry.status.in_(["pending", "queued"])
        )
    )
    queue_depth = queue_depth.scalar() or 0

    # Revenue (from Stripe - would need webhook data)
    # Placeholder
    monthly_revenue = 0.0

    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_agents=total_agents,
        total_calls_30d=total_calls,
        calls_per_minute=round(calls_per_minute, 2),
        queue_depth=queue_depth,
        monthly_revenue=monthly_revenue,
    )


@router.get("/users", response_model=List[AdminUserResponse])
async def list_users(
    current_user: User = Depends(require_admin),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> List[AdminUserResponse]:
    """List all users with pagination and search."""
    check_admin_ip(request)

    query = select(User)

    if search:
        query = query.where(
            or_(
                User.email.ilike(f"%{search}%"),
                User.id.cast(String).ilike(f"%{search}%"),
            )
        )

    query = query.order_by(desc(User.created_at)).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    users = result.scalars().all()

    # Get agent counts and subscription info for each user
    user_responses = []
    for user in users:
        agent_count = await db.execute(
            select(func.count(Agent.id)).where(Agent.owner_id == user.id)
        )

        sub_result = await db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        subscription = sub_result.scalar_one_or_none()

        user_responses.append(AdminUserResponse(
            id=user.id,
            email=user.email,
            plan=user.plan,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            agent_count=agent_count.scalar() or 0,
            subscription_status=subscription.status if subscription else None,
            subscription_plan=subscription.plan if subscription else None,
        ))

    return user_responses


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    """Get detailed user information."""
    check_admin_ip(request)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    agent_count = await db.execute(
        select(func.count(Agent.id)).where(Agent.owner_id == user.id)
    )

    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = sub_result.scalar_one_or_none()

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        plan=user.plan,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        agent_count=agent_count.scalar() or 0,
        subscription_status=subscription.status if subscription else None,
        subscription_plan=subscription.plan if subscription else None,
    )


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Suspend a user account."""
    check_admin_ip(request)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot suspend yourself")

    user.is_active = False
    await db.commit()

    # Log audit event
    await _log_audit(db, current_user, "user.suspend", "user", str(user_id), None, {"email": user.email})

    return {"message": "User suspended"}


@router.post("/users/{user_id}/unsuspend")
async def unsuspend_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Unsuspend a user account."""
    check_admin_ip(request)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    await db.commit()

    await _log_audit(db, current_user, "user.unsuspend", "user", str(user_id), None, {"email": user.email})

    return {"message": "User unsuspended"}


@router.get("/agents", response_model=List[AdminAgentResponse])
async def list_all_agents(
    current_user: User = Depends(require_admin),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(None),
    owner_email: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> List[AdminAgentResponse]:
    """List all agents across all users."""
    check_admin_ip(request)

    query = select(Agent, User.email).join(User, Agent.owner_id == User.id)

    if status_filter:
        query = query.where(Agent.status == status_filter)
    if owner_email:
        query = query.where(User.email.ilike(f"%{owner_email}%"))

    query = query.order_by(desc(Agent.created_at)).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    return [
        AdminAgentResponse(
            id=agent.id,
            name=agent.name,
            direction=agent.direction,
            status=agent.status,
            owner_email=email,
            owner_id=agent.owner_id,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )
        for agent, email in rows
    ]


@router.get("/audit-logs")
async def get_audit_logs(
    current_user: User = Depends(require_admin),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    action: Optional[str] = Query(None),
    user_id: Optional[UUID] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
) -> dict:
    """Get audit logs with filtering."""
    check_admin_ip(request)

    query = select(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)

    query = query.order_by(desc(AuditLog.created_at)).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    logs = result.scalars().all()

    total = await db.execute(select(func.count(AuditLog.id)))

    return {
        "logs": [
            {
                "id": str(log.id),
                "user_id": str(log.user_id) if log.user_id else None,
                "account_id": str(log.account_id) if log.account_id else None,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "created_at": log.created_at,
            }
            for log in logs
        ],
        "total": total.scalar() or 0,
        "page": page,
        "page_size": page_size,
    }


async def _log_audit(
    db: AsyncSession,
    actor: User,
    action: str,
    resource_type: str,
    resource_id: str,
    old_values: dict = None,
    new_values: dict = None,
    ip_address: str = None,
    user_agent: str = None,
):
    """Helper to log audit events."""
    audit_log = AuditLog(
        user_id=actor.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(audit_log)
    await db.commit()