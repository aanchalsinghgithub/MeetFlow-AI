"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("teams", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("leader_email", sa.String(255), nullable=False), sa.Column("keywords", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    op.create_table("meetings", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(255), nullable=False), sa.Column("provider", sa.String(40), nullable=False), sa.Column("external_id", sa.String(255)), sa.Column("join_url", sa.Text()), sa.Column("starts_at", sa.DateTime()), sa.Column("ends_at", sa.DateTime()), sa.Column("summary", sa.Text()), sa.Column("decisions", sa.JSON(), nullable=False), sa.Column("transcript", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("email", sa.String(255), nullable=False), sa.Column("full_name", sa.String(255), nullable=False), sa.Column("hashed_password", sa.String(255), nullable=False), sa.Column("role", sa.String(40), nullable=False), sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id")), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    op.create_table("participants", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id"), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("email", sa.String(255)), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    op.create_table("tasks", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id")), sa.Column("title", sa.String(255), nullable=False), sa.Column("description", sa.Text()), sa.Column("owner", sa.String(255)), sa.Column("mentioned_by", sa.String(255)), sa.Column("requested_by", sa.String(255)), sa.Column("deadline", sa.String(255)), sa.Column("priority", sa.String(40), nullable=False), sa.Column("domain", sa.String(80)), sa.Column("dependencies", sa.JSON(), nullable=False), sa.Column("confidence", sa.Float(), nullable=False), sa.Column("status", sa.String(60), nullable=False), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    op.create_table("approvals", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id"), nullable=False), sa.Column("manager_email", sa.String(255), nullable=False), sa.Column("decision", sa.String(40), nullable=False), sa.Column("edited_payload", sa.JSON()), sa.Column("notes", sa.Text()), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    op.create_table("notifications", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("channel", sa.String(60), nullable=False), sa.Column("recipient", sa.String(255), nullable=False), sa.Column("subject", sa.String(255), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("status", sa.String(40), nullable=False), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    op.create_table("corrections", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id")), sa.Column("field_name", sa.String(120), nullable=False), sa.Column("old_value", sa.Text()), sa.Column("new_value", sa.Text()), sa.Column("corrected_by", sa.String(255), nullable=False), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    op.create_table("audit_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("actor", sa.String(255), nullable=False), sa.Column("action", sa.String(120), nullable=False), sa.Column("resource_type", sa.String(120), nullable=False), sa.Column("resource_id", sa.String(120), nullable=False), sa.Column("metadata", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))


def downgrade() -> None:
    for table in ["audit_logs", "corrections", "notifications", "approvals", "tasks", "participants", "users", "meetings", "teams"]:
        op.drop_table(table)
