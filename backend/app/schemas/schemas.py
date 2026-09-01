"""
Pydantic schemas for API request/response validation.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# =============================================================================
# Enums
# =============================================================================

class AgentDirection(str, Enum):
    """Agent call direction."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class AgentStatus(str, Enum):
    """Agent lifecycle status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class CallStatus(str, Enum):
    """Call status."""
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no_answer"
    VOICEMAIL = "voicemail"
    QUEUED_FOR_EXTERNAL_DIALER = "queued_for_external_dialer"


class QueueEntryStatus(str, Enum):
    """Cold call queue entry status."""
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SubscriptionStatus(str, Enum):
    """Stripe subscription status."""
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"


class PlanTier(str, Enum):
    """Subscription plan tiers."""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class LLMPROVIDER(str, Enum):
    """LLM provider options."""
    NVIDIA_INTEGRATE = "nvidia_integrate"


class STTEngine(str, Enum):
    """STT engine options."""
    FASTER_WHISPER = "faster-whisper"


class TTSEngine(str, Enum):
    """TTS engine options."""
    KOKORO = "kokoro"
    PIPER = "piper"
    CHATTERBOX = "chatterbox"


class InterruptionSensitivity(str, Enum):
    """Interruption sensitivity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VoiceStack(str, Enum):
    """Voice technology stack selection."""
    STACK_A = "stack_a"  # Local: faster-whisper + Silero + Kokoro/Piper
    STACK_B = "stack_b"  # NVIDIA NIM: Riva ASR + Riva VAD + Chatterbox TTS


# =============================================================================
# Base schemas
# =============================================================================

class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class TimestampMixin(BaseModel):
    """Mixin for created_at/updated_at timestamps."""
    created_at: datetime
    updated_at: Optional[datetime] = None


# =============================================================================
# User schemas
# =============================================================================

class UserBase(BaseSchema):
    """Base user schema."""
    email: EmailStr = Field(..., description="User's email address")


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, max_length=128, description="User's password")


class UserLogin(BaseSchema):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserUpdate(BaseSchema):
    """Schema for user updates."""
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)


class UserResponse(UserBase, TimestampMixin):
    """Schema for user response."""
    id: str  # UUID as string
    plan: PlanTier = PlanTier.FREE
    is_active: bool = True
    stripe_customer_id: Optional[str] = None


class Token(BaseSchema):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenPayload(BaseSchema):
    """JWT token payload."""
    sub: str  # user_id (UUID as string)
    exp: int
    iat: int
    type: str  # "access" or "refresh"


class TokenRefresh(BaseSchema):
    """Schema for refresh token request."""
    refresh_token: Optional[str] = None


class EmailVerificationRequest(BaseSchema):
    """Schema for email verification request."""
    token: str = Field(..., description="Verification token from email")


class PasswordResetRequest(BaseSchema):
    """Schema for password reset request (forgot password)."""
    email: EmailStr = Field(..., description="User's email address")


class PasswordResetConfirm(BaseSchema):
    """Schema for password reset confirmation."""
    token: str = Field(..., description="Reset token from email")
    password: str = Field(..., min_length=8, max_length=128, description="New password")


# =============================================================================
# Agent schemas
# =============================================================================

class AgentPromptFields(BaseSchema):
    """All prompt fields for an agent (nullable for drafts)."""

    # Voice technology stack
    voice_stack: Optional[VoiceStack] = Field(VoiceStack.STACK_A, description="Voice technology stack")

    # Shared fields
    system_prompt: Optional[str] = Field(None, description="Core persona, tone, do's/don'ts")
    interruption_sensitivity: Optional[InterruptionSensitivity] = Field(
        InterruptionSensitivity.MEDIUM, description="VAD/turn detection sensitivity"
    )
    max_call_duration_s: Optional[int] = Field(300, ge=30, le=7200, description="Max call duration in seconds")
    silence_timeout_s: Optional[int] = Field(10, ge=1, le=60, description="Silence timeout in seconds")

    # Engine configuration (Stack A - Local)
    stt_engine: Optional[STTEngine] = Field(STTEngine.FASTER_WHISPER)
    tts_engine: Optional[TTSEngine] = Field(TTSEngine.KOKORO)
    tts_voice: Optional[str] = Field("af_heart", description="TTS voice ID")
    language: Optional[str] = Field("en-US", description="Language code")

    # Stack B (NVIDIA NIM) configuration
    # Chatterbox TTS voices: https://github.com/resemble-ai/chatterbox#voices
    chatterbox_voice: Optional[str] = Field(
        "Chatterbox-Multilingual.en-US.Female",
        description="Chatterbox voice (e.g., Chatterbox-Multilingual.en-US.Female, Chatterbox-Multilingual.es-US.Male)"
    )
    chatterbox_emotion_exaggeration: Optional[float] = Field(
        0.5, ge=0.0, le=1.0, description="Chatterbox emotion exaggeration (0.0-1.0, recommended 0.4-0.7)"
    )
    riva_asr_language: Optional[str] = Field("en-US", description="Riva ASR language code (BCP-47)")
    riva_vad_threshold: Optional[float] = Field(0.5, ge=0.0, le=1.0, description="Riva VAD threshold")

    # LLM configuration
    llm_provider: Optional[LLMPROVIDER] = Field(LLMPROVIDER.NVIDIA_INTEGRATE)
    llm_model: Optional[str] = Field("stepfun-ai/step-3.7-flash", description="LLM model identifier")

    # Outbound-specific fields
    opening_line: Optional[str] = Field(None, description="First thing said when callee picks up")
    objective_prompt: Optional[str] = Field(None, description="What the call is trying to achieve")
    objection_handling_prompt: Optional[str] = Field(None, description="How to respond to pushback")
    voicemail_prompt: Optional[str] = Field(None, description="What to say if voicemail detected")
    closing_prompt: Optional[str] = Field(None, description="How to end the call / next steps")
    escalation_rule: Optional[str] = Field(None, description="When to transfer to human")

    # Inbound-specific fields
    greeting_prompt: Optional[str] = Field(None, description="First thing said when call answered")
    qualification_prompt: Optional[str] = Field(None, description="Questions to understand caller intent")
    knowledge_prompt: Optional[str] = Field(None, description="FAQ / product info for grounding")
    fallback_prompt: Optional[str] = Field(None, description="What to say when doesn't know answer")
    handoff_prompt: Optional[str] = Field(None, description="How to hand off to human/ticket")


class AgentBase(BaseSchema):
    """Base agent schema."""
    name: str = Field(..., min_length=1, max_length=255)
    direction: AgentDirection
    status: AgentStatus = AgentStatus.DRAFT


class AgentCreate(AgentBase, AgentPromptFields):
    """Schema for creating an agent."""
    pass


class AgentUpdate(BaseSchema):
    """Schema for updating an agent (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    direction: Optional[AgentDirection] = None
    status: Optional[AgentStatus] = None

    # Voice stack
    voice_stack: Optional[VoiceStack] = None

    # Shared fields
    system_prompt: Optional[str] = None
    interruption_sensitivity: Optional[InterruptionSensitivity] = None
    max_call_duration_s: Optional[int] = Field(None, ge=30, le=7200)
    silence_timeout_s: Optional[int] = Field(None, ge=1, le=60)

    # Stack A (Local) engine configuration
    stt_engine: Optional[STTEngine] = None
    tts_engine: Optional[TTSEngine] = None
    tts_voice: Optional[str] = None
    language: Optional[str] = None

    # Stack B (NVIDIA NIM) configuration
    chatterbox_voice: Optional[str] = None
    chatterbox_emotion_exaggeration: Optional[float] = Field(None, ge=0.0, le=1.0)
    riva_asr_language: Optional[str] = None
    riva_vad_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)

    # LLM configuration
    llm_provider: Optional[LLMPROVIDER] = None
    llm_model: Optional[str] = None

    # Outbound-specific fields
    opening_line: Optional[str] = None
    objective_prompt: Optional[str] = None
    objection_handling_prompt: Optional[str] = None
    voicemail_prompt: Optional[str] = None
    closing_prompt: Optional[str] = None
    escalation_rule: Optional[str] = None

    # Inbound-specific fields
    greeting_prompt: Optional[str] = None
    qualification_prompt: Optional[str] = None
    knowledge_prompt: Optional[str] = None
    fallback_prompt: Optional[str] = None
    handoff_prompt: Optional[str] = None


class AgentPromptVersionResponse(BaseSchema):
    """Schema for prompt version history."""
    id: str
    agent_id: str
    field_name: str
    old_value: Optional[str]
    new_value: Optional[str]
    edited_at: datetime


class AgentCompletenessResponse(BaseSchema):
    """Schema for agent configuration completeness check."""
    agent_id: str
    direction: AgentDirection
    is_complete: bool
    missing_required_fields: List[str]
    field_status: Dict[str, bool]  # field_name -> is_filled
    completion_percentage: int


class AgentResponse(AgentBase, AgentPromptFields, TimestampMixin):
    """Schema for agent response."""
    id: str
    owner_id: str
    completeness_percentage: Optional[int] = None


class AgentListResponse(BaseSchema):
    """Schema for agent list item."""
    id: str
    name: str
    direction: AgentDirection
    status: AgentStatus
    completeness_percentage: int
    last_test_call_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# =============================================================================
# API Key schemas
# =============================================================================

class ApiKeyCreate(BaseSchema):
    """Schema for API key creation request."""
    pass  # No input needed, key is generated


class ApiKeyResponse(BaseSchema):
    """Schema for API key response (plaintext shown once)."""
    id: str
    agent_id: str
    key: str = Field(..., description="Plaintext API key (shown once)")
    key_prefix: str = Field(..., description="Key prefix for display (e.g., 'ov_live_••••ab12')")
    webhook_url: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None


class ApiKeyMaskedResponse(BaseSchema):
    """Schema for API key response (masked for list views)."""
    id: str
    agent_id: str
    key_prefix: str
    webhook_url: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None
    usage_today: int = 0


# =============================================================================
# Call Log schemas
# =============================================================================

class CallLogBase(BaseSchema):
    """Base call log schema."""
    agent_id: str
    direction: AgentDirection
    caller_ref: Optional[str] = Field(None, description="External call reference (e.g., Twilio SID)")


class CallLogCreate(CallLogBase):
    """Schema for creating a call log entry."""
    status: CallStatus = CallStatus.INITIATED
    transcript: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class CallLogUpdate(BaseSchema):
    """Schema for updating a call log entry."""
    status: Optional[CallStatus] = None
    transcript: Optional[List[Dict[str, Any]]] = None
    duration_s: Optional[int] = None
    ended_at: Optional[datetime] = None


class CallLogResponse(CallLogBase, TimestampMixin):
    """Schema for call log response."""
    id: str
    status: CallStatus
    transcript: List[Dict[str, Any]]
    duration_s: Optional[int] = None
    started_at: datetime
    ended_at: Optional[datetime] = None


# =============================================================================
# Cold Call Queue schemas
# =============================================================================

class ColdCallQueueEntryBase(BaseSchema):
    """Base cold call queue entry schema."""
    agent_id: str
    contact_name: str = Field(..., min_length=1, max_length=255)
    phone_number: str = Field(..., min_length=10, max_length=20)
    source: Optional[str] = Field("manual", description="Source of the lead")


class ColdCallQueueEntryCreate(ColdCallQueueEntryBase):
    """Schema for creating a queue entry (single)."""
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ColdCallQueueEntryBulkCreate(BaseSchema):
    """Schema for bulk creating queue entries."""
    entries: List[ColdCallQueueEntryCreate] = Field(..., min_length=1, max_length=10000)


class ColdCallQueueEntryUpdate(BaseSchema):
    """Schema for updating a queue entry."""
    status: Optional[QueueEntryStatus] = None
    contact_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone_number: Optional[str] = Field(None, min_length=10, max_length=20)
    payload: Optional[Dict[str, Any]] = None


class ColdCallQueueEntryResponse(ColdCallQueueEntryBase, TimestampMixin):
    """Schema for queue entry response."""
    id: str
    status: QueueEntryStatus
    payload: Dict[str, Any]
    call_log_id: Optional[str] = None


class ColdCallQueueStatsResponse(BaseSchema):
    """Schema for queue statistics."""
    agent_id: str
    total: int
    pending: int
    queued: int
    in_progress: int
    completed: int
    failed: int


# =============================================================================
# Subscription / Billing schemas
# =============================================================================

class SubscriptionBase(BaseSchema):
    """Base subscription schema."""
    user_id: str
    stripe_subscription_id: str
    plan: PlanTier
    status: SubscriptionStatus
    current_period_end: datetime


class SubscriptionResponse(SubscriptionBase, TimestampMixin):
    """Schema for subscription response."""
    id: str


class CheckoutSessionRequest(BaseSchema):
    """Schema for creating a Stripe checkout session."""
    price_id: str
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseSchema):
    """Schema for checkout session response."""
    session_id: str
    url: str
    client_secret: Optional[str] = None


class PortalSessionResponse(BaseSchema):
    """Schema for Stripe customer portal session."""
    url: str


class UsageStatsResponse(BaseSchema):
    """Schema for usage statistics."""
    plan: PlanTier
    period_start: datetime
    period_end: datetime
    agents_used: int
    agents_limit: Optional[int] = None
    minutes_used: int
    minutes_limit: Optional[int] = None
    queue_rows_used: int
    queue_rows_limit: Optional[int] = None


# =============================================================================
# Webhook / API Key Auth schemas
# =============================================================================

class WebhookPayload(BaseSchema):
    """Base schema for webhook payloads."""
    event_type: str
    timestamp: datetime
    agent_id: str
    data: Dict[str, Any]


class ColdCallWebhookPayload(WebhookPayload):
    """Schema for cold call webhook."""
    queue_entry_id: str
    contact_name: str
    phone_number: str
    payload: Dict[str, Any]


# =============================================================================
# Health check schemas
# =============================================================================

class HealthCheckResponse(BaseSchema):
    """Schema for health check response."""
    status: str = "healthy"
    version: str
    timestamp: datetime
    services: Dict[str, str]  # service_name -> status


# =============================================================================
# Error schemas
# =============================================================================

class ErrorResponse(BaseSchema):
    """Standard error response."""
    detail: str
    error_code: Optional[str] = None
    field: Optional[str] = None


class ValidationErrorResponse(BaseSchema):
    """Validation error response."""
    detail: List[Dict[str, Any]]


# =============================================================================
# Admin schemas
# =============================================================================

class AdminStatsResponse(BaseSchema):
    """Schema for platform-wide statistics."""
    total_users: int
    active_users: int
    total_agents: int
    total_calls_30d: int
    calls_per_minute: float
    queue_depth: int
    monthly_revenue: float


class AdminUserResponse(BaseSchema):
    """Schema for admin user view."""
    id: str
    email: str
    plan: PlanTier
    is_active: bool
    is_verified: bool
    created_at: datetime
    agent_count: int
    subscription_status: Optional[str] = None
    subscription_plan: Optional[PlanTier] = None


class AdminAgentResponse(BaseSchema):
    """Schema for admin agent view."""
    id: str
    name: str
    direction: AgentDirection
    status: AgentStatus
    owner_email: str
    owner_id: str
    created_at: datetime
    updated_at: datetime