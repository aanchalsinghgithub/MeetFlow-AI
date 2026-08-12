"""remove bot-related columns (meeting bot feature removed)

The meeting bot (Playwright joining Google Meet, per-org Google session,
auto-join scheduler) has been removed entirely — see CHANGES.md. The
transcript has only ever come from Electron's WASAPI capture + Whisper,
never from the bot, so removing it doesn't affect transcription. This
drops the columns that only existed to support it.

Revision ID: 0008_remove_bot_columns
Revises: 0007_org_google_bot_session
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_remove_bot_columns"
down_revision = "0007_org_google_bot_session"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("meetings", "error_message")
    op.drop_column("meetings", "auto_join")
    op.drop_column("organizations", "google_bot_email")
    op.drop_column("organizations", "google_bot_storage_state")


def downgrade() -> None:
    op.add_column("organizations", sa.Column("google_bot_storage_state", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("google_bot_email", sa.String(length=255), nullable=True))
    op.add_column("meetings", sa.Column("auto_join", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("meetings", sa.Column("error_message", sa.Text(), nullable=True))
