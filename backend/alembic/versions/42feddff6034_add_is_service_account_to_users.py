"""add_is_service_account_to_users

Revision ID: 42feddff6034
Revises: 72a9aa17fc28
Create Date: 2026-04-12 16:16:09.779234

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '42feddff6034'
down_revision: Union[str, None] = '72a9aa17fc28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('is_service_account', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'is_service_account')
