"""
WheelSpec — structured extraction schema for wheel parts (rims).

Concrete fields (M004/S06): ``diameter_inches`` (e.g. 18, 19, 20),
``width_inches`` (e.g. 8.5, 9.5), ``offset_mm`` (signed — wheels can have
negative offset), and ``bolt_pattern`` canonicalized to ``<lugs>x<pcd>``
shape (e.g. ``5x114.3``, ``4x100``). Each value field has a paired
``*_confidence`` companion.

Before-validator coercion (M004/S06)
------------------------------------
``diameter_inches`` / ``width_inches`` accept stringly-typed adapter payloads
with optional ``in`` / ``inch`` / ``inches`` / ``"`` unit suffixes; numeric
inputs pass through as ``float``. ``offset_mm`` accepts signed numerics or
``"+45mm"`` / ``"-12 mm"`` strings and rounds to ``int``. ``bolt_pattern``
canonicalizes free-form strings (``"5 x 114.3"``, ``"5*114.3"``) to the
``<lugs>x<pcd>`` shape via a bounded regex per MEM029.

This module deliberately does NOT import from ``app.crawlers.parsing`` per
the MEM239/MEM240 circular-import guard.
"""

import re
from typing import Any, Literal, Optional

from pydantic import field_validator

from app.crawlers.specs.base import CategorySpec

# Bounded numeric run + optional inch-unit token. Anchored to full string.
# MEM029 ReDoS contract: ``\d{1,3}(?:\.\d{1,4})?`` is bounded.
_INCH_RE = re.compile(
    r"^\s*(\d{1,3}(?:\.\d{1,4})?)\s*(in|inch|inches|\")?\s*$",
    re.IGNORECASE,
)

# Signed numeric run + optional ``mm`` token. Wheels can have negative offset.
_OFFSET_MM_RE = re.compile(
    r"^\s*([+-]?\d{1,4})\s*(mm)?\s*$",
    re.IGNORECASE,
)

# Bolt-pattern shape: ``<lugs>x<pcd>`` where lugs is 1-2 digits and pcd is up
# to 3 integer digits with up to 2 decimal places. Accepts ``x``/``X``/``*``
# as the separator and tolerates surrounding whitespace.
_BOLT_PATTERN_RE = re.compile(
    r"^\s*(\d{1,2})\s*[xX*]\s*(\d{1,3}(?:\.\d{1,2})?)\s*$",
)


def _coerce_inches(field_name: str, value: Any) -> Any:
    """Coerce numeric or string-with-inch-suffix payloads to float inches."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(
            f"{field_name} must be int/float/str/None, got bool"
        )
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = _INCH_RE.match(value)
        if match is None:
            raise ValueError(
                f"{field_name} string did not match '<num>[ unit]' shape: {value!r}"
            )
        return float(match.group(1))
    raise ValueError(
        f"{field_name} must be int/float/str/None, got {type(value).__name__}"
    )


class WheelSpec(CategorySpec):
    diameter_inches: Optional[float] = None
    diameter_inches_confidence: Optional[Literal["high", "medium", "low"]] = None

    width_inches: Optional[float] = None
    width_inches_confidence: Optional[Literal["high", "medium", "low"]] = None

    offset_mm: Optional[int] = None
    offset_mm_confidence: Optional[Literal["high", "medium", "low"]] = None

    bolt_pattern: Optional[str] = None
    bolt_pattern_confidence: Optional[Literal["high", "medium", "low"]] = None

    @field_validator("diameter_inches", mode="before")
    @classmethod
    def _coerce_diameter_inches(cls, value: Any) -> Any:
        return _coerce_inches("diameter_inches", value)

    @field_validator("width_inches", mode="before")
    @classmethod
    def _coerce_width_inches(cls, value: Any) -> Any:
        return _coerce_inches("width_inches", value)

    @field_validator("offset_mm", mode="before")
    @classmethod
    def _coerce_offset_mm(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("offset_mm must be int/float/str/None, got bool")
        if isinstance(value, (int, float)):
            return int(round(value))
        if isinstance(value, str):
            match = _OFFSET_MM_RE.match(value)
            if match is None:
                raise ValueError(
                    f"offset_mm string did not match '[+-]<int>[ mm]' shape: {value!r}"
                )
            return int(match.group(1))
        raise ValueError(
            f"offset_mm must be int/float/str/None, got {type(value).__name__}"
        )

    @field_validator("bolt_pattern", mode="before")
    @classmethod
    def _coerce_bolt_pattern(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                f"bolt_pattern must be str/None, got {type(value).__name__}"
            )
        match = _BOLT_PATTERN_RE.match(value)
        if match is None:
            raise ValueError(
                f"bolt_pattern did not match '<lugs>x<pcd>' shape: {value!r}"
            )
        lugs, pcd = match.group(1), match.group(2)
        return f"{int(lugs)}x{pcd}"
