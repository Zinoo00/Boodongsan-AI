"""Change vector dimension from 1536 to 1024 for Titan Embed v2.

Revision ID: a1b2c3d4e5f6
Revises: 826ddedd5b20
Create Date: 2025-12-02 17:42:00.000000

This migration handles ALL vector columns in the database:
1. Our application's `entities` table
2. LightRAG's internal tables (BODA_chunks, BODA_entities, BODA_relationships)

WARNING: All existing embeddings will be dropped and need to be regenerated.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "826ddedd5b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Change all vector columns from 1536 to 1024 dimensions.

    Handles:
    - entities.embedding (our application table)
    - BODA_chunks.__vector__ (LightRAG)
    - BODA_entities.__vector__ (LightRAG)
    - BODA_relationships.__vector__ (LightRAG)
    """
    # 1. Our application's entities table
    op.execute("ALTER TABLE entities DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE entities ADD COLUMN embedding vector(1024)")

    # 2. LightRAG tables (workspace: BODA)
    # These tables are created by LightRAG with __vector__ columns
    lightrag_tables = [
        '"BODA_chunks"',
        '"BODA_entities"',
        '"BODA_relationships"',
    ]

    for table in lightrag_tables:
        # Check if table exists before altering
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT FROM pg_tables WHERE tablename = {table.replace('"', "'")} OR tablename = LOWER({table.replace('"', "'")})) THEN
                    -- Drop and recreate vector column with new dimension
                    EXECUTE 'ALTER TABLE ' || {table} || ' DROP COLUMN IF EXISTS "__vector__"';
                    EXECUTE 'ALTER TABLE ' || {table} || ' ADD COLUMN "__vector__" vector(1024)';
                END IF;
            END
            $$;
        """)


def downgrade() -> None:
    """Revert all vector columns to 1536 dimensions (Titan Embed v1)."""
    # 1. Our application's entities table
    op.execute("ALTER TABLE entities DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE entities ADD COLUMN embedding vector(1536)")

    # 2. LightRAG tables
    lightrag_tables = [
        '"BODA_chunks"',
        '"BODA_entities"',
        '"BODA_relationships"',
    ]

    for table in lightrag_tables:
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT FROM pg_tables WHERE tablename = {table.replace('"', "'")} OR tablename = LOWER({table.replace('"', "'")})) THEN
                    EXECUTE 'ALTER TABLE ' || {table} || ' DROP COLUMN IF EXISTS "__vector__"';
                    EXECUTE 'ALTER TABLE ' || {table} || ' ADD COLUMN "__vector__" vector(1536)';
                END IF;
            END
            $$;
        """)
