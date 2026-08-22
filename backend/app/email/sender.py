"""
Email sender using aiosmtplib with background task support and rate limiting.
"""
import asyncio
import logging
from typing import Optional, List
from email.message import EmailMessage

import aiosmtplib
from pydantic import EmailStr

from app.core.config import settings
from app.email.rate_limiter import get_email_rate_limiter

logger = logging.getLogger(__name__)


class EmailSender:
    """Async email sender with connection pooling and rate limiting."""

    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM
        self.use_tls = settings.SMTP_PORT == 465  # Implicit TLS on 465
        self._client: Optional[aiosmtplib.SMTP] = None
        self.rate_limiter = get_email_rate_limiter()

    async def _get_client(self) -> aiosmtplib.SMTP:
        """Get or create SMTP client."""
        if self._client is None:
            self._client = aiosmtplib.SMTP(
                hostname=self.host,
                port=self.port,
                use_tls=self.use_tls,
                start_tls=not self.use_tls,  # STARTTLS on 587
                timeout=30,
            )
            await self._client.connect()
            if self.user and self.password:
                await self._client.login(self.user, self.password)
        return self._client

    async def send(
        self,
        to: List[EmailStr],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Send an email with rate limiting.

        Args:
            to: List of recipient email addresses
            subject: Email subject
            html_content: HTML body
            text_content: Plain text body (optional, auto-generated from HTML if not provided)
            user_id: User ID for rate limiting (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        # Check rate limit if user_id provided
        if user_id:
            allowed, retry_after = await self.rate_limiter.check_limit(user_id)
            if not allowed:
                logger.warning(f"Rate limit exceeded for user {user_id}, retry after {retry_after:.0f}s")
                return False

        if not self.host:
            logger.warning("SMTP not configured, logging email instead")
            logger.info(f"EMAIL TO: {to}, SUBJECT: {subject}")
            logger.debug(f"HTML: {html_content[:200]}...")
            return True

        try:
            client = await self._get_client()

            msg = EmailMessage()
            msg["From"] = self.from_email
            msg["To"] = ", ".join(to)
            msg["Subject"] = subject

            if text_content:
                msg.set_content(text_content)
            msg.add_alternative(html_content, subtype="html")

            await client.send_message(msg)
            logger.info(f"Email sent to {to}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False

    async def close(self):
        """Close SMTP connection."""
        if self._client:
            try:
                await self._client.quit()
            except Exception:
                pass
            self._client = None


# Global sender instance
_sender: Optional[EmailSender] = None


def get_sender() -> EmailSender:
    """Get or create global email sender."""
    global _sender
    if _sender is None:
        _sender = EmailSender()
    return _sender


async def send_email(
    to: List[EmailStr],
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> bool:
    """Send email using global sender."""
    sender = get_sender()
    return await sender.send(to, subject, html_content, text_content)


async def send_email_background(
    to: List[EmailStr],
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> None:
    """Send email in background (fire and forget)."""
    asyncio.create_task(send_email(to, subject, html_content, text_content))


# Celery task for sending emails
async def send_email_task(
    to: List[str],
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
    user_id: Optional[str] = None,
    max_retries: int = 3,
) -> dict:
    """Celery task to send email with retry logic and rate limiting."""
    for attempt in range(max_retries):
        try:
            success = await send_email(to, subject, html_content, text_content, user_id)
            if success:
                return {"status": "sent", "attempts": attempt + 1}
        except Exception as e:
            logger.warning(f"Email send attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

    logger.error(f"Failed to send email to {to} after {max_retries} attempts")
    return {"status": "failed", "attempts": max_retries}