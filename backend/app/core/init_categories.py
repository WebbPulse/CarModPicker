"""
Initialize part categories in the database on application startup.

This module ensures that all part categories defined in part_categories_data.py
are present in the database. Source code is the source of truth: existing rows
are updated to match the latest data; new rows are created when missing.
"""

import logging

from app.api.dependencies.repositories import get_repositories
from app.core.part_categories_data import get_all_part_categories
from app.db.dynamo.catalog import Category
from app.db.dynamo.users import UniqueAttributeTaken

logger = logging.getLogger(__name__)

# Fields from source that are synced when updating an existing category
# (only fields defined on PartCategoryData; is_active is not in source, Category defaults to True)
_CATEGORY_SYNC_FIELDS = ("display_name", "description", "icon", "sort_order")


def init_part_categories() -> None:
    """
    Initialize part categories in the database from part_categories_data (source of truth).

    For each category in source:
    - If it already exists (same name): update synced fields to match source.
    - If it does not exist: create it.
    """
    categories = get_repositories().categories

    logger.info("Initializing part categories...")

    all_categories = get_all_part_categories()
    created_count = 0
    updated_count = 0

    for cat_data in all_categories:
        existing = categories.get_by_name(cat_data["name"])
        if existing:
            changes = {key: cat_data.get(key) for key in _CATEGORY_SYNC_FIELDS if key in cat_data}
            if any(getattr(existing, key) != value for key, value in changes.items()):
                categories.update_unique(existing, **changes)
            updated_count += 1
        else:
            try:
                categories.create_unique(Category(**cat_data))
            except UniqueAttributeTaken:
                continue
            created_count += 1

    if created_count > 0:
        logger.info(f"Created {created_count} new part category(ies)")
    if updated_count > 0:
        logger.info(f"Updated {updated_count} part category(ies) to match source of truth")
    if created_count == 0 and updated_count == 0:
        logger.info("No part categories to create or update")
    logger.info("Part category initialization complete")
