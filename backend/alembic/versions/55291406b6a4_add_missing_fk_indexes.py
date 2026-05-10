"""add missing FK indexes

DATA-05 (Phase 4 D-12/D-16) — index-only migration for FK join keys; Phase 1
SAFE-09 naming_convention auto-names each index. Non-index output from
alembic autogenerate (constraint renames, FK re-adds that reflect Phase 1's
naming_convention overlay) was discarded per D-13 / Pitfall 10 — those are
forward-only historic-name deferrals, not real schema work.

Revision ID: 55291406b6a4
Revises: aa583927d86a
Create Date: 2026-04-22 20:36:06.417062

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '55291406b6a4'
down_revision: Union[str, None] = 'aa583927d86a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — add missing FK indexes only."""
    op.create_index(op.f('ix_bug_reports_assigned_to'), 'bug_reports', ['assigned_to'], unique=False)
    op.create_index(op.f('ix_build_list_parts_added_by'), 'build_list_parts', ['added_by'], unique=False)
    op.create_index(op.f('ix_build_list_parts_build_list_id'), 'build_list_parts', ['build_list_id'], unique=False)
    op.create_index(op.f('ix_build_list_parts_build_list_phase_id'), 'build_list_parts', ['build_list_phase_id'], unique=False)
    op.create_index(op.f('ix_build_list_parts_part_id'), 'build_list_parts', ['part_id'], unique=False)
    op.create_index(op.f('ix_build_list_phases_build_list_id'), 'build_list_phases', ['build_list_id'], unique=False)
    op.create_index(op.f('ix_build_lists_car_id'), 'build_lists', ['car_id'], unique=False)
    op.create_index(op.f('ix_build_lists_user_id'), 'build_lists', ['user_id'], unique=False)
    op.create_index(op.f('ix_build_log_posts_user_id'), 'build_log_posts', ['user_id'], unique=False)
    op.create_index(op.f('ix_crawler_adapter_configs_default_category_id'), 'crawler_adapter_configs', ['default_category_id'], unique=False)
    op.create_index(op.f('ix_parts_category_id'), 'parts', ['category_id'], unique=False)
    op.create_index(op.f('ix_parts_user_id'), 'parts', ['user_id'], unique=False)
    op.create_index(op.f('ix_reports_reviewed_by'), 'reports', ['reviewed_by'], unique=False)


def downgrade() -> None:
    """Downgrade schema — drop the indexes added above."""
    op.drop_index(op.f('ix_reports_reviewed_by'), table_name='reports')
    op.drop_index(op.f('ix_parts_user_id'), table_name='parts')
    op.drop_index(op.f('ix_parts_category_id'), table_name='parts')
    op.drop_index(op.f('ix_crawler_adapter_configs_default_category_id'), table_name='crawler_adapter_configs')
    op.drop_index(op.f('ix_build_log_posts_user_id'), table_name='build_log_posts')
    op.drop_index(op.f('ix_build_lists_user_id'), table_name='build_lists')
    op.drop_index(op.f('ix_build_lists_car_id'), table_name='build_lists')
    op.drop_index(op.f('ix_build_list_phases_build_list_id'), table_name='build_list_phases')
    op.drop_index(op.f('ix_build_list_parts_part_id'), table_name='build_list_parts')
    op.drop_index(op.f('ix_build_list_parts_build_list_phase_id'), table_name='build_list_parts')
    op.drop_index(op.f('ix_build_list_parts_build_list_id'), table_name='build_list_parts')
    op.drop_index(op.f('ix_build_list_parts_added_by'), table_name='build_list_parts')
    op.drop_index(op.f('ix_bug_reports_assigned_to'), table_name='bug_reports')
