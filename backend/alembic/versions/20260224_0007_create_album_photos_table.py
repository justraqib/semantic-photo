"""create album_photos junction table

Revision ID: 20260224_0007
Revises: 20260224_0006
Create Date: 2026-02-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260224_0007"
down_revision = "20260224_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "album_photos",
        sa.Column("album_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("albums.id", ondelete="CASCADE"), nullable=False),
        sa.Column("photo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("photos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("album_id", "photo_id", name="pk_album_photos"),
    )
    op.create_index("ix_album_photos_album_id_position", "album_photos", ["album_id", "position"])


def downgrade() -> None:
    op.drop_index("ix_album_photos_album_id_position", table_name="album_photos")
    op.drop_table("album_photos")
