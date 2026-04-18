"""rename global_parts to parts

Revision ID: c1f3e8a92d45
Revises: a7b5e43f2000
Create Date: 2026-04-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "c1f3e8a92d45"
down_revision: Union[str, None] = "a7b5e43f2000"
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

    # Migrate polymorphic entity_type strings stored as data
    op.execute("UPDATE votes SET entity_type = 'part' WHERE entity_type = 'global_part'")
    op.execute("UPDATE reports SET entity_type = 'part' WHERE entity_type = 'global_part'")


def downgrade() -> None:
    # Reverse entity_type data migration
    op.execute("UPDATE votes SET entity_type = 'global_part' WHERE entity_type = 'part'")
    op.execute("UPDATE reports SET entity_type = 'global_part' WHERE entity_type = 'part'")

    # Restore FK column names
    op.alter_column("crawled_pages", "part_id", new_column_name="global_part_id")
    op.alter_column("part_listings", "part_id", new_column_name="global_part_id")
    op.alter_column("build_list_parts", "part_id", new_column_name="global_part_id")
    op.alter_column("part_cars", "part_id", new_column_name="global_part_id")

    # Restore table names
    op.rename_table("part_cars", "global_part_cars")
    op.rename_table("parts", "global_parts")
