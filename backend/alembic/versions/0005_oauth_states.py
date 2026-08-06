"""oauth states table for calendar connect flow

Revision ID: 0005_oauth_states
Revises: 0004_multi_tenant_organizations
Create Date: 2026-08-07
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_oauth_states"
down_revision = "0004_multi_tenant_organizations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state", sa.String(255), nullable=False, unique=True),
        sa.Column("code_verifier", sa.String(255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_oauth_states_id", "oauth_states", ["id"])
    op.create_index("ix_oauth_states_state", "oauth_states", ["state"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_oauth_states_state", table_name="oauth_states")
    op.drop_index("ix_oauth_states_id", table_name="oauth_states")
    op.drop_table("oauth_states")
