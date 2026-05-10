"""Sample CarGeneration creator (also seeds CarMake / CarModel)."""

import time

from sqlalchemy.orm import Session

from app.api.models.car_generation import CarGeneration  # pyright: ignore[reportMissingImports]
from app.api.models.car_make import CarMake  # pyright: ignore[reportMissingImports]
from app.api.models.car_model import CarModel  # pyright: ignore[reportMissingImports]
from app.core.car_generations_data import (  # pyright: ignore[reportMissingImports]
    get_all_car_generations,
)

from ._logging import log_info, log_section


def create_sample_cars(db: Session) -> list[CarGeneration]:
    """Create sample centrally managed car generations using the canonical data source.
    Uses CarMake and CarModel entities; same logic as init_car_generations.
    """
    start_time = time.time()
    log_section("Creating sample car generations...")

    cars_data = get_all_car_generations()
    cars: list[CarGeneration] = []
    created_count = 0
    skipped_count = 0

    for car_data in cars_data:
        make_name = car_data["make"]
        model_name = car_data["model"]

        # Get or create CarMake
        make_entity = db.query(CarMake).filter(CarMake.name == make_name).first()
        if make_entity is None:
            make_entity = CarMake(name=make_name)
            db.add(make_entity)
            db.flush()

        # Get or create CarModel
        car_model_entity = (
            db.query(CarModel)
            .filter(CarModel.car_make_id == make_entity.id, CarModel.name == model_name)
            .first()
        )
        if car_model_entity is None:
            car_model_entity = CarModel(car_make_id=make_entity.id, name=model_name)
            db.add(car_model_entity)
            db.flush()

        # Check if car generation already exists
        existing = (
            db.query(CarGeneration)
            .filter(
                CarGeneration.car_model_id == car_model_entity.id,
                CarGeneration.generation_name == car_data["generation_name"],
            )
            .first()
        )
        if existing:
            cars.append(existing)
            skipped_count += 1
        else:
            car = CarGeneration(
                car_model_id=car_model_entity.id,
                generation_name=car_data["generation_name"],
                start_year=car_data["start_year"],
                end_year=car_data.get("end_year"),
                description=car_data.get("description"),
            )
            db.add(car)
            cars.append(car)
            created_count += 1

    db.commit()
    for car in cars:
        db.refresh(car)

    elapsed = time.time() - start_time
    log_info(
        f"✓ Created {created_count:,} new car generations, skipped {skipped_count:,} existing, {len(cars):,} total (took {elapsed:.1f}s)"
    )
    return cars
