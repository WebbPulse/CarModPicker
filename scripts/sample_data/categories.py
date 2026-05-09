"""Sample Category creator."""

import time

from sqlalchemy.orm import Session

from app.api.models.category import Category  # pyright: ignore[reportMissingImports]
from app.core.part_categories_data import (  # pyright: ignore[reportMissingImports]
    get_all_part_categories,
)

from ._logging import log_info, log_section


def create_sample_categories(db: Session) -> list[Category]:
    """Create sample categories from canonical part_categories_data (same as init_categories)."""
    start_time = time.time()
    log_section("Creating sample categories...")

    categories_data = get_all_part_categories()
    categories = []
    created_count = 0
    for cat_data in categories_data:
        # Check if category already exists
        existing = db.query(Category).filter(Category.name == cat_data["name"]).first()
        if existing:
            categories.append(existing)
        else:
            category = Category(**cat_data)
            db.add(category)
            categories.append(category)
            created_count += 1

    db.commit()
    for category in categories:
        db.refresh(category)

    elapsed = time.time() - start_time
    log_info(
        f"✓ Created {created_count:,} new categories, {len(categories):,} total (took {elapsed:.1f}s)"
    )
    return categories
