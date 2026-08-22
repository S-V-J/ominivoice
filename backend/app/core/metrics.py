"""
Prometheus metrics for OminiVoice.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import time
from typing import Callable
from functools import wraps

# HTTP Request Metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Auth Metrics
auth_login_attempts = Counter(
    "auth_login_attempts_total",
    "Total login attempts",
    ["status"],  # success, failure, rate_limited
)

auth_token_refreshes = Counter(
    "auth_token_refreshes_total",
    "Total token refresh attempts",
    ["status"],  # success, failure
)

# Agent Metrics
agent_creations = Counter(
    "agent_creations_total",
    "Total agents created",
    ["direction"],  # inbound, outbound
)

agent_updates = Counter(
    "agent_updates_total",
    "Total agent updates",
)

agent_deletions = Counter(
    "agent_deletions_total",
    "Total agents deleted",
)

# API Key Metrics
api_key_generations = Counter(
    "api_key_generations_total",
    "Total API keys generated",
)

api_key_revocations = Counter(
    "api_key_revocations_total",
    "Total API keys revoked",
)

# Call Metrics
call_sessions_active = Gauge(
    "call_sessions_active",
    "Number of active call sessions",
)

call_duration_seconds = Histogram(
    "call_duration_seconds",
    "Call duration in seconds",
    ["direction", "status"],
    buckets=[10, 30, 60, 120, 300, 600, 1800, 3600],
)

call_interruptions = Counter(
    "call_interruptions_total",
    "Total call interruptions (barge-in events)",
    ["agent_id"],
)

stt_latency_seconds = Histogram(
    "stt_latency_seconds",
    "STT processing latency in seconds",
    ["engine"],  # faster-whisper, riva-asr
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

tts_latency_seconds = Histogram(
    "tts_latency_seconds",
    "TTS processing latency in seconds",
    ["engine"],  # kokoro, piper, chatterbox
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

llm_latency_seconds = Histogram(
    "llm_latency_seconds",
    "LLM processing latency in seconds",
    ["provider"],  # nvidia_integrate
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# Queue Metrics
queue_entries_created = Counter(
    "queue_entries_created_total",
    "Total queue entries created",
    ["source"],  # csv_upload, api, manual
)

queue_entries_processed = Counter(
    "queue_entries_processed_total",
    "Total queue entries processed",
    ["status"],  # queued, completed, failed
)

queue_daily_cap_hits = Counter(
    "queue_daily_cap_hits_total",
    "Times daily call cap was reached",
    ["agent_id"],
)

# Billing Metrics
stripe_checkout_sessions = Counter(
    "stripe_checkout_sessions_total",
    "Total Stripe checkout sessions created",
    ["plan"],  # starter, pro, enterprise
)

stripe_webhook_events = Counter(
    "stripe_webhook_events_total",
    "Total Stripe webhook events received",
    ["event_type", "status"],  # success, failure
)

# Database Metrics
db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],  # select, insert, update, delete
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

db_connections_active = Gauge(
    "db_connections_active",
    "Active database connections",
)

# Redis Metrics
redis_operations_total = Counter(
    "redis_operations_total",
    "Total Redis operations",
    ["operation", "status"],  # get, set, delete / success, failure
)

redis_latency_seconds = Histogram(
    "redis_latency_seconds",
    "Redis operation latency in seconds",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
)

# Celery Metrics
celery_tasks_total = Counter(
    "celery_tasks_total",
    "Total Celery tasks executed",
    ["task_name", "status"],  # success, failure, retry
)

celery_task_duration_seconds = Histogram(
    "celery_task_duration_seconds",
    "Celery task duration in seconds",
    ["task_name"],
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600],
)

celery_queue_length = Gauge(
    "celery_queue_length",
    "Number of tasks in Celery queue",
    ["queue_name"],
)


def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


class MetricsMiddleware:
    """ASGI middleware for automatic HTTP metrics collection."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")

        # Track request
        http_requests_total.labels(method=method, endpoint=path, status_code="0").inc()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                duration = time.time() - start_time
                http_requests_total.labels(
                    method=method, endpoint=path, status_code=str(status_code)
                ).inc()
                http_request_duration_seconds.labels(
                    method=method, endpoint=path
                ).observe(duration)

            await send(message)

        await self.app(scope, receive, send_wrapper)


def track_time(metric: Histogram, labels: dict = None):
    """Decorator to track execution time of a function."""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                metric.labels(**labels).observe(duration) if labels else metric.observe(duration)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                metric.labels(**labels).observe(duration) if labels else metric.observe(duration)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator