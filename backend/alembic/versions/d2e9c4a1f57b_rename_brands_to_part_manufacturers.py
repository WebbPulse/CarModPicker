"""rename brands to part_manufacturers

Revision ID: d2e9c4a1f57b
Revises: c1f3e8a92d45
Create Date: 2026-04-17 00:10:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "d2e9c4a1f57b"
down_revision: Union[str, None] = "c1f3e8a92d45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename table
    op.rename_table("brands", "part_manufacturers")

    # Rename FK column on parts
    op.alter_column("parts", "brand_id", new_column_name="part_manufacturer_id")

    # Rename indexes so names line up with the new table/column
    op.execute("ALTER INDEX ix_brands_id RENAME TO ix_part_manufacturers_id")
    op.execute("ALTER INDEX ix_brands_name RENAME TO ix_part_manufacturers_name")
    op.execute("ALTER INDEX ix_parts_brand_id RENAME TO ix_parts_part_manufacturer_id")

    # Rename PK and FK constraints (Postgres does not auto-rename on table/column rename)
    op.execute("ALTER TABLE part_manufacturers RENAME CONSTRAINT brands_pkey TO part_manufacturers_pkey")
    op.execute("ALTER TABLE parts RENAME CONSTRAINT parts_brand_id_fkey TO parts_part_manufacturer_id_fkey")


def downgrade() -> None:
    op.execute("ALTER TABLE parts RENAME CONSTRAINT parts_part_manufacturer_id_fkey TO parts_brand_id_fkey")
    op.execute("ALTER TABLE part_manufacturers RENAME CONSTRAINT part_manufacturers_pkey TO brands_pkey")

    op.execute("ALTER INDEX ix_parts_part_manufacturer_id RENAME TO ix_parts_brand_id")
    op.execute("ALTER INDEX ix_part_manufacturers_name RENAME TO ix_brands_name")
    op.execute("ALTER INDEX ix_part_manufacturers_id RENAME TO ix_brands_id")

    op.alter_column("parts", "part_manufacturer_id", new_column_name="brand_id")
    op.rename_table("part_manufacturers", "brands")
