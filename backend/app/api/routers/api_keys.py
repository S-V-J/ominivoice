"""
API Key and Webhook management routes.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_owned_agent, get_db, get_redis_client
from app.core.security import generate_api_key, hash_api_key
from app.models import Agent, ApiKey, CallLog, CallStatus, User
from app.schemas.schemas import (
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeyMaskedResponse,
)

router = APIRouter()


@router.post("/agents/{agent_id}/api-key", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiKeyResponse:
    """
    Generate a new API key for an agent.

    Returns the plaintext key ONCE - store it securely.
    The key format is: ov_live_<32 random url-safe chars>
    """
    # Revoke any existing active keys for this agent (single active key per agent)
    from sqlalchemy import update
    await db.execute(
        update(ApiKey)
        .where(ApiKey.agent_id == agent.id, ApiKey.is_active == True)
        .values(is_active=False)
    )

    # Generate new key
    plaintext_key, key_hash = generate_api_key()
    key_prefix = plaintext_key[:12] + "••••" + plaintext_key[-4:]

    # Build webhook URL
    from app.core.config import settings
    webhook_url = f"{settings.FRONTEND_URL}/webhook/v1/agents/{agent.id}"

    api_key = ApiKey(
        agent_id=agent.id,
        user_id=current_user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        webhook_url=webhook_url,
        is_active=True,
    )

    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyResponse(
        id=api_key.id,
        agent_id=api_key.agent_id,
        key=plaintext_key,
        key_prefix=key_prefix,
        webhook_url=webhook_url,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
    )


@router.post("/agents/{agent_id}/api-key/regenerate", response_model=ApiKeyResponse)
async def regenerate_api_key(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiKeyResponse:
    """
    Regenerate an agent's API key.

    Immediately invalidates the old key. Returns new plaintext key ONCE.
    """
    # This is the same as create - revokes old and creates new
    return await create_api_key(agent, db, current_user)


@router.get("/agents/{agent_id}/api-key", response_model=ApiKeyMaskedResponse)
async def get_api_key(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyMaskedResponse:
    """
    Get the current API key info (masked) for an agent.
    """
    result = await db.execute(
        select(ApiKey).where(ApiKey.agent_id == agent.id, ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active API key found for this agent",
        )

    # Get usage stats (calls today)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(CallLog.id)).where(
            CallLog.agent_id == agent.id,
            CallLog.started_at >= today_start,
        )
    )
    calls_today = result.scalar() or 0

    return ApiKeyMaskedResponse(
        id=api_key.id,
        agent_id=api_key.agent_id,
        key_prefix=api_key.key_prefix,
        webhook_url=api_key.webhook_url,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        usage_today=calls_today,
    )


@router.delete("/agents/{agent_id}/api-key", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Revoke (deactivate) an agent's API key.

    Does not delete the key record for audit purposes.
    """
    result = await db.execute(
        select(ApiKey).where(ApiKey.agent_id == agent.id, ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active API key found for this agent",
        )

    api_key.is_active = False
    await db.commit()


@router.get("/agents/{agent_id}/webhook-url")
async def get_webhook_url(
    agent: Agent = Depends(get_owned_agent),
) -> dict:
    """
    Get the webhook URL for an agent.

    This is the URL external systems should POST to for interacting with this agent.
    """
    from app.core.config import settings
    webhook_url = f"{settings.FRONTEND_URL}/webhook/v1/agents/{agent.id}"
    return {"webhook_url": webhook_url}


@router.get("/agents/{agent_id}/websocket-urls")
async def get_websocket_urls(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get WebSocket URLs for connecting to this agent's voice engine.

    Returns a COMMON WebSocket endpoint for all agents.
    Authentication is via API key query parameter (?api_key=...) or test token (?token=...).
    The server resolves the agent from the API key.

    For local testing: wss://ominivoice.local/ws?api_key=...
    For internet (AWS): wss://api.yourdomain.com/ws?api_key=...

    Note: Local URLs require mkcert certificates and /etc/hosts entry.
    """
    from app.core.config import settings
    from app.models import ApiKey

    # Get the active API key for this agent
    result = await db.execute(
        select(ApiKey).where(ApiKey.agent_id == agent.id, ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active API key found. Generate an API key first.",
        )

    key_prefix = api_key.key_prefix

    # Common WebSocket endpoint (same for all agents)
    # Agent is resolved from the API key
    local_ws_url = "wss://ominivoice.local/ws"
    internet_ws_url = "wss://api.ominivoice.com/ws"

    return {
        "agent_id": str(agent.id),
        "api_key_prefix": key_prefix,
        "note": "Use the COMMON WebSocket URL with ?api_key=YOUR_FULL_API_KEY or ?token=TEST_TOKEN",
        "common_websocket_endpoint": "wss://<domain>/ws",
        "authentication": "Query parameter: ?api_key=ov_live_... OR ?token=<jwt_test_token>",
        "local": {
            "description": "For local LAN testing (requires mkcert + /etc/hosts)",
            "websocket_url": local_ws_url,
            "example_full": f"{local_ws_url}?api_key=ov_live_<your_32_char_key>",
            "https_base": "https://ominivoice.local",
            "api_docs": "https://ominivoice.local/docs",
        },
        "internet": {
            "description": "For internet/AWS deployment (configure after deployment)",
            "websocket_url": internet_ws_url,
            "example_full": f"{internet_ws_url}?api_key=ov_live_<your_32_char_key>",
            "https_base": "https://api.ominivoice.com",
            "note": "Update this URL after deploying to AWS with your domain",
        },
    }


@router.get("/agents/{agent_id}/websocket-test-token")
async def get_websocket_test_token(
    agent: Agent = Depends(get_owned_agent),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Generate a one-time test token for WebSocket testing.

    This creates a short-lived token that can be used instead of the API key
    for quick testing without exposing the full API key.
    """
    import secrets
    from datetime import datetime, timezone, timedelta
    from jose import jwt
    from app.core.config import settings

    # Generate a one-time token valid for 1 hour
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=1)

    # Store the token hash in the API key record for validation
    # For now, we'll use a simple approach - encode the token in a JWT
    test_token = jwt.encode(
        {
            "sub": str(agent.id),
            "agent_id": str(agent.id),
            "type": "websocket_test",
            "exp": expires,
            "iat": datetime.now(timezone.utc),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    return {
        "test_token": test_token,
        "expires_at": expires.isoformat(),
        "usage": "Use as ?token=TEST_TOKEN instead of ?api_key=API_KEY",
        "note": "Valid for 1 hour, single use recommended",
    }