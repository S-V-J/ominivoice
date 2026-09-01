"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # =========================================================================
    # DATABASE
    # =========================================================================
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://ominivoice:ominivoice_dev@localhost:5432/ominivoice",
        description="PostgreSQL connection string with asyncpg driver",
    )

    # =========================================================================
    # REDIS
    # =========================================================================
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string for cache, sessions, and Celery broker",
    )

    # =========================================================================
    # AUTHENTICATION & SECURITY
    # =========================================================================
    JWT_SECRET: str = Field(
        default="your-super-secret-jwt-key-change-in-production-min-32-chars",
        description="JWT secret key for signing access/refresh tokens",
    )

    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT algorithm (HS256, RS256, etc.)",
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token expiration in minutes",
    )

    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        description="Refresh token expiration in days",
    )

    BCRYPT_ROUNDS: int = Field(
        default=12,
        description="Bcrypt rounds for password hashing",
    )

    # =========================================================================
    # STRIPE BILLING
    # =========================================================================
    STRIPE_SECRET_KEY: str = Field(
        default="sk_test_your_stripe_secret_key",
        description="Stripe secret key (test mode: sk_test_..., live: sk_live_...)",
    )

    STRIPE_PUBLISHABLE_KEY: str = Field(
        default="pk_test_your_stripe_publishable_key",
        description="Stripe publishable key (test: pk_test_..., live: pk_live_...)",
    )

    STRIPE_WEBHOOK_SECRET: str = Field(
        default="whsec_your_webhook_signing_secret",
        description="Stripe webhook secret for verifying webhook signatures",
    )

    STRIPE_PRICE_ID_STARTER: str = Field(
        default="price_starter_monthly",
        description="Stripe price ID for starter plan",
    )

    STRIPE_PRICE_ID_PRO: str = Field(
        default="price_pro_monthly",
        description="Stripe price ID for pro plan",
    )

    STRIPE_PRICE_ID_ENTERPRISE: str = Field(
        default="price_enterprise_monthly",
        description="Stripe price ID for enterprise plan",
    )

    # =========================================================================
    # NVIDIA API (Hosted LLM Provider) - Used by BOTH Stack A and Stack B
    # =========================================================================
    NVIDIA_API_KEY: str = Field(
        default="",
        description="NVIDIA API key for integrate.api.nvidia.com",
    )

    NVIDIA_BASE_URL: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        description="NVIDIA base URL",
    )

    NVIDIA_DEFAULT_MODEL: str = Field(
        default="stepfun-ai/step-3.7-flash",
        description="Default model to use (can be overridden per-agent)",
    )

    # =========================================================================
    # STACK B: NVIDIA NIM Services (Riva ASR, Chatterbox TTS)
    # =========================================================================
    # Riva ASR NIM
    RIVA_ASR_GRPC_ENDPOINT: str = Field(
        default="voice-riva-asr:50051",
        description="Riva ASR NIM gRPC endpoint",
    )

    RIVA_ASR_LANGUAGE: str = Field(
        default="en-US",
        description="Riva ASR language code (BCP-47)",
    )

    RIVA_ASR_USE_SSL: bool = Field(
        default=False,
        description="Use SSL for Riva ASR gRPC",
    )

    RIVA_ASR_FUNCTION_ID: Optional[str] = Field(
        default=None,
        description="Riva ASR NIM function ID (for NVCF)",
    )

    # Chatterbox TTS NIM
    CHATTERBOX_GRPC_ENDPOINT: str = Field(
        default="voice-chatterbox:50051",
        description="Chatterbox TTS NIM gRPC endpoint",
    )

    CHATTERBOX_LANGUAGE: str = Field(
        default="en-US",
        description="Chatterbox TTS language code (BCP-47)",
    )

    CHATTERBOX_VOICE: str = Field(
        default="Chatterbox-Multilingual.en-US.Female",
        description="Chatterbox default voice",
    )

    CHATTERBOX_EMOTION_EXAGGERATION: float = Field(
        default=0.5,
        description="Chatterbox emotion exaggeration (0.0-1.0, recommended 0.4-0.7)",
    )

    CHATTERBOX_USE_SSL: bool = Field(
        default=False,
        description="Use SSL for Chatterbox gRPC",
    )

    CHATTERBOX_FUNCTION_ID: Optional[str] = Field(
        default=None,
        description="Chatterbox NIM function ID (for NVCF)",
    )

    # Riva VAD (uses same endpoint as Riva ASR)
    RIVA_VAD_THRESHOLD: float = Field(
        default=0.5,
        description="Riva VAD threshold (0.0-1.0)",
    )

    RIVA_VAD_FUNCTION_ID: Optional[str] = Field(
        default=None,
        description="Riva VAD NIM function ID (for NVCF)",
    )

    # NGC API Key for NIM authentication
    NGC_API_KEY: str = Field(
        default="",
        description="NGC API key for NIM container authentication",
    )

    # =========================================================================
    # STT (Speech-to-Text)
    # =========================================================================
    STT_ENGINE: str = Field(
        default="faster-whisper",
        description="STT engine: faster-whisper, whisper",
    )

    STT_MODEL_SIZE: str = Field(
        default="base",
        description="faster-whisper model size: tiny, base, small, medium, large-v3",
    )

    STT_DEVICE: str = Field(
        default="cpu",
        description="Device: cpu, cuda",
    )

    STT_COMPUTE_TYPE: str = Field(
        default="int8",
        description="Compute type: int8, int8_float16, float16, float32",
    )

    # =========================================================================
    # TTS (Text-to-Speech)
    # =========================================================================
    TTS_ENGINE: str = Field(
        default="kokoro",
        description="TTS engine: kokoro, piper",
    )

    KOKORO_MODEL_PATH: str = Field(
        default="/models/kokoro-v1.0.onnx",
        description="Path to Kokoro ONNX model",
    )

    KOKORO_VOICES_PATH: str = Field(
        default="/models/voices",
        description="Path to Kokoro voices directory",
    )

    KOKORO_DEFAULT_VOICE: str = Field(
        default="af_heart",
        description="Default Kokoro voice",
    )

    PIPER_MODEL_PATH: str = Field(
        default="/models/piper/en_US-lessac-medium.onnx",
        description="Path to Piper ONNX model",
    )

    PIPER_DEFAULT_VOICE: str = Field(
        default="en_US-lessac-medium",
        description="Default Piper voice",
    )

    # =========================================================================
    # VAD (Voice Activity Detection)
    # =========================================================================
    VAD_ENGINE: str = Field(
        default="silero",
        description="VAD engine: silero",
    )

    VAD_THRESHOLD: float = Field(
        default=0.5,
        description="Silero VAD threshold (0.0-1.0, higher = more sensitive)",
    )

    # =========================================================================
    # VOICE ENGINE
    # =========================================================================
    VOICE_ENGINE_HOST: str = Field(
        default="0.0.0.0",
        description="Voice engine host for internal communication",
    )

    VOICE_ENGINE_PORT: int = Field(
        default=8080,
        description="Voice engine port for internal communication",
    )

    FASTRTC_HOST: str = Field(
        default="0.0.0.0",
        description="FastRTC host for simulated calls",
    )

    FASTRTC_PORT: int = Field(
        default=7860,
        description="FastRTC port for simulated calls",
    )

    # =========================================================================
    # API SETTINGS
    # =========================================================================
    API_HOST: str = Field(
        default="0.0.0.0",
        description="API host",
    )

    API_PORT: int = Field(
        default=8000,
        description="API port",
    )

    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="CORS allowed origins",
    )

    API_RATE_LIMIT: int = Field(
        default=60,
        description="Rate limiting (requests per minute per API key)",
    )

    # =========================================================================
    # FRONTEND
    # =========================================================================
    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        description="Frontend URL (for email links, redirects, etc.)",
    )

    # =========================================================================
    # CELERY / BACKGROUND WORKERS
    # =========================================================================
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/1",
        description="Celery broker URL (uses Redis)",
    )

    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/2",
        description="Celery result backend",
    )

    CELERY_WORKER_CONCURRENCY: int = Field(
        default=4,
        description="Celery worker concurrency",
    )

    ENVIRONMENT: str = Field(
        default="development",
        description="Environment: development, staging, production",
    )

    # =========================================================================
    # LOGGING & MONITORING
    # =========================================================================
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR",
    )

    STRUCTURED_LOGGING: bool = Field(
        default=True,
        description="Enable structured JSON logging",
    )

    SENTRY_DSN: Optional[str] = Field(
        default=None,
        description="Sentry DSN (optional)",
    )

    # =========================================================================
    # EMAIL (Optional - for notifications, password reset)
    # =========================================================================
    SMTP_HOST: Optional[str] = Field(
        default=None,
        description="SMTP host",
    )

    SMTP_PORT: int = Field(
        default=587,
        description="SMTP port",
    )

    SMTP_USER: Optional[str] = Field(
        default=None,
        description="SMTP user",
    )

    SMTP_PASSWORD: Optional[str] = Field(
        default=None,
        description="SMTP password",
    )

    SMTP_FROM: str = Field(
        default="noreply@ominivoice.com",
        description="SMTP from address",
    )

    EMAIL_RATE_LIMIT_PER_HOUR: int = Field(
        default=50,
        description="Maximum emails per user per hour",
    )

    # Admin IP restriction (comma-separated CIDR blocks, e.g., "192.168.1.0/24,10.0.0.0/8")
    ADMIN_ALLOWED_IPS: Optional[str] = Field(
        default=None,
        description="Comma-separated CIDR blocks for admin access restriction",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()