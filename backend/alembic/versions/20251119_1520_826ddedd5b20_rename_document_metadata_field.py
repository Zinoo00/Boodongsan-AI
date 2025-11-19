"""rename_document_metadata_field

Revision ID: 826ddedd5b20
Revises: 
Create Date: 2025-11-19 15:20:10.581325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '826ddedd5b20'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename metadata column to doc_metadata to avoid SQLAlchemy conflict."""
    op.alter_column('documents', 'metadata', new_column_name='doc_metadata')


def downgrade() -> None:
    """Rename doc_metadata back to metadata."""
    op.alter_column('documents', 'doc_metadata', new_column_name='metadata')
