"""
Initialize car generations in the database on application startup.

This module ensures that all car generations defined in car_generations_data.py
are present in the database. It only creates new entries and skips existing ones,
preserving any manual edits that have been made to existing cars.
"""

import logging

from sqlalchemy.orm import Session

from app.core.car_generations_data import get_all_car_generations

logger = logging.getLogger(__name__)


def init_car_generations(db: Session) -> None:
    """
    Initialize car generations in the database.

    This function:
    1. Retrieves all car generation definitions from car_generations_data
    2. Checks if each generation already exists in the database
    3. Creates new generations that don't exist
    4. Skips existing generations entirely (preserves manual edits)
    5. Logs the results

    Args:
        db: Database session
    """
    from app.api.models.car import Car

    logger.info("Initializing car generations...")

    all_generations = get_all_car_generations()
    created_count = 0
    skipped_count = 0

    for gen_data in all_generations:
        # Check if car generation already exists
        existing = (
            db.query(Car)
            .filter(
                Car.make == gen_data["make"],
                Car.model == gen_data["model"],
                Car.generation_name == gen_data["generation_name"],
            )
            .first()
        )

        if existing:
            # Skip existing cars to preserve manual edits
            skipped_count += 1
            continue

        # Create new car generation
        car = Car(**gen_data)
        db.add(car)
        created_count += 1

    # Commit all changes at once
    if created_count > 0:
        db.commit()
        logger.info(f"Created {created_count} new car generation(s)")
    else:
        logger.info("No new car generations to create")

    if skipped_count > 0:
        logger.info(f"Skipped {skipped_count} car generation(s) (already exist, preserving manual edits)")

    logger.info("Car generation initialization complete")
