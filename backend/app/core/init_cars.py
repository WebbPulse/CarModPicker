"""
Initialize car generations in the database on application startup.

This module ensures that all car generations defined in car_generations_data.py
are present in the database. Source code is the source of truth: existing rows
are updated to match the latest data; new rows are created when missing.

CarMake and CarModel are created/looked up by name; CarGeneration is keyed by
car_model_id + generation_name.
"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.car_generations_data import get_all_car_generations

logger = logging.getLogger(__name__)

# Fields synced when updating an existing CarGeneration (id, created_at, updated_at, image_urls stay as-is)
_CAR_GENERATION_SYNC_FIELDS = ("generation_name", "start_year", "end_year", "description")


def init_car_generations(db: Session) -> None:
    """
    Initialize car generations in the database from car_generations_data (source of truth).

    For each generation in source:
    - Ensure CarMake exists (by name), then CarModel exists (car_make_id + name).
    - If CarGeneration exists for that car_model_id + generation_name: update synced fields.
    - Otherwise create the CarGeneration.
    """
    from app.api.models.car_generation import CarGeneration
    from app.api.models.car_make import CarMake
    from app.api.models.car_model import CarModel

    logger.info("Initializing car generations...")

    # Sync sequences so new inserts get ids above existing max (avoids UniqueViolation
    # when the sequence was never advanced, e.g. after migration backfill with explicit ids).
    db.execute(
        text("SELECT setval(pg_get_serial_sequence('car_makes', 'id'), COALESCE((SELECT MAX(id) FROM car_makes), 1))")
    )
    db.execute(
        text("SELECT setval(pg_get_serial_sequence('car_models', 'id'), COALESCE((SELECT MAX(id) FROM car_models), 1))")
    )
    db.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('car_generations', 'id'),"
            " COALESCE((SELECT MAX(id) FROM car_generations), 1))"
        )
    )

    all_generations = get_all_car_generations()
    created_count = 0
    updated_count = 0

    for gen_data in all_generations:
        car_make_name = gen_data["make"]
        car_model_name = gen_data["model"]

        # Get or create CarMake
        car_make = db.query(CarMake).filter(CarMake.name == car_make_name).first()
        if car_make is None:
            car_make = CarMake(name=car_make_name)
            db.add(car_make)
            db.flush()

        # Get or create CarModel
        car_model = (
            db.query(CarModel).filter(CarModel.car_make_id == car_make.id, CarModel.name == car_model_name).first()
        )
        if car_model is None:
            car_model = CarModel(car_make_id=car_make.id, name=car_model_name)
            db.add(car_model)
            db.flush()

        # Find existing CarGeneration by car_model_id + generation_name
        existing = (
            db.query(CarGeneration)
            .filter(
                CarGeneration.car_model_id == car_model.id,
                CarGeneration.generation_name == gen_data["generation_name"],
            )
            .first()
        )

        if existing:
            for key in _CAR_GENERATION_SYNC_FIELDS:
                if key in gen_data:
                    setattr(existing, key, gen_data[key])
            updated_count += 1
        else:
            gen = CarGeneration(
                car_model_id=car_model.id,
                generation_name=gen_data["generation_name"],
                start_year=gen_data["start_year"],
                end_year=gen_data.get("end_year"),
                description=gen_data.get("description"),
            )
            db.add(gen)
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
