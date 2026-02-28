"""create drive sync job tables

Revision ID: 20260226_0011
Revises: 20260224_0010
Create Date: 2026-02-26 02:35:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260226_0011"
down_revision = "20260224_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drive_sync_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folder_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("job_type", sa.String(), nullable=False, server_default="full_sync"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("total_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploaded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_drive_sync_jobs_user_id"), "drive_sync_jobs", ["user_id"], unique=False)

    op.create_table(
        "drive_sync_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_file_id", sa.Text(), nullable=False),
        sa.Column("source_entry_id", sa.Text(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("state", sa.String(), nullable=False, server_default="pending"),
        sa.Column("batch_no", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["job_id"], ["drive_sync_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "source_file_id", "source_entry_id", name="uq_drive_sync_file_source"),
    )
    op.create_index(op.f("ix_drive_sync_files_job_id"), "drive_sync_files", ["job_id"], unique=False)
    op.create_index(op.f("ix_drive_sync_files_user_id"), "drive_sync_files", ["user_id"], unique=False)

    op.create_table(
        "drive_sync_checkpoints",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_batch_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_success_key", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["job_id"], ["drive_sync_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )


def downgrade() -> None:
    op.drop_table("drive_sync_checkpoints")
    op.drop_index(op.f("ix_drive_sync_files_user_id"), table_name="drive_sync_files")
    op.drop_index(op.f("ix_drive_sync_files_job_id"), table_name="drive_sync_files")
    op.drop_table("drive_sync_files")
    op.drop_index(op.f("ix_drive_sync_jobs_user_id"), table_name="drive_sync_jobs")
    op.drop_table("drive_sync_jobs")
