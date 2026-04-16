"""migrate all PKs and FKs to uuid7

Revision ID: 5a381dff5fd1
Revises: 5f5924feaa24
Create Date: 2026-04-15 21:44:01.111969

DESTRUCTIVE: All existing rows are dropped. Every table is re-created with
UUID primary/foreign keys from the current SQLAlchemy model metadata.
Casting integer IDs to UUID has no meaningful conversion, so the plan
(CAR-64) accepts data loss in dev. Production databases should be reseeded
after this migration.
"""
from typing import Sequence, Union

from alembic import op

from app.db.base import Base

# Ensure all model modules register their tables on Base.metadata before drop/create.
import app.api.models  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = '5a381dff5fd1'
down_revision: Union[str, None] = '5f5924feaa24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop every model-managed table and recreate with UUID schema."""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """No non-destructive downgrade path — see migration docstring."""
    raise NotImplementedError(
        "Downgrade from UUID back to integer primary keys is not supported."
    )
