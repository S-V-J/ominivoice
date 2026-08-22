"""initial_schema

Revision ID: 947f600fb21d
Revises: 062a9df6074b
Create Date: 2026-08-15 06:45:54.554638

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '947f600fb21d'
down_revision: Union[str, None] = '062a9df6074b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('plan', sa.Enum('free', 'starter', 'pro', 'enterprise', name='userplan'), server_default='free', nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_verified', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_stripe_customer_id', 'users', ['stripe_customer_id'], unique=False)

    # Create agents table
    op.create_table(
        'agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('direction', sa.Enum('inbound', 'outbound', name='agentdirection'), nullable=False),
        sa.Column('status', sa.Enum('draft', 'active', 'paused', 'archived', name='agentstatus'), server_default='draft', nullable=False),
        sa.Column('stt_engine', sa.String(length=50), server_default='faster-whisper', nullable=False),
        sa.Column('tts_engine', sa.String(length=50), server_default='kokoro', nullable=False),
        sa.Column('tts_voice', sa.String(length=100), server_default='af_heart', nullable=False),
        sa.Column('language', sa.String(length=10), server_default='en', nullable=False),
        sa.Column('llm_provider', sa.String(length=50), server_default='ollama', nullable=False),
        sa.Column('llm_model', sa.String(length=100), server_default='qwen3:4b', nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('opening_line', sa.Text(), nullable=True),
        sa.Column('objective_prompt', sa.Text(), nullable=True),
        sa.Column('objection_handling_prompt', sa.Text(), nullable=True),
        sa.Column('voicemail_prompt', sa.Text(), nullable=True),
        sa.Column('closing_prompt', sa.Text(), nullable=True),
        sa.Column('escalation_rule', sa.Text(), nullable=True),
        sa.Column('greeting_prompt', sa.Text(), nullable=True),
        sa.Column('qualification_prompt', sa.Text(), nullable=True),
        sa.Column('knowledge_prompt', sa.Text(), nullable=True),
        sa.Column('fallback_prompt', sa.Text(), nullable=True),
        sa.Column('handoff_prompt', sa.Text(), nullable=True),
        sa.Column('interruption_sensitivity', sa.String(length=20), server_default='medium', nullable=False),
        sa.Column('max_call_duration_s', sa.Integer(), server_default='300', nullable=False),
        sa.Column('silence_timeout_s', sa.Integer(), server_default='10', nullable=False),
        sa.Column('daily_call_cap', sa.Integer(), server_default='100', nullable=False),
        sa.Column('rate_limit_per_minute', sa.Integer(), server_default='30', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agents_owner_status', 'agents', ['owner_id', 'status'], unique=False)
    op.create_index('ix_agents_owner_direction', 'agents', ['owner_id', 'direction'], unique=False)

    # Create agent_prompt_versions table
    op.create_table(
        'agent_prompt_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('edited_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('key_prefix', sa.String(length=20), nullable=False),
        sa.Column('webhook_url', sa.String(length=500), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'], unique=True)
    op.create_index('ix_api_keys_agent_id', 'api_keys', ['agent_id'], unique=False)
    op.create_index('ix_api_keys_user_id', 'api_keys', ['user_id'], unique=False)

    # Create call_logs table
    op.create_table(
        'call_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('direction', sa.Enum('inbound', 'outbound', name='calldirection'), nullable=False),
        sa.Column('caller_ref', sa.String(length=255), nullable=True),
        sa.Column('transcript', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('duration_s', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.Enum('initiated', 'ringing', 'answered', 'in_progress', 'completed', 'failed', 'busy', 'no_answer', 'voicemail', 'queued_for_external_dialer', name='callstatus'), server_default='initiated', nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('call_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_call_logs_agent_started', 'call_logs', ['agent_id', 'started_at'], unique=False)
    op.create_index('ix_call_logs_status', 'call_logs', ['status'], unique=False)

    # Create cold_call_queue_entries table
    op.create_table(
        'cold_call_queue_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('contact_name', sa.String(length=255), nullable=False),
        sa.Column('phone_number', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=True),
        sa.Column('status', sa.Enum('pending', 'queued', 'in_progress', 'completed', 'failed', name='queueentrystatus'), server_default='pending', nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('call_log_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['call_log_id'], ['call_logs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_id', 'phone_number', name='uq_agent_phone')
    )
    op.create_index('ix_queue_agent_status', 'cold_call_queue_entries', ['agent_id', 'status'], unique=False)
    op.create_index('ix_queue_scheduled', 'cold_call_queue_entries', ['scheduled_at'], unique=False)

    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('plan', sa.Enum('free', 'starter', 'pro', 'enterprise', name='userplan'), server_default='free', nullable=False),
        sa.Column('status', sa.Enum('active', 'past_due', 'canceled', 'unpaid', 'trialing', 'incomplete', 'incomplete_expired', 'paused', name='subscriptionstatus'), server_default='incomplete', nullable=False),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trial_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trial_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
        sa.UniqueConstraint('stripe_subscription_id')
    )
    op.create_index('ix_subscriptions_stripe_customer_id', 'subscriptions', ['stripe_customer_id'], unique=False)

    # Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
    )
    op.create_index('ix_refresh_tokens_user_expires', 'refresh_tokens', ['user_id', 'expires_at'], unique=False)
    op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'], unique=True)

    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')


def downgrade() -> None:
    op.drop_table('refresh_tokens')
    op.drop_table('subscriptions')
    op.drop_table('cold_call_queue_entries')
    op.drop_table('call_logs')
    op.drop_table('api_keys')
    op.drop_table('agent_prompt_versions')
    op.drop_table('agents')
    op.drop_table('users')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS userplan')
    op.execute('DROP TYPE IF EXISTS agentdirection')
    op.execute('DROP TYPE IF EXISTS agentstatus')
    op.execute('DROP TYPE IF EXISTS calldirection')
    op.execute('DROP TYPE IF EXISTS callstatus')
    op.execute('DROP TYPE IF EXISTS queueentrystatus')
    op.execute('DROP TYPE IF EXISTS subscriptionstatus')