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
from uuid import UUID

from app.api.dependencies.repositories import Repositories, get_repositories
from app.core.car_generations_data import get_all_car_generations
from app.db.dynamo.catalog import CarGeneration, CarMake, CarModel
from app.db.dynamo.users import UniqueAttributeTaken

logger = logging.getLogger(__name__)

# Fields synced when updating an existing CarGeneration (id, created_at, updated_at, image_urls stay as-is).
# The flattener always emits display_name; None clears a stale DB value.
# Slug is the lookup key, not a synced field — it's set on create and treated as immutable.
_CAR_GENERATION_SYNC_FIELDS = ("generation_name", "start_year", "end_year", "description", "display_name")


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int_or_none(value: object) -> int | None:
    return int(value) if isinstance(value, (int, str)) and str(value).strip() else None


def _get_or_create_make(repos: Repositories, name: str, cache: dict[str, CarMake]) -> CarMake:
    cached = cache.get(name.lower())
    if cached is not None:
        return cached
    make = repos.car_makes.get_by_name(name)
    if make is None:
        try:
            make = repos.car_makes.create_unique(CarMake(name=name))
        except UniqueAttributeTaken:
            make = repos.car_makes.get_by_name(name)
            if make is None:
                raise
    cache[name.lower()] = make
    return make


def init_car_generations() -> None:
    """
    Initialize car generations in the database from car_generations_data (source of truth).

    For each generation in source:
    - Ensure CarMake exists (by name), CarModel exists (car_make_id + slug), and
      CarGeneration exists (car_model_id + slug).
    - On an existing CarModel, sync name and display_name.
    - On an existing CarGeneration, sync the fields in _CAR_GENERATION_SYNC_FIELDS.
    - Otherwise create the row with slug derived from the name (or pinned via source).
    """
    repos = get_repositories()

    logger.info("Initializing car generations...")

    all_generations = get_all_car_generations()
    gen_created = 0
    gen_updated = 0
    model_created = 0
    model_updated = 0
    make_cache: dict[str, CarMake] = {}
    model_cache: dict[tuple[UUID, str], CarModel] = {}
    generation_cache: dict[UUID, dict[str, CarGeneration]] = {}

    for gen_data in all_generations:
        car_make_name = _str_or_none(gen_data["make"]) or ""
        car_model_name = _str_or_none(gen_data["model"]) or ""
        model_slug = _str_or_none(gen_data["model_slug"]) or ""
        model_display_name = _str_or_none(gen_data.get("model_display_name"))
        generation_name = _str_or_none(gen_data["generation_name"]) or ""
        generation_slug = _str_or_none(gen_data["generation_slug"]) or ""

        car_make = _get_or_create_make(repos, car_make_name, make_cache)

        model_key = (car_make.id, model_slug)
        car_model = model_cache.get(model_key)
        if car_model is None:
            car_model = repos.car_models.get_by_make_and_slug(car_make.id, model_slug)
        if car_model is None:
            car_model = repos.car_models.create_unique(
                CarModel(
                    car_make_id=car_make.id,
                    slug=model_slug,
                    name=car_model_name,
                    display_name=model_display_name,
                )
            )
            model_created += 1
        elif car_model.name != car_model_name or car_model.display_name != model_display_name:
            car_model = repos.car_models.update_unique(car_model, name=car_model_name, display_name=model_display_name)
            model_updated += 1
        model_cache[model_key] = car_model

        by_slug = generation_cache.get(car_model.id)
        if by_slug is None:
            by_slug = {gen.slug: gen for gen in repos.car_generations.list_by_model(car_model.id)}
            generation_cache[car_model.id] = by_slug
        existing = by_slug.get(generation_slug)

        if existing:
            changes = {key: gen_data[key] for key in _CAR_GENERATION_SYNC_FIELDS if key in gen_data}
            if any(getattr(existing, key) != value for key, value in changes.items()):
                by_slug[generation_slug] = repos.car_generations.update_unique(existing, **changes)
            gen_updated += 1
        else:
            gen = repos.car_generations.create_unique(
                CarGeneration(
                    car_model_id=car_model.id,
                    slug=generation_slug,
                    generation_name=generation_name,
                    display_name=_str_or_none(gen_data.get("display_name")),
                    start_year=int(str(gen_data["start_year"])),
                    end_year=_int_or_none(gen_data.get("end_year")),
                    description=_str_or_none(gen_data.get("description")),
                )
            )
            by_slug[generation_slug] = gen
            gen_created += 1

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
