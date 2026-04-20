"""add slug to car_models and car_generations

Revision ID: 30e2e2139a2e
Revises: 6d5d757e47a8
Create Date: 2026-04-18 18:14:23.793063

"""
import re
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '30e2e2139a2e'
down_revision: Union[str, None] = '6d5d757e47a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slugify(value: str) -> str:
    """Mirrors app.core.car_generations_data.slugify — kept inline to keep migrations standalone."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def upgrade() -> None:
    """Upgrade schema."""
    # Add nullable first, backfill, then enforce NOT NULL + uniqueness. This pattern survives
    # existing-data DBs; a fresh DB with 0 rows degenerates to a plain NOT NULL add.
    op.add_column('car_models', sa.Column('slug', sa.String(), nullable=True))
    op.add_column('car_generations', sa.Column('slug', sa.String(), nullable=True))

    bind = op.get_bind()

    # Backfill CarModel.slug = slugify(name). name is already unique per car_make_id, so
    # slugify is unique per car_make_id too (verified via seed-data collision sweep).
    for row_id, name in bind.execute(sa.text("SELECT id, name FROM car_models")).all():
        bind.execute(
            sa.text("UPDATE car_models SET slug = :slug WHERE id = :id"),
            {"slug": _slugify(name), "id": row_id},
        )

    # Backfill CarGeneration.slug = slugify(generation_name), scoped per model.
    for row_id, gen_name in bind.execute(
        sa.text("SELECT id, generation_name FROM car_generations")
    ).all():
        bind.execute(
            sa.text("UPDATE car_generations SET slug = :slug WHERE id = :id"),
            {"slug": _slugify(gen_name), "id": row_id},
        )

    # Drop any car_generations rows that would collide on (car_model_id, slug) once the unique
    # constraint is applied. Historically seed data may have inserted rows with identical
    # generation_name scoped to the same model (e.g. three "Vanquish" rows for different eras).
    # init_cars re-seeds cleanly on next startup using the slugs now pinned in source.
    bind.execute(
        sa.text(
            """
            DELETE FROM car_generations
            WHERE (car_model_id, slug) IN (
                SELECT car_model_id, slug
                FROM car_generations
                GROUP BY car_model_id, slug
                HAVING COUNT(*) > 1
            )
            """
        )
    )

    op.alter_column('car_models', 'slug', nullable=False)
    op.alter_column('car_generations', 'slug', nullable=False)

    op.create_index(op.f('ix_car_models_slug'), 'car_models', ['slug'], unique=False)
    op.create_unique_constraint('uq_car_models_car_make_id_slug', 'car_models', ['car_make_id', 'slug'])
    op.create_index(op.f('ix_car_generations_slug'), 'car_generations', ['slug'], unique=False)
    op.create_unique_constraint(
        'uq_car_generations_car_model_id_slug', 'car_generations', ['car_model_id', 'slug']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_car_models_car_make_id_slug', 'car_models', type_='unique')
    op.drop_index(op.f('ix_car_models_slug'), table_name='car_models')
    op.drop_column('car_models', 'slug')
    op.drop_constraint('uq_car_generations_car_model_id_slug', 'car_generations', type_='unique')
    op.drop_index(op.f('ix_car_generations_slug'), table_name='car_generations')
    op.drop_column('car_generations', 'slug')
