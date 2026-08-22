"""
Celery tasks for sending emails.
"""
from celery import Celery
from app.core.celery_app import celery_app
from app.email.sender import send_email_task
from app.email.templates import (
    render_verification_email,
    render_password_reset_email,
    render_queue_failure_email,
    render_invoice_email,
)
from app.core.config import settings


@celery_app.task(name="app.tasks.email_tasks.send_verification_email", bind=True, max_retries=3)
def send_verification_email(self, email: str, verification_token: str, user_id: str = None):
    """Send email verification link."""
    import asyncio

    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
    html_content = render_verification_email(verification_url)

    result = asyncio.run(send_email_task(
        to=[email],
        subject="Verify Your OminiVoice Account",
        html_content=html_content,
        user_id=user_id,
    ))

    if result["status"] == "failed":
        raise self.retry(exc=Exception("Email send failed"), countdown=60)

    return result


@celery_app.task(name="app.tasks.email_tasks.send_password_reset_email", bind=True, max_retries=3)
def send_password_reset_email(self, email: str, reset_token: str, user_id: str = None):
    """Send password reset link."""
    import asyncio

    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    html_content = render_password_reset_email(reset_url)

    result = asyncio.run(send_email_task(
        to=[email],
        subject="Reset Your OminiVoice Password",
        html_content=html_content,
        user_id=user_id,
    ))

    if result["status"] == "failed":
        raise self.retry(exc=Exception("Email send failed"), countdown=60)

    return result


@celery_app.task(name="app.tasks.email_tasks.send_queue_failure_email", bind=True, max_retries=3)
def send_queue_failure_email(self, user_email: str, agent_name: str, failures: list, user_id: str = None):
    """Send queue failure notification."""
    import asyncio

    dashboard_url = f"{settings.FRONTEND_URL}/dashboard"
    html_content = render_queue_failure_email(agent_name, failures, dashboard_url)

    result = asyncio.run(send_email_task(
        to=[user_email],
        subject=f"Queue Failures for {agent_name}",
        html_content=html_content,
        user_id=user_id,
    ))

    if result["status"] == "failed":
        raise self.retry(exc=Exception("Email send failed"), countdown=60)

    return result


@celery_app.task(name="app.tasks.email_tasks.send_invoice_email", bind=True, max_retries=3)
def send_invoice_email(self, user_email: str, invoice_number: str, amount: str, plan: str, period: str, invoice_url: str, user_id: str = None):
    """Send invoice receipt email."""
    import asyncio

    html_content = render_invoice_email(invoice_number, amount, plan, period, invoice_url)

    result = asyncio.run(send_email_task(
        to=[user_email],
        subject=f"Invoice {invoice_number} - {amount}",
        html_content=html_content,
        user_id=user_id,
    ))

    if result["status"] == "failed":
        raise self.retry(exc=Exception("Email send failed"), countdown=60)

    return result


@celery_app.task(name="app.tasks.email_tasks.send_test_email")
def send_test_email(email: str):
    """Send a test email."""
    import asyncio
    from app.email.templates import render_verification_email

    html_content = render_verification_email(f"{settings.FRONTEND_URL}/test")

    return asyncio.run(send_email_task(
        to=[email],
        subject="OminiVoice Test Email",
        html_content=html_content,
    ))


@celery_app.task(name="app.tasks.email_tasks.send_daily_queue_failure_summary")
def send_daily_queue_failure_summary():
    """Send daily summary of queue failures to all users with failed entries."""
    import asyncio
    from sqlalchemy import select, func
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.core.database import async_session_maker
    from app.models import User, Agent, ColdCallQueueEntry, QueueEntryStatus
    from app.email.templates import render_queue_failure_email
    from app.email.sender import send_email_task

    async def _send_summaries():
        async with async_session_maker() as session:
            # Find all users with failed queue entries in the last 24 hours
            result = await session.execute(
                select(
                    User.email,
                    User.id,
                    Agent.name,
                    func.count(ColdCallQueueEntry.id).label('failure_count')
                )
                .select_from(ColdCallQueueEntry)
                .join(Agent, ColdCallQueueEntry.agent_id == Agent.id)
                .join(User, Agent.owner_id == User.id)
                .where(
                    ColdCallQueueEntry.status == QueueEntryStatus.FAILED,
                    ColdCallQueueEntry.last_attempt_at >= func.now() - func.interval('24 hours')
                )
                .group_by(User.email, User.id, Agent.name)
            )
            failures_by_user = result.all()

            for email, user_id, agent_name, failure_count in failures_by_user:
                # Get detailed failures for this user/agent
                detail_result = await session.execute(
                    select(ColdCallQueueEntry)
                    .where(
                        ColdCallQueueEntry.agent_id == Agent.id,
                        Agent.owner_id == user_id,
                        ColdCallQueueEntry.status == QueueEntryStatus.FAILED,
                        ColdCallQueueEntry.last_attempt_at >= func.now() - func.interval('24 hours')
                    )
                    .limit(20)
                )
                failures = detail_result.scalars().all()

                failure_details = [
                    {
                        "contact_name": f.contact_name,
                        "phone_number": f.phone_number,
                        "error": f.error_message or "Unknown error"
                    }
                    for f in failures
                ]

                html_content = render_queue_failure_email(
                    agent_name=agent_name,
                    failures=failure_details,
                    dashboard_url=f"{settings.FRONTEND_URL}/dashboard"
                )

                await send_email_task(
                    to=[email],
                    subject=f"Daily Queue Failure Summary: {failure_count} failures for {agent_name}",
                    html_content=html_content,
                )

    asyncio.run(_send_summaries())


@celery_app.task(name="app.tasks.email_tasks.send_test_email")
def send_test_email(email: str):
    """Send a test email."""
    import asyncio
    from app.email.templates import render_verification_email

    html_content = render_verification_email(f"{settings.FRONTEND_URL}/test")

    return asyncio.run(send_email_task(
        to=[email],
        subject="OminiVoice Test Email",
        html_content=html_content,
    ))