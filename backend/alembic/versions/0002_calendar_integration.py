"""calendar integration: calendar_connections, transcripts, meeting auto-join/status

Revision ID: 0002_calendar_integration
Revises: 0001_initial
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_calendar_integration"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create calendar_connections table
    op.create_table(
        "calendar_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_email", sa.String(255), nullable=False, unique=True),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text()),
        sa.Column("token_expiry", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )

    # Add new columns to meetings table
    op.add_column(
        "meetings",
        sa.Column(
            "status",
            sa.String(40),
            nullable=False,
            server_default="scheduled",
        ),
    )

    op.add_column(
        "meetings",
        sa.Column(
            "auto_join",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # SQLite-compatible foreign key addition
    with op.batch_alter_table("meetings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "calendar_connection_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.create_foreign_key(
            "fk_meetings_calendar_connection",
            "calendar_connections",
            ["calendar_connection_id"],
            ["id"],
        )

    # Create transcripts table
    op.create_table(
        "transcripts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.Integer(),
            sa.ForeignKey("meetings.id"),
            nullable=False,
        ),
        sa.Column("speaker", sa.String(120), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.String(40)),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.create_index(
        "ix_transcripts_meeting_id",
        "transcripts",
        ["meeting_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_transcripts_meeting_id",
        table_name="transcripts",
    )

    op.drop_table("transcripts")

    with op.batch_alter_table("meetings") as batch_op:
        batch_op.drop_constraint(
            "fk_meetings_calendar_connection",
            type_="foreignkey",
        )
        batch_op.drop_column("calendar_connection_id")

    op.drop_column("meetings", "auto_join")
    op.drop_column("meetings", "status")

    op.drop_table("calendar_connections")