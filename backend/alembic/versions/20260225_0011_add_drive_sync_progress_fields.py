"""add drive sync progress fields

Revision ID: 20260225_0011
Revises: 20260224_0010
Create Date: 2026-02-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260225_0011"
down_revision = "20260224_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("drive_sync_state", sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'idle'")))
    op.add_column("drive_sync_state", sa.Column("pending_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("drive_sync_state", sa.Column("processed_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("drive_sync_state", sa.Column("imported_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("drive_sync_state", sa.Column("skipped_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("drive_sync_state", sa.Column("failed_count", sa.Integer(), nullable=False, server_default=sa.text("0")))


def downgrade() -> None:
    op.drop_column("drive_sync_state", "failed_count")
    op.drop_column("drive_sync_state", "skipped_count")
    op.drop_column("drive_sync_state", "imported_count")
    op.drop_column("drive_sync_state", "processed_count")
    op.drop_column("drive_sync_state", "pending_count")
    op.drop_column("drive_sync_state", "status")
