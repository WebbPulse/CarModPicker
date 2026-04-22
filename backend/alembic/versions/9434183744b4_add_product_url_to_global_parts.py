"""add product url to global parts

Revision ID: 9434183744b4
Revises: 04e42912c65c
Create Date: 2026-01-19 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9434183744b4"
down_revision: Union[str, None] = "04e42912c65c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("global_parts", sa.Column("product_url", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # SAFE: downgrade reversal of already-applied migration — see SAFE-04
    op.drop_column("global_parts", "product_url")
