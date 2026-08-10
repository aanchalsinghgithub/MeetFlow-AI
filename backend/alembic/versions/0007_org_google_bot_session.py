"""add per-organization google bot session columns

Revision ID: 0007_org_google_bot_session
Revises: 0006_meeting_error_message
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_org_google_bot_session"
down_revision = "0006_meeting_error_message"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("google_bot_email", sa.String(length=255), nullable=True))
    op.add_column("organizations", sa.Column("google_bot_storage_state", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "google_bot_storage_state")
    op.drop_column("organizations", "google_bot_email")
