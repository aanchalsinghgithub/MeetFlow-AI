"""meeting summary detail: key_discussion_points, risks, blockers

Revision ID: 0003_meeting_summary_detail
Revises: 0002_calendar_integration
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_meeting_summary_detail"
down_revision = "0002_calendar_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("key_discussion_points", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "meetings",
        sa.Column("risks", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "meetings",
        sa.Column("blockers", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("meetings", "blockers")
    op.drop_column("meetings", "risks")
    op.drop_column("meetings", "key_discussion_points")
