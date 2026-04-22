"""
Car generation data for popular modern cars since the 70s.

Thin shim preserving the public API of the old 8,412-line module.

The large CAR_GENERATIONS literal now lives in car_generations_data.json and is
loaded lazily via car_generations.load_car_generations(). Callers see no behavior
change: `slugify`, `CarGenerationData`, `CarModelData`, `CAR_GENERATIONS`, and
`get_all_car_generations()` are all still importable from this module.

To add a new car generation:
1. Edit car_generations_data.json (or the source you regenerate it from)
2. Re-run `python scripts/export_car_generations.py` if editing via Python
3. The initialization logic will automatically create it in the database
"""
from __future__ import annotations

import re
from typing import Any, TypedDict

from typing_extensions import NotRequired

from app.core.car_generations import load_car_generations


def slugify(value: str) -> str:
    """
    Convert a name into a stable, url-safe slug used for init_cars lookup.

    Lowercases, collapses non-alphanumeric runs into single hyphens, and trims
    leading/trailing hyphens. "Mk5 Supra" → "mk5-supra", "RX-7" → "rx-7",
    "SA/FB" → "sa-fb", "911 (992)" → "911-992".
    """
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


class CarGenerationData(TypedDict):
    """Type definition for car generation data."""

    generation_name: str
    start_year: int
    end_year: int | None  # None for current/ongoing generations
    description: NotRequired[str]  # Optional field
    # Consumer-friendly label (e.g. "Mk4 Supra" for A80). Presentation-only — never used by inference.
    display_name: NotRequired[str]
    # Optional stable slug override. Pin to the old slugify(generation_name) when renaming
    # `generation_name` in seed to preserve the existing DB row instead of creating a duplicate.
    # When absent, init_cars uses slugify(generation_name).
    slug: NotRequired[str]


class CarModelData(TypedDict):
    """Type definition for car model data."""

    model: str
    generations: list[CarGenerationData]
    # Consumer-friendly model label. Presentation-only — never used by inference.
    model_display_name: NotRequired[str]
    # Optional stable slug override. Pin to the old slugify(model) when renaming `model` in seed
    # to preserve the existing DB row. When absent, init_cars uses slugify(model).
    slug: NotRequired[str]


# Module-level CAR_GENERATIONS is now exposed lazily via __getattr__ so importing
# this shim no longer eagerly parses the ~hundreds-of-ms JSON asset (WR-01 / D-28).
# The first attribute access invokes load_car_generations(), which is @lru_cache'd —
# subsequent accesses return the same dict without re-parsing.
# WARNING: Callers MUST NOT mutate the returned dict (see Pitfall JS-01 in 03-RESEARCH.md).
# @lru_cache returns the SAME object on every call; mutation would leak across callers.
def __getattr__(name: str) -> Any:
    """Defer the JSON load until CAR_GENERATIONS is actually accessed (PEP 562).

    Re-exporting via `from app.core.car_generations_data import CAR_GENERATIONS`
    triggers this hook on first access; the returned dict is the @lru_cache'd
    output of load_car_generations(), so identity comparisons against the
    loader's result still hold.
    """
    if name == "CAR_GENERATIONS":
        return load_car_generations()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_all_car_generations() -> list[dict[str, str | int | None]]:
    """
    Flatten the nested car generations structure into a flat list.

    Returns:
        List of dictionaries with make, model, model_slug, generation_name, generation_slug,
        start_year, end_year, and optionally description, display_name, model_display_name.

    Slug semantics: every row always has "model_slug" and "generation_slug" keys, non-None.
    These are the stable lookup keys used by init_cars. They default to slugify(model) /
    slugify(generation_name) but can be pinned via explicit "slug" in the source dict to
    survive a name rename.

    Tri-state semantics: every row always has "display_name" and "model_display_name" keys.
    The value is None when no friendly name is defined in source — init_cars uses that
    explicit None to clear any stale DB value (rather than leaving it in place).
    """
    generations: list[dict[str, str | int | None]] = []
    for make, models in load_car_generations().items():
        for model_data in models:
            model = model_data["model"]
            model_display_name = model_data.get("model_display_name")
            model_slug = model_data.get("slug") or slugify(model)
            for gen in model_data["generations"]:
                gen_dict: dict[str, str | int | None] = {
                    "make": make,
                    "model": model,
                    "model_slug": model_slug,
                    "model_display_name": model_display_name,
                    "generation_name": gen["generation_name"],
                    "generation_slug": gen.get("slug") or slugify(gen["generation_name"]),
                    "display_name": gen.get("display_name"),
                    "start_year": gen["start_year"],
                    "end_year": gen["end_year"],
                }
                if "description" in gen:
                    gen_dict["description"] = gen["description"]
                generations.append(gen_dict)
    return generations
