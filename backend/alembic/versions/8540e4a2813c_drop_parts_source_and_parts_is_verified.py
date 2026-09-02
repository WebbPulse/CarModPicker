"""drop parts.source and parts.is_verified

Revision ID: 8540e4a2813c
Revises: 7bf8ed526fbb
Create Date: 2026-05-16 17:48:28.386351

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8540e4a2813c'
down_revision: Union[str, None] = '7bf8ed526fbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Hand-trimmed: autogenerate also surfaced pre-existing schema drift
    (categories constraint renames, FK naming, the mfr_pn index) unrelated
    to this change. Only the two column drops are kept here.
    """
    # SAFE: a crawler-vs-user_created discriminator; crawler part creation was disconnected in da7e10a and dedup now runs off canonical_part_id.
    op.drop_column('parts', 'source')
    # SAFE: never written anywhere in the codebase: model default False, exposed read-only in PartRead, no assignment in app, crawlers, or fixtures.
    op.drop_column('parts', 'is_verified')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('parts', sa.Column('is_verified', sa.BOOLEAN(), autoincrement=False, nullable=False, server_default=sa.false()))
    op.add_column('parts', sa.Column('source', sa.VARCHAR(), autoincrement=False, nullable=False, server_default='user_created'))
