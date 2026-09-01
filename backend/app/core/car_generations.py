"""Lazy JSON loader for car-generations data (QUAL-01).

Per-make JSON assets live in car_generations_seed/ (package-adjacent), one
file per make. First call reads+parses every file once and merges into a
single dict; subsequent calls return the memoized dict reference.

WARNING: Callers MUST NOT mutate the returned dict — @lru_cache returns the
same object reference on every call (see Pitfall JS-01 in 03-RESEARCH.md).
"""

from __future__ import annotations

import functools
import json
from importlib.resources import files


@functools.lru_cache(maxsize=1)
def load_car_generations() -> dict:
    """Load and memoize the merged car-generations dict from car_generations_seed/.

    Each per-make file is a single-key JSON object: {"<Make>": [...models]}.
    The loader globs *.json under the seed directory and merges into one dict.
    Make-level keys must be unique across files (verified by an assertion).
    """
    seed_dir = files("app.core").joinpath("car_generations_seed")
    merged: dict = {}
    for entry in sorted(seed_dir.iterdir(), key=lambda p: p.name):
        if not entry.name.endswith(".json"):
            continue
        payload = json.loads(entry.read_text(encoding="utf-8"))
        for make, models in payload.items():
            assert make not in merged, (
                f"Duplicate make key '{make}' across seed files " f"(found again in {entry.name})"
            )
            merged[make] = models
    return merged
