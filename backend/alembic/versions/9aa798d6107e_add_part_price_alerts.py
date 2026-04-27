"""add part_price_alerts

Revision ID: 9aa798d6107e
Revises: afdf25556c6c
Create Date: 2026-04-25 15:16:20.075458

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9aa798d6107e'
down_revision: Union[str, None] = 'afdf25556c6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'part_price_alerts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('part_id', sa.Uuid(), nullable=False),
        sa.Column('threshold_cents', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('last_fired_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('threshold_cents >= 0', name=op.f('ck_part_price_alerts_threshold_cents_non_negative')),
        sa.ForeignKeyConstraint(['part_id'], ['parts.id'], name=op.f('fk_part_price_alerts_part_id_parts')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_part_price_alerts_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_part_price_alerts')),
        sa.UniqueConstraint('user_id', 'part_id', name='uq_part_price_alert_user_part'),
    )
    op.create_index(op.f('ix_part_price_alerts_id'), 'part_price_alerts', ['id'], unique=False)
    op.create_index(op.f('ix_part_price_alerts_part_id'), 'part_price_alerts', ['part_id'], unique=False)
    op.create_index(op.f('ix_part_price_alerts_user_id'), 'part_price_alerts', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_part_price_alerts_user_id'), table_name='part_price_alerts')
    op.drop_index(op.f('ix_part_price_alerts_part_id'), table_name='part_price_alerts')
    op.drop_index(op.f('ix_part_price_alerts_id'), table_name='part_price_alerts')
    # SAFE: downgrade reversal of already-applied migration — see SAFE-04
    op.drop_table('part_price_alerts')
