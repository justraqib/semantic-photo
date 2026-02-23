"""add embedding_generated_at to photos

Revision ID: 20260224_0003
Revises: 20260223_0002
Create Date: 2026-02-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260224_0003"
down_revision = "20260223_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("photos", sa.Column("embedding_generated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("photos", "embedding_generated_at")
