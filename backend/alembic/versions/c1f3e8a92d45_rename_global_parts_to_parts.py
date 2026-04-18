"""rename global_parts to parts

Revision ID: c1f3e8a92d45
Revises: a7b5e43f2000
Create Date: 2026-04-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "c1f3e8a92d45"
down_revision: Union[str, None] = "5a381dff5fd1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename tables
    op.rename_table("global_parts", "parts")
    op.rename_table("global_part_cars", "part_cars")

    # Rename FK columns in join/child tables
    op.alter_column("part_cars", "global_part_id", new_column_name="part_id")
    op.alter_column("build_list_parts", "global_part_id", new_column_name="part_id")
    op.alter_column("part_listings", "global_part_id", new_column_name="part_id")
    op.alter_column("crawled_pages", "global_part_id", new_column_name="part_id")

    # Rename indexes (Postgres does not auto-rename on table/column rename)
    op.execute("ALTER INDEX ix_global_parts_id RENAME TO ix_parts_id")
    op.execute("ALTER INDEX ix_global_parts_name RENAME TO ix_parts_name")
    op.execute("ALTER INDEX ix_global_parts_gtin RENAME TO ix_parts_gtin")
    op.execute("ALTER INDEX ix_global_parts_brand_id RENAME TO ix_parts_brand_id")
    op.execute("ALTER INDEX ix_part_listings_global_part_id RENAME TO ix_part_listings_part_id")
    op.execute("ALTER INDEX ix_crawled_pages_global_part_id RENAME TO ix_crawled_pages_part_id")

    # Rename PK constraints
    op.execute("ALTER TABLE parts RENAME CONSTRAINT global_parts_pkey TO parts_pkey")
    op.execute("ALTER TABLE part_cars RENAME CONSTRAINT global_part_cars_pkey TO part_cars_pkey")

    # Rename FK constraints
    op.execute("ALTER TABLE parts RENAME CONSTRAINT global_parts_user_id_fkey TO parts_user_id_fkey")
    op.execute("ALTER TABLE parts RENAME CONSTRAINT global_parts_category_id_fkey TO parts_category_id_fkey")
    op.execute("ALTER TABLE parts RENAME CONSTRAINT global_parts_brand_id_fkey TO parts_brand_id_fkey")
    op.execute("ALTER TABLE part_cars RENAME CONSTRAINT global_part_cars_global_part_id_fkey TO part_cars_part_id_fkey")
    op.execute("ALTER TABLE part_cars RENAME CONSTRAINT global_part_cars_car_id_fkey TO part_cars_car_id_fkey")
    op.execute("ALTER TABLE build_list_parts RENAME CONSTRAINT build_list_parts_global_part_id_fkey TO build_list_parts_part_id_fkey")
    op.execute("ALTER TABLE part_listings RENAME CONSTRAINT part_listings_global_part_id_fkey TO part_listings_part_id_fkey")
    op.execute("ALTER TABLE crawled_pages RENAME CONSTRAINT crawled_pages_global_part_id_fkey TO crawled_pages_part_id_fkey")

    # Rename unique constraint
    op.execute("ALTER TABLE part_listings RENAME CONSTRAINT uq_part_listing_global_part_retailer TO uq_part_listing_part_retailer")

    # Migrate polymorphic entity_type strings stored as data
    op.execute("UPDATE votes SET entity_type = 'part' WHERE entity_type = 'global_part'")
    op.execute("UPDATE reports SET entity_type = 'part' WHERE entity_type = 'global_part'")


def downgrade() -> None:
    # Reverse entity_type data migration
    op.execute("UPDATE votes SET entity_type = 'global_part' WHERE entity_type = 'part'")
    op.execute("UPDATE reports SET entity_type = 'global_part' WHERE entity_type = 'part'")

    # Reverse unique constraint rename
    op.execute("ALTER TABLE part_listings RENAME CONSTRAINT uq_part_listing_part_retailer TO uq_part_listing_global_part_retailer")

    # Reverse FK constraint renames
    op.execute("ALTER TABLE crawled_pages RENAME CONSTRAINT crawled_pages_part_id_fkey TO crawled_pages_global_part_id_fkey")
    op.execute("ALTER TABLE part_listings RENAME CONSTRAINT part_listings_part_id_fkey TO part_listings_global_part_id_fkey")
    op.execute("ALTER TABLE build_list_parts RENAME CONSTRAINT build_list_parts_part_id_fkey TO build_list_parts_global_part_id_fkey")
    op.execute("ALTER TABLE part_cars RENAME CONSTRAINT part_cars_car_id_fkey TO global_part_cars_car_id_fkey")
    op.execute("ALTER TABLE part_cars RENAME CONSTRAINT part_cars_part_id_fkey TO global_part_cars_global_part_id_fkey")
    op.execute("ALTER TABLE parts RENAME CONSTRAINT parts_brand_id_fkey TO global_parts_brand_id_fkey")
    op.execute("ALTER TABLE parts RENAME CONSTRAINT parts_category_id_fkey TO global_parts_category_id_fkey")
    op.execute("ALTER TABLE parts RENAME CONSTRAINT parts_user_id_fkey TO global_parts_user_id_fkey")

    # Reverse PK constraint renames
    op.execute("ALTER TABLE part_cars RENAME CONSTRAINT part_cars_pkey TO global_part_cars_pkey")
    op.execute("ALTER TABLE parts RENAME CONSTRAINT parts_pkey TO global_parts_pkey")

    # Reverse index renames
    op.execute("ALTER INDEX ix_crawled_pages_part_id RENAME TO ix_crawled_pages_global_part_id")
    op.execute("ALTER INDEX ix_part_listings_part_id RENAME TO ix_part_listings_global_part_id")
    op.execute("ALTER INDEX ix_parts_brand_id RENAME TO ix_global_parts_brand_id")
    op.execute("ALTER INDEX ix_parts_gtin RENAME TO ix_global_parts_gtin")
    op.execute("ALTER INDEX ix_parts_name RENAME TO ix_global_parts_name")
    op.execute("ALTER INDEX ix_parts_id RENAME TO ix_global_parts_id")

    # Restore FK column names
    op.alter_column("crawled_pages", "part_id", new_column_name="global_part_id")
    op.alter_column("part_listings", "part_id", new_column_name="global_part_id")
    op.alter_column("build_list_parts", "part_id", new_column_name="global_part_id")
    op.alter_column("part_cars", "part_id", new_column_name="global_part_id")

    # Restore table names
    op.rename_table("part_cars", "global_part_cars")
    op.rename_table("parts", "global_parts")
