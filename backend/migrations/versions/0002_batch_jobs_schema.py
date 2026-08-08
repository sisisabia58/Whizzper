"""batch_jobs schema

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "batch_jobs" not in inspector.get_table_names():
        op.create_table(
            "batch_jobs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("batch_id", sa.String(), nullable=False),
            sa.Column("source_type", sa.String(), server_default="drive_folder"),
            sa.Column("source_url", sa.String(), nullable=True),
            sa.Column("folder_name", sa.String(), nullable=False),
            sa.Column("status", sa.String(), server_default="queued"),
            sa.Column("total_files", sa.Integer(), server_default="0"),
            sa.Column("completed_files", sa.Integer(), server_default="0"),
            sa.Column("failed_files", sa.Integer(), server_default="0"),
            sa.Column("task_params", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("access_mode", sa.String(), server_default="link"),
            sa.Column("connection_id", sa.String(), nullable=True),
            sa.Column("writeback_enabled", sa.Boolean(), server_default=sa.false()),
            sa.Column("uploaded_files", sa.Integer(), server_default="0"),
            sa.Column("writeback_failed_files", sa.Integer(), server_default="0"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_batch_jobs_batch_id"), "batch_jobs", ["batch_id"], unique=True)
        op.create_index(op.f("ix_batch_jobs_folder_name"), "batch_jobs", ["folder_name"], unique=False)

    if "tasks" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("tasks")}
        if "batch_id" not in columns:
            op.add_column("tasks", sa.Column("batch_id", sa.String(), nullable=True))
            op.create_index(op.f("ix_tasks_batch_id"), "tasks", ["batch_id"], unique=False)
        if "source_file_id" not in columns:
            op.add_column("tasks", sa.Column("source_file_id", sa.String(), nullable=True))
        if "source_path" not in columns:
            op.add_column("tasks", sa.Column("source_path", sa.String(), nullable=True))
        if "source_parent_id" not in columns:
            op.add_column("tasks", sa.Column("source_parent_id", sa.String(), nullable=True))
        if "writeback_status" not in columns:
            op.add_column("tasks", sa.Column("writeback_status", sa.String(), nullable=True))
        if "writeback_file_id" not in columns:
            op.add_column("tasks", sa.Column("writeback_file_id", sa.String(), nullable=True))
        if "writeback_error" not in columns:
            op.add_column("tasks", sa.Column("writeback_error", sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tasks" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("tasks")}
        if "writeback_error" in columns:
            op.drop_column("tasks", "writeback_error")
        if "writeback_file_id" in columns:
            op.drop_column("tasks", "writeback_file_id")
        if "writeback_status" in columns:
            op.drop_column("tasks", "writeback_status")
        if "source_parent_id" in columns:
            op.drop_column("tasks", "source_parent_id")
        if "source_path" in columns:
            op.drop_column("tasks", "source_path")
        if "source_file_id" in columns:
            op.drop_column("tasks", "source_file_id")
        if "batch_id" in columns:
            op.drop_index(op.f("ix_tasks_batch_id"), table_name="tasks")
            op.drop_column("tasks", "batch_id")
    if "batch_jobs" in inspector.get_table_names():
        op.drop_index(op.f("ix_batch_jobs_folder_name"), table_name="batch_jobs")
        op.drop_index(op.f("ix_batch_jobs_batch_id"), table_name="batch_jobs")
        op.drop_table("batch_jobs")
