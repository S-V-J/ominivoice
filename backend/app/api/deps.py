"""
FastAPI dependencies for authentication, rate limiting, and tenant isolation.
"""
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User, Agent, ApiKey
from app.core.config import settings

# Security scheme for JWT tokens
security = HTTPBearer(auto_error=False)


async def get_redis_client():
    """Get Redis client for rate limiting and caching."""
    import redis.asyncio as redis
    client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        yield client
    finally:
        await client.close()


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from JWT access token.

    Raises:
        HTTPException: 401 if token is missing, invalid, or expired
        HTTPException: 401 if user not found or inactive
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_token(credentials.credentials)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = token_data.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Attach user to request state for downstream use
    request.state.current_user = user
    return user


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Get the current user if authenticated, otherwise return None.
    Useful for endpoints that work both with and without auth.
    """
    if not credentials:
        return None

    try:
        return await get_current_user(request, credentials, db)
    except HTTPException:
        return None


async def get_owned_agent(
    agent_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """
    Get an agent that belongs to the current user.

    Returns 404 (not 403) if agent doesn't exist or doesn't belong to user
    to avoid leaking existence of other users' agents.

    Raises:
        HTTPException: 404 if agent not found or not owned by user
    """
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.owner_id == current_user.id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    return agent


async def get_agent_by_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """
    Authenticate an API request using an agent's API key.

    Used for webhook endpoints and external API calls.
    Rate limiting is applied per API key via Redis (handled in middleware).

    Raises:
        HTTPException: 401 if API key is missing, invalid, or inactive
        HTTPException: 404 if associated agent not found
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key_plain = credentials.credentials

    # Verify format: ov_live_<32 chars>
    if not api_key_plain.startswith("ov_live_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from app.core.security import hash_api_key
    key_hash = hash_api_key(api_key_plain)

    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load the associated agent
    result = await db.execute(select(Agent).where(Agent.id == api_key.agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated agent not found",
        )

    # Update last_used_at
    api_key.last_used_at = request.state.get("request_time")  # Will be set in middleware

    # Attach to request state for downstream use
    request.state.api_key = api_key
    request.state.agent = agent

    return agent


async def require_plan(
    min_plan: str,
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency that checks if user's plan meets minimum requirement.

    Plan hierarchy: free < starter < pro < enterprise

    Args:
        min_plan: Minimum plan required (free, starter, pro, enterprise)

    Raises:
        HTTPException: 402 if user's plan is below minimum
    """
    plan_hierarchy = {"free": 0, "starter": 1, "pro": 2, "enterprise": 3}
    user_plan_level = plan_hierarchy.get(current_user.plan, 0)
    required_level = plan_hierarchy.get(min_plan, 0)

    if user_plan_level < required_level:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"This feature requires {min_plan} plan or higher",
            headers={"X-Upgrade-Required": "true"},
        )

    return current_user