"""
TurboSpec — structured extraction schema for turbocharger parts.

Stub field set per the M002 roadmap. ``housing_ar`` is the A/R ratio of the
turbine housing (e.g. 0.63, 0.82) and is stored as a float for direct
comparison. Each value field has a paired ``*_confidence`` companion.
"""

from typing import Literal, Optional

from app.crawlers.specs.base import CategorySpec

JournalOrBB = Literal["journal", "ballbearing"]


class TurboSpec(CategorySpec):
    compressor_wheel_mm: Optional[float] = None
    compressor_wheel_mm_confidence: Optional[Literal["high", "medium", "low"]] = None

    turbine_wheel_mm: Optional[float] = None
    turbine_wheel_mm_confidence: Optional[Literal["high", "medium", "low"]] = None

    journal_or_bb: Optional[JournalOrBB] = None
    journal_or_bb_confidence: Optional[Literal["high", "medium", "low"]] = None

    housing_ar: Optional[float] = None
    housing_ar_confidence: Optional[Literal["high", "medium", "low"]] = None
