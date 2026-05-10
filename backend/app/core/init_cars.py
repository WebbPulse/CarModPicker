"""
Initialize car generations in the database on application startup.

Source code (car_generations_data.py) is the source of truth for CarMake, CarModel,
and CarGeneration. Existing rows are updated to match seed data; new rows are created
when missing. Rows that have drifted out of source are left in place (FK refs may still
point at them — deleting is a manual operation).

Lookup keys are stable **slugs**, not display-level names:
- CarModel: (car_make_id, slug)
- CarGeneration: (car_model_id, slug)

Slugs default to slugify(name) / slugify(generation_name). To rename a name in seed
without creating a duplicate row, pin the `slug` field in the source dict to the original
slugified form; the existing row will be found and its `name` (or `generation_name`)
updated in place.

Synced fields — overwritten on every startup from source. Manual DB edits to these fields
will be clobbered on next boot:
- CarMake: name (by current lookup; lookup key)
- CarModel: name, display_name
- CarGeneration: generation_name, start_year, end_year, description, display_name

Not synced — safe for admin curation:
- CarGeneration.image_urls
- created_at / updated_at / id
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.car_generations_data import get_all_car_generations

logger = logging.getLogger(__name__)

# Fields synced when updating an existing CarGeneration (id, created_at, updated_at, image_urls stay as-is).
# The flattener always emits display_name; None clears a stale DB value.
# Slug is the lookup key, not a synced field — it's set on create and treated as immutable.
_CAR_GENERATION_SYNC_FIELDS = ("generation_name", "start_year", "end_year", "description", "display_name")


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def init_car_generations(db: Session) -> None:
    """
    Initialize car generations in the database from car_generations_data (source of truth).

    For each generation in source:
    - Ensure CarMake exists (by name), CarModel exists (car_make_id + slug), and
      CarGeneration exists (car_model_id + slug).
    - On an existing CarModel, sync name and display_name.
    - On an existing CarGeneration, sync the fields in _CAR_GENERATION_SYNC_FIELDS.
    - Otherwise create the row with slug derived from the name (or pinned via source).
    """
    from app.api.models.car_generation import CarGeneration
    from app.api.models.car_make import CarMake
    from app.api.models.car_model import CarModel

    logger.info("Initializing car generations...")

    all_generations = get_all_car_generations()
    gen_created = 0
    gen_updated = 0
    model_created = 0
    model_updated = 0

    for gen_data in all_generations:
        car_make_name = _str_or_none(gen_data["make"]) or ""
        car_model_name = _str_or_none(gen_data["model"]) or ""
        model_slug = _str_or_none(gen_data["model_slug"]) or ""
        model_display_name = _str_or_none(gen_data.get("model_display_name"))
        generation_name = _str_or_none(gen_data["generation_name"]) or ""
        generation_slug = _str_or_none(gen_data["generation_slug"]) or ""

        # Get or create CarMake (still by name — makes are identity-stable and few).
        car_make = db.scalars(select(CarMake).where(CarMake.name == car_make_name)).first()
        if car_make is None:
            car_make = CarMake(name=car_make_name)
            db.add(car_make)
            db.flush()

        # Get or create CarModel by (make_id, slug). Name/display_name are synced fields.
        car_model = db.scalars(
            select(CarModel).where(CarModel.car_make_id == car_make.id, CarModel.slug == model_slug)
        ).first()
        if car_model is None:
            car_model = CarModel(
                car_make_id=car_make.id,
                slug=model_slug,
                name=car_model_name,
                display_name=model_display_name,
            )
            db.add(car_model)
            db.flush()
            model_created += 1
        else:
            changed = False
            if car_model.name != car_model_name:
                car_model.name = car_model_name
                changed = True
            if car_model.display_name != model_display_name:
                car_model.display_name = model_display_name
                changed = True
            if changed:
                model_updated += 1

        # Get or create CarGeneration by (model_id, slug).
        existing = db.scalars(
            select(CarGeneration).where(
                CarGeneration.car_model_id == car_model.id,
                CarGeneration.slug == generation_slug,
            )
        ).first()

        if existing:
            for key in _CAR_GENERATION_SYNC_FIELDS:
                if key in gen_data:
                    setattr(existing, key, gen_data[key])
            gen_updated += 1
        else:
            gen = CarGeneration(
                car_model_id=car_model.id,
                slug=generation_slug,
                generation_name=generation_name,
                display_name=_str_or_none(gen_data.get("display_name")),
                start_year=gen_data["start_year"],
                end_year=gen_data.get("end_year"),
                description=_str_or_none(gen_data.get("description")),
            )
            db.add(gen)
            gen_created += 1

    if gen_created or gen_updated or model_created or model_updated:
        db.commit()
    if model_created:
        logger.info(f"Created {model_created} new car model(s)")
    if model_updated:
        logger.info(f"Updated {model_updated} car model(s) to match source of truth")
    if gen_created:
        logger.info(f"Created {gen_created} new car generation(s)")
    if gen_updated:
        logger.info(f"Updated {gen_updated} car generation(s) to match source of truth")
    if not (gen_created or gen_updated or model_created or model_updated):
        logger.info("No car models or generations to create or update")
    logger.info("Car generation initialization complete")
