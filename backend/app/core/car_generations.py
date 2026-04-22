"""Lazy JSON loader for car-generations data (QUAL-01).

JSON asset lives at car_generations_data.json (package-adjacent). First call
reads+parses (~100-200ms on warm SSD); subsequent calls return the memoized
dict reference.

WARNING: Callers MUST NOT mutate the returned dict — @lru_cache returns the
same object reference on every call (see Pitfall JS-01 in 03-RESEARCH.md).
"""
from __future__ import annotations

import functools
import json
from importlib.resources import files


@functools.lru_cache(maxsize=1)
def load_car_generations() -> dict:
    """Load and memoize the car-generations dict from car_generations_data.json."""
    resource = files("app.core").joinpath("car_generations_data.json")
    return json.loads(resource.read_text(encoding="utf-8"))
