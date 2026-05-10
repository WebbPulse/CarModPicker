"""add build_list_labor_estimates

Revision ID: f99b709f371a
Revises: 165ed4efb3bf
Create Date: 2026-05-02 21:23:08.491818

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f99b709f371a'
down_revision: Union[str, None] = '165ed4efb3bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'build_list_labor_estimates',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('build_list_id', sa.Uuid(), nullable=False),
        sa.Column('build_list_phase_id', sa.Uuid(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('cost_cents', sa.Integer(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['build_list_id'],
            ['build_lists.id'],
            name=op.f('fk_build_list_labor_estimates_build_list_id_build_lists'),
        ),
        sa.ForeignKeyConstraint(
            ['build_list_phase_id'],
            ['build_list_phases.id'],
            name=op.f('fk_build_list_labor_estimates_build_list_phase_id_build_list_phases'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_build_list_labor_estimates')),
    )
    op.create_index(
        op.f('ix_build_list_labor_estimates_build_list_id'),
        'build_list_labor_estimates',
        ['build_list_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_build_list_labor_estimates_build_list_phase_id'),
        'build_list_labor_estimates',
        ['build_list_phase_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_build_list_labor_estimates_id'),
        'build_list_labor_estimates',
        ['id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_build_list_labor_estimates_id'), table_name='build_list_labor_estimates'
    )
    op.drop_index(
        op.f('ix_build_list_labor_estimates_build_list_phase_id'),
        table_name='build_list_labor_estimates',
    )
    op.drop_index(
        op.f('ix_build_list_labor_estimates_build_list_id'),
        table_name='build_list_labor_estimates',
    )
    op.drop_table('build_list_labor_estimates')
