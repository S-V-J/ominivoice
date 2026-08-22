"""
Celery application configuration for background tasks.
"""
import os
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "ominivoice",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.queue_tasks",
        "app.tasks.billing_tasks",
        "app.tasks.email_tasks",
        "app.tasks.auth_tasks",
    ],
)

# Override broker URL from environment variable at runtime to ensure Docker networking works
celery_app.conf.broker_url = os.environ.get("CELERY_BROKER_URL", settings.CELERY_BROKER_URL)
celery_app.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", settings.CELERY_RESULT_BACKEND)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    result_expires=86400,  # 24 hours
    # Beat schedule for periodic tasks
    beat_schedule={
        "process-cold-call-queue": {
            "task": "app.tasks.queue_tasks.process_cold_call_queue",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
        },
        "cleanup-expired-tokens": {
            "task": "app.tasks.auth_tasks.cleanup_expired_refresh_tokens",
            "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
        },
        "sync-stripe-subscriptions": {
            "task": "app.tasks.billing_tasks.sync_stripe_subscriptions",
            "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
        },
        # Email tasks
        "daily-queue-failure-summary": {
            "task": "app.tasks.email_tasks.send_daily_queue_failure_summary",
            "schedule": crontab(hour=9, minute=0),  # Daily at 9 AM
        },
    },
)

# Configure logging for Celery
celery_app.log.setup(loglevel="INFO")

if __name__ == "__main__":
    celery_app.start()