"""multi-tenant organizations

Revision ID: 0004_multi_tenant_organizations
Revises: 0003_meeting_summary_detail
Create Date: 2026-07-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_multi_tenant_organizations"
down_revision = "0003_meeting_summary_detail"
branch_labels = None
depends_on = None

TENANT_TABLES = ("users", "calendar_connections", "meetings", "tasks", "approvals")


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_organizations_id", "organizations", ["id"])
    op.create_index("ix_organizations_name", "organizations", ["name"], unique=True)

    conn = op.get_bind()
    conn.execute(
        sa.text("INSERT INTO organizations (name, created_at) VALUES (:name, CURRENT_TIMESTAMP)"),
        {"name": "Default Org"},
    )
    default_org_id = conn.execute(
        sa.text("SELECT id FROM organizations WHERE name = :name"),
        {"name": "Default Org"},
    ).scalar_one()

    for table_name in TENANT_TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))

        conn.execute(
            sa.text(f"UPDATE {table_name} SET organization_id = :organization_id WHERE organization_id IS NULL"),
            {"organization_id": default_org_id},
        )

        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column("organization_id", existing_type=sa.Integer(), nullable=False)
            batch_op.create_foreign_key(
                f"fk_{table_name}_organization_id",
                "organizations",
                ["organization_id"],
                ["id"],
            )

        op.create_index(f"ix_{table_name}_organization_id", table_name, ["organization_id"])

    # Calendar connections must be unique per tenant, not global by Google email.
    try:
        op.drop_constraint("calendar_connections_user_email_key", "calendar_connections", type_="unique")
    except Exception:
        pass
    op.create_index(
        "ix_calendar_connections_org_email",
        "calendar_connections",
        ["organization_id", "user_email"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_calendar_connections_org_email", table_name="calendar_connections")

    for table_name in reversed(TENANT_TABLES):
        op.drop_index(f"ix_{table_name}_organization_id", table_name=table_name)
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(f"fk_{table_name}_organization_id", type_="foreignkey")
            batch_op.drop_column("organization_id")

    op.drop_index("ix_organizations_name", table_name="organizations")
    op.drop_index("ix_organizations_id", table_name="organizations")
    op.drop_table("organizations")
