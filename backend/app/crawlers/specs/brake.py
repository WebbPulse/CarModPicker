"""
BrakeSpec — structured extraction schema for brake-system parts (rotors, calipers).

Stub field set per the M002 roadmap; pad-compound is free-form ``str`` for now
because the pad-compound vocabulary is not yet curated. Each value field has a
paired ``*_confidence`` companion.
"""

from typing import Literal, Optional

from app.crawlers.specs.base import CategorySpec


class BrakeSpec(CategorySpec):
    rotor_diameter_mm: Optional[float] = None
    rotor_diameter_mm_confidence: Optional[Literal["high", "medium", "low"]] = None

    pad_compound: Optional[str] = None
    pad_compound_confidence: Optional[Literal["high", "medium", "low"]] = None

    piston_count: Optional[int] = None
    piston_count_confidence: Optional[Literal["high", "medium", "low"]] = None

    vented: Optional[bool] = None
    vented_confidence: Optional[Literal["high", "medium", "low"]] = None
