"""create drive_sync_state table

Revision ID: 20260224_0005
Revises: 20260224_0004
Create Date: 2026-02-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260224_0005"
down_revision = "20260224_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drive_sync_state",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("folder_id", sa.Text(), nullable=True),
        sa.Column("folder_name", sa.Text(), nullable=True),
        sa.Column("next_page_token", sa.Text(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("drive_sync_state")
