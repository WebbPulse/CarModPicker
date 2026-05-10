"""add base_price_cents to build_lists

Adds the donor-car purchase price to ``build_lists`` so it can be folded into
the rolled-up build cost alongside parts and labor. ``server_default='0'``
backfills existing rows, allowing the column to land non-nullable in one step.

Revision ID: 6efb708f60b1
Revises: 4edb71f895f0
Create Date: 2026-05-03 18:32:50.963196

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6efb708f60b1'
down_revision: Union[str, None] = '4edb71f895f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'build_lists',
        sa.Column('base_price_cents', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('build_lists', 'base_price_cents')
