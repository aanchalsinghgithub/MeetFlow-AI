"""add error_message column to meetings

So a failed bot-join has a visible reason instead of just "failed".

Revision ID: 0006_meeting_error_message
Revises: 0005_oauth_states
Create Date: 2026-08-07
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_meeting_error_message"
down_revision = "0005_oauth_states"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("meetings", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("meetings", "error_message")
