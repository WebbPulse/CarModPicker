"""add_purchased_field_to_build_list_parts

Revision ID: 3a3e341a0988
Revises: 03841789e0c3
Create Date: 2026-01-18 16:55:04.757766

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3a3e341a0988"
down_revision: Union[str, None] = "03841789e0c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add purchased column as boolean with default False
    op.add_column("build_list_parts", sa.Column("purchased", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("build_list_parts", "purchased")
