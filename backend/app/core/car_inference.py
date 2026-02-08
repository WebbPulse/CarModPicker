"""
Infer car make / model / generation from part name and description using phrase matching.

Used by the crawler to set car_ids when scraping so parts are associated with the
right car generations (e.g. "MKV Supra A90" -> Toyota Supra A90).

Returns a list of (make, model, generation_name) triples; caller resolves to car IDs
via resolve_car_triples_to_ids().
"""

import re
from typing import TYPE_CHECKING, Optional

from app.core.car_generations_data import CAR_GENERATIONS

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _build_phrase_triples() -> list[tuple[str, str, str, str]]:
    """
    Build (phrase, make, model, generation_name) from canonical data.
    Phrase is normalized (lowercase, single spaces) for matching.
    """
    triples: list[tuple[str, str, str, str]] = []
    for make, models in CAR_GENERATIONS.items():
        for model_data in models:
            model = model_data["model"]
            for gen in model_data["generations"]:
                gen_name = gen["generation_name"]
                # Full phrase: "Toyota Supra A90"
                full = f"{make} {model} {gen_name}".lower()
                triples.append((full, make, model, gen_name))
                # Model + generation: "Supra A90", "M4 G82/G83"
                model_gen = f"{model} {gen_name}".lower()
                triples.append((model_gen, make, model, gen_name))
                # Generation only for short codes (e.g. A90, G82) - add so we can match when context has model
                if len(gen_name) <= 6 and "/" not in gen_name:
                    triples.append((gen_name.lower(), make, model, gen_name))
    return triples


# Aliases: phrase -> (make, model, generation_name). Used when product text uses
# nicknames (MKV Supra, GR Supra, G82, etc.). Order: longer phrases first for specificity.
CAR_ALIASES: list[tuple[str, str, str, str]] = [
    # Toyota Supra A90
    ("mkv supra", "Toyota", "Supra", "A90"),
    ("mk5 supra", "Toyota", "Supra", "A90"),
    ("gr supra", "Toyota", "Supra", "A90"),
    ("supra gr a90", "Toyota", "Supra", "A90"),
    ("supra gr a91", "Toyota", "Supra", "A90"),
    ("a90/a91", "Toyota", "Supra", "A90"),
    ("a90 supra", "Toyota", "Supra", "A90"),
    ("a91 supra", "Toyota", "Supra", "A90"),
    ("mkv toyota supra", "Toyota", "Supra", "A90"),
    ("mkv supra gr", "Toyota", "Supra", "A90"),
    # BMW M4 G82
    ("g82 m4", "BMW", "M4", "G82/G83"),
    ("g83 m4", "BMW", "M4", "G82/G83"),
    ("bmw g82", "BMW", "M4", "G82/G83"),
    ("m4 g82", "BMW", "M4", "G82/G83"),
    ("m4 g83", "BMW", "M4", "G82/G83"),
    # BMW Z4 G29 (current gen; if not in CAR_GENERATIONS, resolve will return no ID)
    ("z4 g29", "BMW", "Z4", "G29"),
    ("bmw z4 g29", "BMW", "Z4", "G29"),
    ("g29 z4", "BMW", "Z4", "G29"),
    # Honda Civic 10th Gen
    ("10th gen civic", "Honda", "Civic", "10th Gen"),
    ("civic 10th gen", "Honda", "Civic", "10th Gen"),
    ("10th gen", "Honda", "Civic", "10th Gen"),  # ambiguous; often Civic in product titles
    # Civic Type R
    ("fk8", "Honda", "Civic Type R", "FK8"),
    ("fk8 civic", "Honda", "Civic Type R", "FK8"),
    ("fl5", "Honda", "Civic Type R", "FL5"),
    # BMW B58 engine cars (multiple; we match "B58" only when Supra/M340i/Z4 etc. in text)
    ("b58 supra", "Toyota", "Supra", "A90"),
    ("supra b58", "Toyota", "Supra", "A90"),
    ("b58 m340", "BMW", "3 Series", "G20/G21"),
]

# Word-boundary for short codes so "A90" doesn't match inside "BA90", and "nd" not inside "random"
_SHORT_PHRASE_MAX_LEN = 8


def _phrase_matches(text: str, phrase: str) -> bool:
    """Return True if phrase appears in text (case-insensitive). Word boundaries for short alphanumeric phrases."""
    if not text or not phrase:
        return False
    lower = text.lower()
    phrase_lower = phrase.lower()
    if phrase_lower not in lower:
        return False
    # For short alphanumeric codes (e.g. A90, G82, ND), require word boundary to avoid false positives
    if len(phrase) <= _SHORT_PHRASE_MAX_LEN and phrase.replace("/", "").replace(" ", "").isalnum():
        return bool(re.search(r"\b" + re.escape(phrase_lower.replace("/", r"/")) + r"\b", lower))
    return True


def infer_car_generations(
    name: Optional[str],
    description: Optional[str],
    product_url: Optional[str] = None,
) -> list[tuple[str, str, str]]:
    """
    Infer (make, model, generation_name) triples from part name, description, and optional URL.

    Returns unique list of triples that can be resolved to car IDs via resolve_car_triples_to_ids().
    Order: aliases first (more specific), then phrase triples from canonical data.
    """
    name = (name or "").strip()
    description = (description or "").strip()
    url = (product_url or "").strip()
    combined = f"{name} {description} {url}".strip()
    if not combined:
        return []

    seen: set[tuple[str, str, str]] = set()
    result: list[tuple[str, str, str]] = []

    # Check aliases first (specific nicknames)
    for phrase, make, model, gen_name in CAR_ALIASES:
        if (make, model, gen_name) in seen:
            continue
        if _phrase_matches(combined, phrase):
            seen.add((make, model, gen_name))
            result.append((make, model, gen_name))

    # Then canonical phrases (from get_all_car_generations); prefer longer matches
    phrase_triples = _build_phrase_triples()
    # Sort by phrase length descending so "toyota supra a90" matches before "supra a90" before "a90"
    phrase_triples.sort(key=lambda x: -len(x[0]))
    for phrase, make, model, gen_name in phrase_triples:
        if (make, model, gen_name) in seen:
            continue
        if _phrase_matches(combined, phrase):
            seen.add((make, model, gen_name))
            result.append((make, model, gen_name))

    return result


def resolve_car_triples_to_ids(
    db: "Session",
    triples: list[tuple[str, str, str]],
) -> list[int]:
    """
    Resolve (make, model, generation_name) triples to car IDs using the database.

    Only returns IDs for cars that exist (Make + CarModel + Car with that generation_name).
    """
    if not triples:
        return []
    from app.api.models.car import Car
    from app.api.models.car_model import CarModel
    from app.api.models.make import Make

    ids: list[int] = []
    seen_ids: set[int] = set()
    for make_name, model_name, gen_name in triples:
        make = db.query(Make).filter(Make.name == make_name).first()
        if not make:
            continue
        car_model = (
            db.query(CarModel)
            .filter(CarModel.make_id == make.id, CarModel.name == model_name)
            .first()
        )
        if not car_model:
            continue
        car = (
            db.query(Car)
            .filter(
                Car.car_model_id == car_model.id,
                Car.generation_name == gen_name,
            )
            .first()
        )
        if car and car.id not in seen_ids:
            seen_ids.add(car.id)
            ids.append(car.id)
    return ids
