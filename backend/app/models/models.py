"""
SQLAlchemy models for OminiVoice multi-tenant voice agent platform.
"""
import enum
from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    Column, String, Text, DateTime, Enum, ForeignKey, Index, Boolean,
    Integer, BigInteger, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class UserPlan(str, enum.Enum):
    """Subscription plan tiers."""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class AgentDirection(str, enum.Enum):
    """Agent call direction."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class AgentStatus(str, enum.Enum):
    """Agent status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class VoiceStack(str, enum.Enum):
    """Voice technology stack selection."""
    STACK_A = "stack_a"  # Local: faster-whisper + Silero + Kokoro/Piper
    STACK_B = "stack_b"  # NVIDIA NIM: Riva ASR + Riva VAD + Chatterbox TTS

    @classmethod
    def from_string(cls, value: str) -> "VoiceStack":
        """Create VoiceStack from string (case-insensitive)."""
        value_lower = value.lower()
        if value_lower in ("stack_a", "a"):
            return cls.STACK_A
        elif value_lower in ("stack_b", "b"):
            return cls.STACK_B
        raise ValueError(f"Invalid voice stack: {value}")


class CallDirection(str, enum.Enum):
    """Call direction for logs."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, enum.Enum):
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


class QueueEntryStatus(str, enum.Enum):
    """Cold call queue entry status."""
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SubscriptionStatus(str, enum.Enum):
    """Stripe subscription status."""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAUSED = "paused"


class UserRole(str, enum.Enum):
    """User role within an account."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Account(Base):
    """Account/Organization model for team collaboration."""
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    settings = Column(JSONB, nullable=True)  # Account-level settings
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_accounts")
    members = relationship("AccountMember", back_populates="account", cascade="all, delete-orphan", lazy="dynamic")
    agents = relationship("Agent", back_populates="account", lazy="dynamic")
    api_keys = relationship("ApiKey", back_populates="account", lazy="dynamic")

    def __repr__(self):
        return f"<Account(id={self.id}, name={self.name}, owner_id={self.owner_id})>"


class AccountMember(Base):
    """Account membership with role."""
    __tablename__ = "account_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Enum(UserRole), default=UserRole.MEMBER, nullable=False)
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    invited_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    account = relationship("Account", back_populates="members")
    user = relationship("User", foreign_keys=[user_id], back_populates="account_memberships")
    inviter = relationship("User", foreign_keys=[invited_by])

    __table_args__ = (
        UniqueConstraint("account_id", "user_id", name="uq_account_user"),
        Index("ix_account_members_account_role", "account_id", "role"),
    )

    def __repr__(self):
        return f"<AccountMember(account_id={self.account_id}, user_id={self.user_id}, role={self.role})>"


class AccountInvitation(Base):
    """Pending account invitation."""
    __tablename__ = "account_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    role = Column(Enum(UserRole), default=UserRole.MEMBER, nullable=False)
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    token = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_invitations_account_email", "account_id", "email"),
    )

    def __repr__(self):
        return f"<AccountInvitation(account_id={self.account_id}, email={self.email}, role={self.role})>"


class User(Base):
    """User model - multi-tenant owner."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    plan = Column(Enum(UserPlan), default=UserPlan.FREE, nullable=False)
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    owned_accounts = relationship("Account", foreign_keys="Account.owner_id", back_populates="owner", cascade="all, delete-orphan", lazy="dynamic")
    account_memberships = relationship("AccountMember", foreign_keys="AccountMember.user_id", back_populates="user", cascade="all, delete-orphan", lazy="dynamic")
    agents = relationship("Agent", back_populates="owner", cascade="all, delete-orphan", lazy="dynamic")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan", lazy="dynamic")
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan", lazy="dynamic")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, plan={self.plan})>"


class Agent(Base):
    """Voice agent configuration."""
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    direction = Column(Enum(AgentDirection), nullable=False)
    status = Column(Enum(AgentStatus), default=AgentStatus.DRAFT, nullable=False)

    # Voice technology stack
    voice_stack = Column(Enum(VoiceStack), default=VoiceStack.STACK_A, nullable=False)

    # Engine configuration (Stack A - Local)
    stt_engine = Column(String(50), default="faster-whisper", nullable=False)
    tts_engine = Column(String(50), default="kokoro", nullable=False)
    tts_voice = Column(String(100), default="af_heart", nullable=False)
    language = Column(String(10), default="en", nullable=False)

    # Stack B (NVIDIA NIM) configuration
    chatterbox_voice = Column(String(100), default="Chatterbox-Multilingual.en-US.Female", nullable=False)
    chatterbox_emotion_exaggeration = Column(Integer, default=50, nullable=False)  # 0-100, stored as integer percentage
    riva_asr_language = Column(String(10), default="en-US", nullable=False)
    riva_vad_threshold = Column(Integer, default=50, nullable=False)  # 0-100, stored as integer percentage

    # LLM configuration
    llm_provider = Column(String(50), default="ollama", nullable=False)  # ollama, nvidia
    llm_model = Column(String(100), default="qwen3:4b", nullable=False)

    # Prompt configuration (outbound)
    system_prompt = Column(Text, nullable=True)
    opening_line = Column(Text, nullable=True)
    objective_prompt = Column(Text, nullable=True)
    objection_handling_prompt = Column(Text, nullable=True)
    voicemail_prompt = Column(Text, nullable=True)
    closing_prompt = Column(Text, nullable=True)
    escalation_rule = Column(Text, nullable=True)

    # Prompt configuration (inbound)
    greeting_prompt = Column(Text, nullable=True)
    qualification_prompt = Column(Text, nullable=True)
    knowledge_prompt = Column(Text, nullable=True)
    fallback_prompt = Column(Text, nullable=True)
    handoff_prompt = Column(Text, nullable=True)

    # Behavior configuration
    interruption_sensitivity = Column(String(20), default="medium", nullable=False)  # low, medium, high
    max_call_duration_s = Column(Integer, default=300, nullable=False)  # 5 minutes default
    silence_timeout_s = Column(Integer, default=30, nullable=False)

    # Limits
    daily_call_cap = Column(Integer, default=100, nullable=False)
    rate_limit_per_minute = Column(Integer, default=30, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    owner = relationship("User", back_populates="agents")
    account = relationship("Account", back_populates="agents")
    api_keys = relationship("ApiKey", back_populates="agent", cascade="all, delete-orphan", lazy="dynamic")
    call_logs = relationship("CallLog", back_populates="agent", lazy="dynamic")
    queue_entries = relationship("ColdCallQueueEntry", back_populates="agent", lazy="dynamic")
    prompt_versions = relationship("AgentPromptVersion", back_populates="agent", cascade="all, delete-orphan", lazy="dynamic")

    __table_args__ = (
        Index("ix_agents_owner_status", "owner_id", "status"),
        Index("ix_agents_owner_direction", "owner_id", "direction"),
        Index("ix_agents_account_status", "account_id", "status"),
    )

    def __repr__(self):
        return f"<Agent(id={self.id}, name={self.name}, direction={self.direction}, status={self.status})>"


class AgentPromptVersion(Base):
    """Version history for agent prompt fields."""
    __tablename__ = "agent_prompt_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    edited_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    agent = relationship("Agent", back_populates="prompt_versions")

    def __repr__(self):
        return f"<AgentPromptVersion(agent_id={self.agent_id}, field={self.field_name})>"


class ApiKey(Base):
    """API key for agent webhook/authentication."""
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True, index=True)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hex
    key_prefix = Column(String(20), nullable=False)  # e.g., "ov_live_abc123"
    webhook_url = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("Agent", back_populates="api_keys")
    user = relationship("User", back_populates="api_keys")
    account = relationship("Account", back_populates="api_keys")

    def __repr__(self):
        return f"<ApiKey(id={self.id}, prefix={self.key_prefix}, active={self.is_active})>"


class CallLog(Base):
    """Call log with transcript and metadata."""
    __tablename__ = "call_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    direction = Column(Enum(CallDirection), nullable=False)
    caller_ref = Column(String(255), nullable=True)  # phone number or session ID
    transcript = Column(JSONB, nullable=True)  # Full turn-by-turn transcript
    duration_s = Column(Integer, default=0, nullable=False)
    status = Column(Enum(CallStatus), default=CallStatus.INITIATED, nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    call_metadata = Column("metadata", JSONB, nullable=True)  # Additional metadata (interruption count, etc.)
    audio_url = Column(String(500), nullable=True)  # S3/MinIO URL for recorded audio

    agent = relationship("Agent", back_populates="call_logs")

    __table_args__ = (
        Index("ix_call_logs_agent_started", "agent_id", "started_at"),
        Index("ix_call_logs_status", "status"),
    )

    def __repr__(self):
        return f"<CallLog(id={self.id}, agent_id={self.agent_id}, status={self.status}, duration={self.duration_s}s)>"


class ColdCallQueueEntry(Base):
    """Cold call queue entry for outbound dialing."""
    __tablename__ = "cold_call_queue_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_name = Column(String(255), nullable=False)
    phone_number = Column(String(50), nullable=False, index=True)
    source = Column(String(100), nullable=True)  # csv_upload, api, manual
    status = Column(Enum(QueueEntryStatus), default=QueueEntryStatus.PENDING, nullable=False)
    payload = Column(JSONB, nullable=True)  # Extra columns from CSV
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    call_log_id = Column(UUID(as_uuid=True), ForeignKey("call_logs.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    agent = relationship("Agent", back_populates="queue_entries")
    call_log = relationship("CallLog")

    __table_args__ = (
        UniqueConstraint("agent_id", "phone_number", name="uq_agent_phone"),
        Index("ix_queue_agent_status", "agent_id", "status"),
        Index("ix_queue_scheduled", "scheduled_at"),
    )

    def __repr__(self):
        return f"<ColdCallQueueEntry(id={self.id}, agent_id={self.agent_id}, phone={self.phone_number}, status={self.status})>"


class Subscription(Base):
    """User subscription via Stripe."""
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    stripe_subscription_id = Column(String(255), nullable=True, unique=True, index=True)
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    plan = Column(Enum(UserPlan), default=UserPlan.FREE, nullable=False)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.INCOMPLETE, nullable=False)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    trial_start = Column(DateTime(timezone=True), nullable=True)
    trial_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription(user_id={self.user_id}, plan={self.plan}, status={self.status})>"


class RefreshToken(Base):
    """Refresh token storage for JWT rotation."""
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hex
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)

    __table_args__ = (
        Index("ix_refresh_tokens_user_expires", "user_id", "expires_at"),
    )

    def __repr__(self):
        return f"<RefreshToken(user_id={self.user_id}, expires={self.expires_at})>"


class AuditLog(Base):
    """Audit log for admin actions and security events."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False)  # e.g., "user.create", "agent.update", "subscription.cancel"
    resource_type = Column(String(50), nullable=True)  # e.g., "user", "agent", "subscription"
    resource_id = Column(String(100), nullable=True)
    old_values = Column(JSONB, nullable=True)
    new_values = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_account_created", "account_id", "created_at"),
        Index("ix_audit_logs_action_created", "action", "created_at"),
    )

    def __repr__(self):
        return f"<AuditLog(action={self.action}, user_id={self.user_id}, resource={self.resource_type}:{self.resource_id})>"