"""
Security utilities for OminiVoice.
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from passlib.context import CryptContext
from jose import jwt, JWTError

from app.core.config import settings


# Password hashing
# Use bcrypt with SHA-256 pre-hashing to avoid 72-byte limit
pwd_context = CryptContext(
    schemes=["bcrypt_sha256"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt with SHA-256 pre-hashing."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# JWT token handling
ALGORITHM = settings.JWT_ALGORITHM
SECRET_KEY = settings.JWT_SECRET
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"sub": subject, "exp": expire, "type": "access", "iat": datetime.utcnow()}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {"sub": subject, "exp": expire, "type": "refresh", "iat": datetime.utcnow()}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise


# API Key generation
def generate_api_key() -> tuple[str, str]:
    """
    Generate a secure API key.

    Returns:
        tuple: (plaintext_key, key_hash)
    """
    # Generate 32 bytes = 256 bits of entropy
    random_bytes = secrets.token_bytes(32)
    plaintext_key = "ov_live_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
    return plaintext_key, key_hash


def hash_api_key(key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


# Input validation
MAX_CSV_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_CSV_MIME_TYPES = ["text/csv", "application/csv", "text/plain"]


def validate_csv_upload(file_size: int, content_type: str) -> Optional[str]:
    """
    Validate CSV upload.

    Returns:
        Error message if invalid, None if valid
    """
    if file_size > MAX_CSV_SIZE:
        return f"File size exceeds maximum of {MAX_CSV_SIZE // (1024*1024)} MB"

    if content_type not in ALLOWED_CSV_MIME_TYPES:
        return f"Invalid file type. Expected CSV, got {content_type}"

    return None


# Rate limiting keys
def get_rate_limit_key(request, prefix: str = "api") -> str:
    """Generate rate limit key from request."""
    client_ip = request.client.host if request.client else "unknown"
    return f"{prefix}:{client_ip}"


# CORS origins validation
def validate_cors_origin(origin: str, allowed_origins: list) -> bool:
    """Validate that origin is in allowed list."""
    if not allowed_origins or "*" in allowed_origins:
        return True
    return origin in allowed_origins


# Email verification tokens (separate from JWT for security)
EMAIL_TOKEN_EXPIRE_HOURS = 24


def generate_email_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a secure email verification/reset token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=EMAIL_TOKEN_EXPIRE_HOURS)

    # Use a separate secret for email tokens
    email_secret = settings.JWT_SECRET + "_email"
    to_encode = {"sub": subject, "exp": expire, "type": "email", "iat": datetime.utcnow()}
    return jwt.encode(to_encode, email_secret, algorithm=ALGORITHM)


def verify_email_token(token: str) -> Optional[str]:
    """Verify an email token and return the subject (user_id)."""
    try:
        email_secret = settings.JWT_SECRET + "_email"
        payload = jwt.decode(token, settings.JWT_SECRET + "_email", algorithms=[ALGORITHM])
        if payload.get("type") != "email":
            return None
        return payload.get("sub")
    except JWTError:
        return None


# Security headers
SECURITY_HEADERS = {
    "X-Frame-Options": "SAMEORIGIN",
    "X-Content-Type-Options": "nosniff",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "microphone=(), camera=(), geolocation=()",
}

# Content Security Policy for production
CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' wss: https:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)