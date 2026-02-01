"""
Initialize car generations in the database on application startup.

This module ensures that all car generations defined in car_generations_data.py
are present in the database. Source code is the source of truth: existing rows
are updated to match the latest data; new rows are created when missing.
"""

import logging

from sqlalchemy.orm import Session

from app.core.car_generations_data import get_all_car_generations

logger = logging.getLogger(__name__)

# Fields from source data that are synced when updating an existing car (id, created_at, updated_at, image_url stay as-is)
_CAR_SYNC_FIELDS = ("make", "model", "generation_name", "start_year", "end_year", "description")


def init_car_generations(db: Session) -> None:
    """
    Initialize car generations in the database from car_generations_data (source of truth).

    For each generation in source:
    - If it already exists (same make, model, generation_name): update all synced fields to match source.
    - If it does not exist: create it.
    """
    from app.api.models.car import Car

    logger.info("Initializing car generations...")

    all_generations = get_all_car_generations()
    created_count = 0
    updated_count = 0

    for gen_data in all_generations:
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
            # Overwrite with latest source of truth (only synced fields; id, created_at, image_url preserved)
            for key in _CAR_SYNC_FIELDS:
                if key in gen_data:
                    setattr(existing, key, gen_data[key])
            updated_count += 1
        else:
            car = Car(**gen_data)
            db.add(car)
            created_count += 1

    if created_count > 0 or updated_count > 0:
        db.commit()
    if created_count > 0:
        logger.info(f"Created {created_count} new car generation(s)")
    if updated_count > 0:
        logger.info(f"Updated {updated_count} car generation(s) to match source of truth")
    if created_count == 0 and updated_count == 0:
        logger.info("No car generations to create or update")
    logger.info("Car generation initialization complete")
