"""
Email infrastructure for OminiVoice.
"""
from .templates import (
    render_verification_email,
    render_password_reset_email,
    render_queue_failure_email,
    render_invoice_email,
)
from .sender import send_email, send_email_background

__all__ = [
    "render_verification_email",
    "render_password_reset_email",
    "render_queue_failure_email",
    "render_invoice_email",
    "send_email",
    "send_email_background",
]