"""Change vector dimension from 1536 to 1024 for Titan Embed v2.

Revision ID: a1b2c3d4e5f6
Revises: 826ddedd5b20
Create Date: 2025-12-02 17:42:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "826ddedd5b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Change embedding vector dimension from 1536 to 1024.

    AWS Titan Embed v2 supports: 256, 512, 1024 dimensions.
    This migration updates the entities.embedding column.

    WARNING: Existing embeddings will be dropped and need to be regenerated.
    """
    # Drop the existing embedding column and recreate with new dimension
    # pgvector doesn't support ALTER COLUMN for dimension changes
    op.execute("ALTER TABLE entities DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE entities ADD COLUMN embedding vector(1024)")


def downgrade() -> None:
    """Revert to 1536 dimension (Titan Embed v1)."""
    op.execute("ALTER TABLE entities DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE entities ADD COLUMN embedding vector(1536)")
