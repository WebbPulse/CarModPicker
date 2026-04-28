"""
BrakeSpec — structured extraction schema for brake-system parts (rotors, calipers).

Stub field set per the M002 roadmap; pad-compound is free-form ``str`` for now
because the pad-compound vocabulary is not yet curated. Each value field has a
paired ``*_confidence`` companion.

Before-validator coercion (M004/S05)
------------------------------------
``rotor_diameter_mm`` accepts stringly-typed adapter payloads in mm or inches
and normalizes inches via the standard 25.4 conversion factor.
"""

import re
from typing import Any, Literal, Optional

from pydantic import field_validator

from app.crawlers.specs.base import CategorySpec

# Length-unit conversion to mm. ``in``, ``inch``, ``inches`` and the literal
# double-quote (encoded as ``"`` or its plain ASCII form) are recognized.
_LENGTH_UNIT_TO_MM: dict[str, float] = {
    "mm": 1.0,
    "millimeter": 1.0,
    "millimeters": 1.0,
    "in": 25.4,
    "inch": 25.4,
    "inches": 25.4,
    '"': 25.4,
}

# Bounded numeric run + optional unit token (letters or a literal ``"``).
# Anchored to full string for tight matching.
_LENGTH_RE = re.compile(
    r"^\s*(\d{1,5}(?:\.\d{1,4})?)\s*([A-Za-z]+|\")?\s*$",
)


def _coerce_length_mm(field_name: str, value: Any) -> Any:
    """Shared length-to-mm coercion used by BrakeSpec and TurboSpec."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        match = _LENGTH_RE.match(value)
        if match is None:
            raise ValueError(
                f"{field_name} string did not match '<num>[ unit]' shape: {value!r}"
            )
        number = float(match.group(1))
        unit = match.group(2)
        if unit is None:
            return number
        factor = _LENGTH_UNIT_TO_MM.get(unit.lower())
        if factor is None:
            raise ValueError(
                f"{field_name} string carries unknown unit suffix: {value!r}"
            )
        return number * factor
    raise ValueError(
        f"{field_name} must be int/float/str/None, got {type(value).__name__}"
    )


class BrakeSpec(CategorySpec):
    rotor_diameter_mm: Optional[float] = None
    rotor_diameter_mm_confidence: Optional[Literal["high", "medium", "low"]] = None

    pad_compound: Optional[str] = None
    pad_compound_confidence: Optional[Literal["high", "medium", "low"]] = None

    piston_count: Optional[int] = None
    piston_count_confidence: Optional[Literal["high", "medium", "low"]] = None

    vented: Optional[bool] = None
    vented_confidence: Optional[Literal["high", "medium", "low"]] = None

    @field_validator("rotor_diameter_mm", mode="before")
    @classmethod
    def _coerce_rotor_diameter_mm(cls, value: Any) -> Any:
        return _coerce_length_mm("rotor_diameter_mm", value)
