"""
Email rate limiting per user.
"""
import time
from typing import Optional
from collections import defaultdict
from dataclasses import dataclass, field
import asyncio

from app.core.config import settings


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""
    tokens: float
    last_refill: float
    capacity: int
    refill_rate: float  # tokens per second


class EmailRateLimiter:
    """Per-user email rate limiter using token bucket algorithm."""

    def __init__(self):
        self.buckets: dict[str, RateLimitBucket] = {}
        self.default_capacity = settings.EMAIL_RATE_LIMIT_PER_HOUR or 50
        self.default_refill_rate = self.default_capacity / 3600  # tokens per second
        self._lock = asyncio.Lock()

    async def check_limit(self, user_id: str, tokens: int = 1) -> tuple[bool, Optional[float]]:
        """
        Check if user can send email.

        Returns:
            (allowed, retry_after_seconds)
        """
        async with self._lock:
            bucket = self.buckets.get(user_id)
            now = time.time()

            if bucket is None:
                bucket = RateLimitBucket(
                    tokens=self.default_capacity,
                    last_refill=now,
                    capacity=self.default_capacity,
                    refill_rate=self.default_refill_rate,
                )
                self.buckets[user_id] = bucket

            # Refill tokens
            elapsed = now - bucket.last_refill
            bucket.tokens = min(bucket.capacity, bucket.tokens + elapsed * bucket.refill_rate)
            bucket.last_refill = now

            if bucket.tokens >= tokens:
                bucket.tokens -= tokens
                return True, None

            # Calculate wait time
            needed = tokens - bucket.tokens
            retry_after = needed / bucket.refill_rate
            return False, retry_after

    async def get_remaining(self, user_id: str) -> int:
        """Get remaining email quota for user."""
        async with self._lock:
            bucket = self.buckets.get(user_id)
            if bucket is None:
                return self.default_capacity

            now = time.time()
            elapsed = now - bucket.last_refill
            bucket.tokens = min(bucket.capacity, bucket.tokens + elapsed * bucket.refill_rate)
            return int(bucket.tokens)

    def reset_user(self, user_id: str) -> None:
        """Reset rate limit for user (e.g., on plan upgrade)."""
        if user_id in self.buckets:
            del self.buckets[user_id]


# Global rate limiter instance
_email_rate_limiter: Optional[EmailRateLimiter] = None


def get_email_rate_limiter() -> EmailRateLimiter:
    """Get global email rate limiter."""
    global _email_rate_limiter
    if _email_rate_limiter is None:
        _email_rate_limiter = EmailRateLimiter()
    return _email_rate_limiter