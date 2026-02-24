"""add public sharing fields to albums

Revision ID: 20260224_0010
Revises: 20260224_0009
Create Date: 2026-02-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260224_0010"
down_revision = "20260224_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("albums", sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("albums", sa.Column("public_token", sa.String(length=64), nullable=True))
    op.create_index("ix_albums_public_token", "albums", ["public_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_albums_public_token", table_name="albums")
    op.drop_column("albums", "public_token")
    op.drop_column("albums", "is_public")
