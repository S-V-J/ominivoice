"""
Structured logging configuration using structlog.
"""
import logging
import sys
from typing import Any, Dict

import structlog


def setup_logging() -> structlog.stdlib.BoundLogger:
    """Configure structured logging for the application."""

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class StructuredLogger:
    """Wrapper for common structured logging patterns."""

    def __init__(self, logger: structlog.stdlib.BoundLogger = None):
        self.logger = logger or structlog.get_logger()

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: str = None,
        **kwargs,
    ):
        """Log an HTTP request."""
        self.logger.info(
            "http_request",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            user_id=user_id,
            **kwargs,
        )

    def log_call_event(
        self,
        event: str,
        agent_id: str = None,
        call_id: str = None,
        user_id: str = None,
        **kwargs,
    ):
        """Log a call-related event."""
        self.logger.info(
            "call_event",
            event=event,
            agent_id=agent_id,
            call_id=call_id,
            user_id=user_id,
            **kwargs,
        )

    def log_agent_event(
        self,
        event: str,
        agent_id: str = None,
        user_id: str = None,
        **kwargs,
    ):
        """Log an agent-related event."""
        self.logger.info(
            "agent_event",
            event=event,
            agent_id=agent_id,
            user_id=user_id,
            **kwargs,
        )

    def log_error(
        self,
        error: Exception,
        context: Dict[str, Any] = None,
        **kwargs,
    ):
        """Log an error with context."""
        self.logger.error(
            "error",
            error_type=type(error).__name__,
            error_message=str(error),
            context=context or {},
            **kwargs,
        )

    def log_security_event(
        self,
        event: str,
        user_id: str = None,
        ip_address: str = None,
        success: bool = True,
        **kwargs,
    ):
        """Log a security-related event."""
        self.logger.warning(
            "security_event",
            event=event,
            user_id=user_id,
            ip_address=ip_address,
            success=success,
            **kwargs,
        )

    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        **kwargs,
    ):
        """Log performance metrics."""
        self.logger.info(
            "performance",
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            **kwargs,
        )


# Global logger instance
logger = get_logger()
structured_logger = StructuredLogger(logger)