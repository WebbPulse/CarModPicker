"""merge_purchased_field_and_votes_reports

Revision ID: 6a5ca7e34fc8
Revises: 03841789e0c3, 3a3e341a0988
Create Date: 2026-01-18 16:59:35.016658

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6a5ca7e34fc8"
down_revision: Union[str, None] = ("03841789e0c3", "3a3e341a0988")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
