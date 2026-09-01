"""drop part specifications column

Revision ID: 7bf8ed526fbb
Revises: 6efb708f60b1
Create Date: 2026-05-03 18:55:10.351018

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7bf8ed526fbb'
down_revision: Union[str, None] = '6efb708f60b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('parts', 'specifications')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'parts',
        sa.Column(
            'specifications',
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
