"""create tags and photo_tags tables

Revision ID: 20260224_0009
Revises: 20260224_0008
Create Date: 2026-02-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260224_0009"
down_revision = "20260224_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
    )

    op.create_table(
        "photo_tags",
        sa.Column("photo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("photos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'clip'")),
        sa.PrimaryKeyConstraint("photo_id", "tag_id", name="pk_photo_tags"),
    )


def downgrade() -> None:
    op.drop_table("photo_tags")
    op.drop_table("tags")
