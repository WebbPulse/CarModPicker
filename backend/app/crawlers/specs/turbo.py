"""
TurboSpec — structured extraction schema for turbocharger parts.

Stub field set per the M002 roadmap. ``housing_ar`` is the A/R ratio of the
turbine housing (e.g. 0.63, 0.82) and is stored as a float for direct
comparison. Each value field has a paired ``*_confidence`` companion.

Before-validator coercion (M004/S05)
------------------------------------
``compressor_wheel_mm`` / ``turbine_wheel_mm`` share the BrakeSpec length-to-mm
coercion (mm or inches → mm). ``journal_or_bb`` canonicalizes free-form
bearing-type descriptions to the existing Literal domain ('journal' /
'ballbearing').
"""

import re
from typing import Any, Literal, Optional

from pydantic import field_validator

from app.crawlers.specs.base import CategorySpec
from app.crawlers.specs.brake import _coerce_length_mm

JournalOrBB = Literal["journal", "ballbearing"]

# Free-form bearing-type strings → canonical Literal values.
_JOURNAL_OR_BB_CANONICAL: dict[str, str] = {
    "journal": "journal",
    "journal bearing": "journal",
    "journal-bearing": "journal",
    "ballbearing": "ballbearing",
    "ball bearing": "ballbearing",
    "ball-bearing": "ballbearing",
    "bb": "ballbearing",
}

_WS_RE = re.compile(r"\s+")


class TurboSpec(CategorySpec):
    compressor_wheel_mm: Optional[float] = None
    compressor_wheel_mm_confidence: Optional[Literal["high", "medium", "low"]] = None

    turbine_wheel_mm: Optional[float] = None
    turbine_wheel_mm_confidence: Optional[Literal["high", "medium", "low"]] = None

    journal_or_bb: Optional[JournalOrBB] = None
    journal_or_bb_confidence: Optional[Literal["high", "medium", "low"]] = None

    housing_ar: Optional[float] = None
    housing_ar_confidence: Optional[Literal["high", "medium", "low"]] = None

    @field_validator("compressor_wheel_mm", mode="before")
    @classmethod
    def _coerce_compressor_wheel_mm(cls, value: Any) -> Any:
        return _coerce_length_mm("compressor_wheel_mm", value)

    @field_validator("turbine_wheel_mm", mode="before")
    @classmethod
    def _coerce_turbine_wheel_mm(cls, value: Any) -> Any:
        return _coerce_length_mm("turbine_wheel_mm", value)

    @field_validator("journal_or_bb", mode="before")
    @classmethod
    def _coerce_journal_or_bb(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                f"journal_or_bb must be str/None, got {type(value).__name__}"
            )
        normalized = _WS_RE.sub(" ", value.strip()).lower()
        if not normalized:
            raise ValueError("journal_or_bb string is empty after normalization")
        canonical = _JOURNAL_OR_BB_CANONICAL.get(normalized)
        if canonical is None:
            raise ValueError(
                f"journal_or_bb does not map to a canonical Literal value: {value!r}"
            )
        return canonical
