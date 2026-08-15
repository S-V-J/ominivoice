"""
Structured logging configuration for OminiVoice.
"""
import logging
import sys
from typing import Any

import structlog
from pythonjsonlogger import jsonlogger

from app.core.config import settings


def setup_logging() -> structlog.BoundLogger:
    """Configure structured logging for the application."""

    # Configure standard library logging
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    if settings.STRUCTURED_LOGGING:
        # JSON structured logging for production
        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s",
            timestamp=True,
        )
        handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        root_logger.handlers = [handler]
        root_logger.setLevel(log_level)
    else:
        # Human-readable logging for development
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            stream=sys.stdout,
        )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer() if settings.STRUCTURED_LOGGING else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a logger instance."""
    return structlog.get_logger(name)