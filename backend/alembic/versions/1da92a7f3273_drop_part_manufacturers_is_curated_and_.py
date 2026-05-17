"""drop part_manufacturers is_curated and created_by_user_id

Revision ID: 1da92a7f3273
Revises: 8540e4a2813c
Create Date: 2026-05-16 18:02:51.046946

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1da92a7f3273'
down_revision: Union[str, None] = '8540e4a2813c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Hand-trimmed to only the part_manufacturers changes; autogenerate also
    surfaced pre-existing schema drift (categories/build_list_parts/parts
    constraint + index renames) that is unrelated to this change.

    Collapses the curated/UGC manufacturer model into a single global
    namespace: drops is_curated + created_by_user_id (and their FK/indexes
    and the two partial unique indexes) and replaces them with one unique
    index on lower(name).
    """
    op.drop_index(op.f('ix_part_manufacturers_created_by_user_id'), table_name='part_manufacturers')
    op.drop_index(op.f('ix_part_manufacturers_is_curated'), table_name='part_manufacturers')
    op.drop_index(op.f('uq_pm_curated_name'), table_name='part_manufacturers', postgresql_where='(is_curated IS TRUE)')
    op.drop_index(op.f('uq_pm_ugc_per_user'), table_name='part_manufacturers', postgresql_where='(is_curated IS FALSE)')
    op.create_index('uq_pm_name', 'part_manufacturers', [sa.literal_column('lower(name)')], unique=True)
    op.drop_constraint(op.f('fk_part_manufacturers_created_by_user_id_users'), 'part_manufacturers', type_='foreignkey')
    op.drop_column('part_manufacturers', 'created_by_user_id')
    op.drop_column('part_manufacturers', 'is_curated')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'part_manufacturers',
        sa.Column('is_curated', sa.BOOLEAN(), autoincrement=False, nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'part_manufacturers',
        sa.Column('created_by_user_id', sa.UUID(), autoincrement=False, nullable=True),
    )
    op.create_foreign_key(op.f('fk_part_manufacturers_created_by_user_id_users'), 'part_manufacturers', 'users', ['created_by_user_id'], ['id'], ondelete='SET NULL')
    op.drop_index('uq_pm_name', table_name='part_manufacturers')
    op.create_index(op.f('uq_pm_ugc_per_user'), 'part_manufacturers', [sa.literal_column('lower(name::text)'), 'created_by_user_id'], unique=True, postgresql_where='(is_curated IS FALSE)')
    op.create_index(op.f('uq_pm_curated_name'), 'part_manufacturers', [sa.literal_column('lower(name::text)')], unique=True, postgresql_where='(is_curated IS TRUE)')
    op.create_index(op.f('ix_part_manufacturers_is_curated'), 'part_manufacturers', ['is_curated'], unique=False)
    op.create_index(op.f('ix_part_manufacturers_created_by_user_id'), 'part_manufacturers', ['created_by_user_id'], unique=False)
