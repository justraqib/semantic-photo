"""create memories table

Revision ID: 20260224_0008
Revises: 20260224_0007
Create Date: 2026-02-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260224_0008"
down_revision = "20260224_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("photo_ids", sa.JSON(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("memory_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_memories_user_id_memory_date", "memories", ["user_id", "memory_date"])


def downgrade() -> None:
    op.drop_index("ix_memories_user_id_memory_date", table_name="memories")
    op.drop_table("memories")
