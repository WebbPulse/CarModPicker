"""rename make to car_make and car to car_generation

Revision ID: e3f4b1c08a91
Revises: d2e9c4a1f57b
Create Date: 2026-04-17 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "e3f4b1c08a91"
down_revision: Union[str, None] = "d2e9c4a1f57b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename tables
    op.rename_table("makes", "car_makes")
    op.rename_table("cars", "car_generations")

    # Rename FK column on car_models
    op.alter_column("car_models", "make_id", new_column_name="car_make_id")

    # Rename indexes so names line up with new tables/columns
    op.execute("ALTER INDEX ix_makes_id RENAME TO ix_car_makes_id")
    op.execute("ALTER INDEX ix_makes_name RENAME TO ix_car_makes_name")
    op.execute("ALTER INDEX ix_cars_id RENAME TO ix_car_generations_id")
    op.execute("ALTER INDEX ix_cars_car_model_id RENAME TO ix_car_generations_car_model_id")
    op.execute("ALTER INDEX ix_car_models_make_id RENAME TO ix_car_models_car_make_id")

    # Rename PK, unique, and FK constraints (Postgres does not auto-rename on table/column rename)
    op.execute("ALTER TABLE car_makes RENAME CONSTRAINT makes_pkey TO car_makes_pkey")
    op.execute("ALTER TABLE car_generations RENAME CONSTRAINT cars_pkey TO car_generations_pkey")
    op.execute("ALTER TABLE car_models RENAME CONSTRAINT uq_car_models_make_id_name TO uq_car_models_car_make_id_name")
    op.execute("ALTER TABLE car_models RENAME CONSTRAINT car_models_make_id_fkey TO car_models_car_make_id_fkey")
    op.execute(
        "ALTER TABLE car_generations RENAME CONSTRAINT cars_car_model_id_fkey TO car_generations_car_model_id_fkey"
    )

    # Update polymorphic vote entity_type discriminator
    op.execute("UPDATE votes SET entity_type = 'car_generation' WHERE entity_type = 'car'")


def downgrade() -> None:
    op.execute("UPDATE votes SET entity_type = 'car' WHERE entity_type = 'car_generation'")

    op.execute(
        "ALTER TABLE car_generations RENAME CONSTRAINT car_generations_car_model_id_fkey TO cars_car_model_id_fkey"
    )
    op.execute("ALTER TABLE car_models RENAME CONSTRAINT car_models_car_make_id_fkey TO car_models_make_id_fkey")
    op.execute("ALTER TABLE car_models RENAME CONSTRAINT uq_car_models_car_make_id_name TO uq_car_models_make_id_name")
    op.execute("ALTER TABLE car_generations RENAME CONSTRAINT car_generations_pkey TO cars_pkey")
    op.execute("ALTER TABLE car_makes RENAME CONSTRAINT car_makes_pkey TO makes_pkey")

    op.execute("ALTER INDEX ix_car_models_car_make_id RENAME TO ix_car_models_make_id")
    op.execute("ALTER INDEX ix_car_generations_car_model_id RENAME TO ix_cars_car_model_id")
    op.execute("ALTER INDEX ix_car_generations_id RENAME TO ix_cars_id")
    op.execute("ALTER INDEX ix_car_makes_name RENAME TO ix_makes_name")
    op.execute("ALTER INDEX ix_car_makes_id RENAME TO ix_makes_id")

    op.alter_column("car_models", "car_make_id", new_column_name="make_id")

    op.rename_table("car_generations", "cars")
    op.rename_table("car_makes", "makes")
