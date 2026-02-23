"""convert embedding to vector and add pgvector index

Revision ID: 20260224_0004
Revises: 20260224_0003
Create Date: 2026-02-24 00:00:00.000000
"""

from alembic import op


revision = "20260224_0004"
down_revision = "20260224_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        ALTER TABLE photos
        ALTER COLUMN embedding TYPE vector(512)
        USING CASE
            WHEN embedding IS NULL OR btrim(embedding) = '' THEN NULL
            ELSE embedding::vector
        END
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS photos_embedding_idx
        ON photos
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS photos_embedding_idx")
    op.execute(
        """
        ALTER TABLE photos
        ALTER COLUMN embedding TYPE text
        USING CASE
            WHEN embedding IS NULL THEN NULL
            ELSE embedding::text
        END
        """
    )
