"""
Security utilities for JWT tokens and password hashing.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings


# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenPayload(BaseModel):
    """JWT token payload schema."""
    sub: str  # user_id
    exp: int  # expiration timestamp
    iat: int  # issued at timestamp
    type: str  # "access" or "refresh"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against its hash.

    Args:
        plain_password: The plain text password to verify
        hashed_password: The stored bcrypt hash

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: The plain text password to hash

    Returns:
        The bcrypt hash string
    """
    return pwd_context.hash(password)


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        subject: The user ID (sub claim)
        expires_delta: Optional custom expiration delta

    Returns:
        Encoded JWT access token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "type": "access",
    }

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(subject: str) -> str:
    """
    Create a JWT refresh token.

    Args:
        subject: The user ID (sub claim)

    Returns:
        Encoded JWT refresh token
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    to_encode = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "type": "refresh",
    }

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT token string

    Returns:
        Dict with decoded claims

    Raises:
        jwt.JWTError: If token is invalid or expired
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )
    return payload


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key and its hash.

    Returns:
        Tuple of (plaintext_key, key_hash)
        plaintext_key is shown once to user, key_hash is stored in DB
    """
    # Format: ov_live_<32 url-safe random chars>
    random_part = secrets.token_urlsafe(24)  # 32 chars after base64 encoding
    plaintext_key = f"ov_live_{random_part}"

    # Hash for storage (SHA-256)
    import hashlib
    key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()

    return plaintext_key, key_hash


def hash_api_key(key: str) -> str:
    """
    Hash an API key for storage/comparison.

    Args:
        key: The plaintext API key

    Returns:
        SHA-256 hex digest
    """
    import hashlib
    return hashlib.sha256(key.encode()).hexdigest()