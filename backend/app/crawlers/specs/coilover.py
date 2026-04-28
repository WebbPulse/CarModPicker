"""
CoiloverSpec — structured extraction schema for coilover suspension parts.

Stub field set per the M002 roadmap; the universal-field retrofit slices
expand it. Each value field has a paired ``*_confidence`` companion to support
heuristic-extraction confidence routing (see ``base.py``).

Before-validator coercion (M004/S05)
------------------------------------
``spring_rate_front`` / ``spring_rate_rear`` accept stringly-typed adapter
payloads carrying lb/in, lbs/in, lbf/in, or kg/mm unit suffixes. kg/mm is in
scope per S05-RESEARCH (common JDM coilover unit). ``damper_adjustability``
canonicalizes free-form adjustability descriptions to the existing Literal
domain ('rebound-only' / 'rebound-and-compression' / etc.).
"""

import re
from typing import Any, Literal, Optional

from pydantic import field_validator

from app.crawlers.specs.base import CategorySpec

DamperAdjustability = Literal[
    "non-adjustable",
    "rebound-only",
    "rebound-and-compression",
    "electronic",
]

# Spring-rate unit conversion to lb/in (the canonical storage unit). Per
# research, US coilovers report lb/in / lbs/in / lbf/in (1:1) while JDM
# coilovers commonly report kg/mm. 1 kg/mm = 55.997 lb/in.
_SPRING_RATE_UNIT_TO_LB_PER_IN: dict[str, float] = {
    "lb/in": 1.0,
    "lbs/in": 1.0,
    "lbf/in": 1.0,
    "kg/mm": 55.997,
}

# Bounded numeric run + unit token. Anchored to full string for tight matching.
_SPRING_RATE_RE = re.compile(
    r"^\s*(\d{1,5}(?:\.\d{1,4})?)\s*([A-Za-z]+/[A-Za-z]+)?\s*$",
)

# Free-form damper-adjustability strings → canonical Literal values.
_DAMPER_ADJ_CANONICAL: dict[str, str] = {
    "non-adjustable": "non-adjustable",
    "non adjustable": "non-adjustable",
    "fixed": "non-adjustable",
    "rebound-only": "rebound-only",
    "rebound only": "rebound-only",
    "rebound": "rebound-only",
    "single adjustable": "rebound-only",
    "single-adjustable": "rebound-only",
    "1-way adjustable": "rebound-only",
    "1 way adjustable": "rebound-only",
    "rebound-and-compression": "rebound-and-compression",
    "rebound and compression": "rebound-and-compression",
    "rebound + compression": "rebound-and-compression",
    "double adjustable": "rebound-and-compression",
    "double-adjustable": "rebound-and-compression",
    "2-way adjustable": "rebound-and-compression",
    "2 way adjustable": "rebound-and-compression",
    "electronic": "electronic",
    "electronic adjustable": "electronic",
    "electronically adjustable": "electronic",
}

_WS_RE = re.compile(r"\s+")


def _coerce_spring_rate(field_name: str, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        match = _SPRING_RATE_RE.match(value)
        if match is None:
            raise ValueError(
                f"{field_name} string did not match '<num>[ unit]' shape: {value!r}"
            )
        number = float(match.group(1))
        unit = match.group(2)
        if unit is None:
            return number
        factor = _SPRING_RATE_UNIT_TO_LB_PER_IN.get(unit.lower())
        if factor is None:
            raise ValueError(
                f"{field_name} string carries unknown unit suffix: {value!r}"
            )
        return number * factor
    raise ValueError(
        f"{field_name} must be int/float/str/None, got {type(value).__name__}"
    )


class CoiloverSpec(CategorySpec):
    spring_rate_front: Optional[float] = None
    spring_rate_front_confidence: Optional[Literal["high", "medium", "low"]] = None

    spring_rate_rear: Optional[float] = None
    spring_rate_rear_confidence: Optional[Literal["high", "medium", "low"]] = None

    damper_adjustability: Optional[DamperAdjustability] = None
    damper_adjustability_confidence: Optional[Literal["high", "medium", "low"]] = None

    height_adjustable: Optional[bool] = None
    height_adjustable_confidence: Optional[Literal["high", "medium", "low"]] = None

    @field_validator("spring_rate_front", mode="before")
    @classmethod
    def _coerce_spring_rate_front(cls, value: Any) -> Any:
        return _coerce_spring_rate("spring_rate_front", value)

    @field_validator("spring_rate_rear", mode="before")
    @classmethod
    def _coerce_spring_rate_rear(cls, value: Any) -> Any:
        return _coerce_spring_rate("spring_rate_rear", value)

    @field_validator("damper_adjustability", mode="before")
    @classmethod
    def _coerce_damper_adjustability(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                f"damper_adjustability must be str/None, got {type(value).__name__}"
            )
        normalized = _WS_RE.sub(" ", value.strip()).lower()
        if not normalized:
            raise ValueError("damper_adjustability string is empty after normalization")
        canonical = _DAMPER_ADJ_CANONICAL.get(normalized)
        if canonical is None:
            raise ValueError(
                f"damper_adjustability does not map to a canonical Literal value: {value!r}"
            )
        return canonical
