"""add ivfflat index for paper embeddings

Revision ID: c35c7a54af6c
Revises: f3df81e2f33d
Create Date: 2026-03-16 02:51:56.566334

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c35c7a54af6c'
down_revision: Union[str, Sequence[str], None] = 'f3df81e2f33d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # IVFFlat cosine index for abstract embedding search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_papers_abstract_embedding_ivfflat
        ON papers
        USING ivfflat (abstract_embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )

    # Refresh planner stats after index creation
    op.execute("ANALYZE papers")



def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_papers_abstract_embedding_ivfflat"
    )
