"""add is_curated and created_by_user_id to part_manufacturers

Revision ID: 165ed4efb3bf
Revises: 9aa798d6107e
Create Date: 2026-05-02 18:22:00.266102

Splits PartManufacturer into two visibility classes:

- ``is_curated=True`` (default for all existing rows via the migration's
  server_default backfill) — crawler/admin-created brands. Surfaced in
  catalog list/search/facet UIs.
- ``is_curated=False`` — UGC, scoped to ``created_by_user_id``. Reachable by
  id (no read boundary) but excluded from catalog browse so one user's
  custom "Honda" entry can't pollute everyone else's autocomplete and search.

Replaces the global UNIQUE on ``name`` with two partial unique indexes so
curated names stay globally unique while two different users can each own a
UGC row of the same name.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '165ed4efb3bf'
down_revision: Union[str, None] = '9aa798d6107e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # is_curated defaults to True at the DB level so the column add backfills
    # every existing row in one shot. Decision: pre-existing manufacturers are
    # treated as curated; the only realistic creators so far have been the
    # crawler service account and admins. Drop the server_default after the
    # backfill so future inserts fall back to the model's own default (False
    # for UGC creates from regular users).
    op.add_column(
        'part_manufacturers',
        sa.Column('is_curated', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column('part_manufacturers', 'is_curated', server_default=None)

    op.add_column('part_manufacturers', sa.Column('created_by_user_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('fk_part_manufacturers_created_by_user_id_users'),
        'part_manufacturers',
        'users',
        ['created_by_user_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # Demote the existing global UNIQUE on name to a non-unique index — the
    # uniqueness model is now per visibility class (see partial indexes below).
    op.drop_index(op.f('ix_part_manufacturers_name'), table_name='part_manufacturers')
    op.create_index(op.f('ix_part_manufacturers_name'), 'part_manufacturers', ['name'], unique=False)

    op.create_index(
        op.f('ix_part_manufacturers_created_by_user_id'),
        'part_manufacturers',
        ['created_by_user_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_part_manufacturers_is_curated'),
        'part_manufacturers',
        ['is_curated'],
        unique=False,
    )

    # Pre-dedup case-insensitive duplicates that the old case-sensitive UNIQUE
    # on name allowed (e.g. "Pure" and "PURE" both exist). The new partial
    # unique index uses lower(name) and would reject them. For each collision
    # group, keep the row with the lexicographically smallest id, repoint any
    # parts.part_manufacturer_id from the losers to the winner, then delete
    # the loser rows. Idempotent: empty CTEs when no collisions remain.
    op.execute(
        """
        WITH collisions AS (
            SELECT id, name,
                   first_value(id) OVER (PARTITION BY lower(name) ORDER BY id) AS keep_id
              FROM part_manufacturers
        ),
        losers AS (
            SELECT id, keep_id FROM collisions WHERE id <> keep_id
        ),
        repoint AS (
            UPDATE parts p
               SET part_manufacturer_id = l.keep_id
              FROM losers l
             WHERE p.part_manufacturer_id = l.id
            RETURNING 1
        )
        DELETE FROM part_manufacturers
         WHERE id IN (SELECT id FROM losers);
        """
    )

    # Curated brands: globally unique by case-insensitive name.
    op.create_index(
        'uq_pm_curated_name',
        'part_manufacturers',
        [sa.literal_column('lower(name)')],
        unique=True,
        postgresql_where=sa.text('is_curated IS true'),
        sqlite_where=sa.text('is_curated IS true'),
    )
    # UGC: each user gets at most one row per case-insensitive name. Two
    # different users can both own a "Mishimoto" without collision.
    op.create_index(
        'uq_pm_ugc_per_user',
        'part_manufacturers',
        [sa.literal_column('lower(name)'), 'created_by_user_id'],
        unique=True,
        postgresql_where=sa.text('is_curated IS false'),
        sqlite_where=sa.text('is_curated IS false'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'uq_pm_ugc_per_user',
        table_name='part_manufacturers',
        postgresql_where=sa.text('is_curated IS false'),
        sqlite_where=sa.text('is_curated IS false'),
    )
    op.drop_index(
        'uq_pm_curated_name',
        table_name='part_manufacturers',
        postgresql_where=sa.text('is_curated IS true'),
        sqlite_where=sa.text('is_curated IS true'),
    )
    op.drop_index(op.f('ix_part_manufacturers_is_curated'), table_name='part_manufacturers')
    op.drop_index(op.f('ix_part_manufacturers_created_by_user_id'), table_name='part_manufacturers')
    op.drop_index(op.f('ix_part_manufacturers_name'), table_name='part_manufacturers')
    op.create_index(op.f('ix_part_manufacturers_name'), 'part_manufacturers', ['name'], unique=True)
    op.drop_constraint(
        op.f('fk_part_manufacturers_created_by_user_id_users'),
        'part_manufacturers',
        type_='foreignkey',
    )
    op.drop_column('part_manufacturers', 'created_by_user_id')
    op.drop_column('part_manufacturers', 'is_curated')
