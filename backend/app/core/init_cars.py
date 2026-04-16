"""
Initialize car generations in the database on application startup.

This module ensures that all car generations defined in car_generations_data.py
are present in the database. Source code is the source of truth: existing rows
are updated to match the latest data; new rows are created when missing.

Make and CarModel are created/looked up by name; Car (generation) is keyed by
car_model_id + generation_name.
"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.car_generations_data import get_all_car_generations

logger = logging.getLogger(__name__)

# Fields from source data that are synced when updating an existing car (id, created_at, updated_at, image_urls stay as-is)
_CAR_SYNC_FIELDS = ("generation_name", "start_year", "end_year", "description")


def init_car_generations(db: Session) -> None:
    """
    Initialize car generations in the database from car_generations_data (source of truth).

    For each generation in source:
    - Ensure Make exists (by name), then CarModel exists (make_id + name).
    - If Car exists for that car_model_id + generation_name: update synced fields.
    - Otherwise create the Car.
    """
    from app.api.models.car import Car
    from app.api.models.car_model import CarModel
    from app.api.models.make import Make

    logger.info("Initializing car generations...")

    # Sync sequences so new inserts get ids above existing max (avoids UniqueViolation
    # when the sequence was never advanced, e.g. after migration backfill with explicit ids).
    db.execute(text("SELECT setval(pg_get_serial_sequence('makes', 'id'), COALESCE((SELECT MAX(id) FROM makes), 1))"))
    db.execute(
        text("SELECT setval(pg_get_serial_sequence('car_models', 'id'), COALESCE((SELECT MAX(id) FROM car_models), 1))")
    )
    db.execute(text("SELECT setval(pg_get_serial_sequence('cars', 'id'), COALESCE((SELECT MAX(id) FROM cars), 1))"))

    all_generations = get_all_car_generations()
    created_count = 0
    updated_count = 0

    for gen_data in all_generations:
        make_name = gen_data["make"]
        model_name = gen_data["model"]

        # Get or create Make
        make = db.query(Make).filter(Make.name == make_name).first()
        if make is None:
            make = Make(name=make_name)
            db.add(make)
            db.flush()

        # Get or create CarModel
        car_model = db.query(CarModel).filter(CarModel.make_id == make.id, CarModel.name == model_name).first()
        if car_model is None:
            car_model = CarModel(make_id=make.id, name=model_name)
            db.add(car_model)
            db.flush()

        # Find existing Car by car_model_id + generation_name
        existing = (
            db.query(Car)
            .filter(
                Car.car_model_id == car_model.id,
                Car.generation_name == gen_data["generation_name"],
            )
            .first()
        )

        if existing:
            for key in _CAR_SYNC_FIELDS:
                if key in gen_data:
                    setattr(existing, key, gen_data[key])
            updated_count += 1
        else:
            car = Car(
                car_model_id=car_model.id,
                generation_name=gen_data["generation_name"],
                start_year=gen_data["start_year"],
                end_year=gen_data.get("end_year"),
                description=gen_data.get("description"),
            )
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
