"""add audio_url to call_logs

Revision ID: 20260824_1200
Revises: 20260815_0645_947f600fb21d
Create Date: 2026-08-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '20260824_1200'
down_revision = '20260815_0645_947f600fb21d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add audio_url column to call_logs table
    op.add_column('call_logs', sa.Column('audio_url', sa.String(500), nullable=True))


def downgrade() -> None:
    # Remove audio_url column from call_logs table
    op.drop_column('call_logs', 'audio_url')