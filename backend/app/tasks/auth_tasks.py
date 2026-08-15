"""
Authentication-related Celery tasks.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import delete

from app.core.celery_app import celery_app
from app.core.database import async_session_maker
from app.models import RefreshToken

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.auth_tasks.cleanup_expired_refresh_tokens")
async def cleanup_expired_refresh_tokens() -> int:
    """
    Delete expired and revoked refresh tokens from the database.
    Runs daily via Celery beat.

    Returns:
        Number of tokens deleted
    """
    async with async_session_maker() as session:
        # Delete expired tokens (older than expiry) and revoked tokens
        result = await session.execute(
            delete(RefreshToken).where(
                (RefreshToken.expires_at < datetime.now(timezone.utc))
                | (RefreshToken.revoked_at.is_not(None))
            )
        )
        await session.commit()
        deleted_count = result.rowcount
        logger.info(f"Cleaned up {deleted_count} expired/revoked refresh tokens")
        return deleted_count