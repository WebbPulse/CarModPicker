"""
CoiloverSpec — structured extraction schema for coilover suspension parts.

Stub field set per the M002 roadmap; the universal-field retrofit slices
expand it. Each value field has a paired ``*_confidence`` companion to support
heuristic-extraction confidence routing (see ``base.py``).
"""

from typing import Literal, Optional

from app.crawlers.specs.base import CategorySpec

DamperAdjustability = Literal[
    "non-adjustable",
    "rebound-only",
    "rebound-and-compression",
    "electronic",
]


class CoiloverSpec(CategorySpec):
    spring_rate_front: Optional[float] = None
    spring_rate_front_confidence: Optional[Literal["high", "medium", "low"]] = None

    spring_rate_rear: Optional[float] = None
    spring_rate_rear_confidence: Optional[Literal["high", "medium", "low"]] = None

    damper_adjustability: Optional[DamperAdjustability] = None
    damper_adjustability_confidence: Optional[Literal["high", "medium", "low"]] = None

    height_adjustable: Optional[bool] = None
    height_adjustable_confidence: Optional[Literal["high", "medium", "low"]] = None
