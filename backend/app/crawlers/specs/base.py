"""
CategorySpec — abstract base for per-category structured-extraction schemas.

Every concrete spec (CoiloverSpec, BrakeSpec, TurboSpec, ...) subclasses
CategorySpec and uses Pydantic v2 with ``ConfigDict(extra='forbid')`` so any
unrecognized field surfaces as a ``ValidationError`` at the adapter boundary
instead of being silently swallowed at ingest. That hard barrier between
"adapter tried to extract" and "ingest got something useful" is the contract
this slice locks in.

Universal-field inheritance (M002/S02)
--------------------------------------
The five universal fields produced by ``app.crawlers.parsing.extract_universal_fields``
— ``weight_grams``, ``material``, ``finish``, ``warranty_days``, ``fitment_notes`` —
are declared on this base class along with their paired ``*_confidence`` companions.
Concrete subclasses (CoiloverSpec, BrakeSpec, TurboSpec, ...) inherit them
automatically and only need to declare *category-specific* fields. A
``UniversalSpec`` subclass (in ``universal.py``) declares no extra fields at all
and is registered under the ``'universal'`` slug as a catch-all for parts whose
inferred category has no registered spec model.

Confidence-flag convention
--------------------------
Every value field ``X`` may carry a companion field ``X_confidence`` typed as
``Optional[Literal['high', 'medium', 'low']]``. Universal extraction (S02) populates
these companions when a value is heuristically derived; adapter-coded
extractions can leave them ``None`` to signal "the adapter is sure". Downstream
consumers (the API, the canonicalizer, future ML re-scoring) can use
confidence flags to decide whether to overwrite, merge, or quarantine values.

Example concrete subclass:

    class CoiloverSpec(CategorySpec):
        spring_rate_front: Optional[float] = None
        spring_rate_front_confidence: Optional[Literal['high', 'medium', 'low']] = None

The companion-field convention is mechanical (just paired ``_confidence`` fields)
rather than enforced by metaclass machinery — this keeps the schemas trivial to
read and JSON-Schema-export, at the cost of needing the convention documented
here. Field metadata helpers may codify this in a later slice.

Before-validator coercion (M004/S05)
------------------------------------
Each universal value field carries a ``@field_validator(mode='before')`` that
canonicalizes the raw input shape *before* Pydantic's type coercion runs.
The validators handle the rare path where ``apply_universal_extraction`` was
suppressed and an adapter handed back a stringly-typed value with a unit
suffix (e.g. ``"600 lb"``, ``"Stainless Steel"``, ``"3 years"``). Every
validator preserves None pass-through and raises ``ValueError`` on
unrecognizable strings so the existing ingest fail-soft hook
(``app/crawlers/base.py:790``, MEM015) drops ``payload.specifications`` to
None and emits ``ExtractionFailureRate`` rather than blocking ingest.
"""

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator

# Unit conversion tables — values mirror ``app.crawlers.parsing._WEIGHT_UNIT_TO_GRAMS``
# / ``_WARRANTY_UNIT_DAYS`` / ``_WARRANTY_LIFETIME_DAYS`` exactly. The schema
# layer defines them locally rather than importing them to avoid a circular
# dependency: ``app.crawlers.base`` imports ``specs`` at module load, and
# ``parsing`` imports ``ScrapedPayload`` from ``app.crawlers.base`` —
# importing parsing here would deadlock the import graph at startup. Whenever
# a unit alias is added in parsing.py, mirror it here.
_WEIGHT_UNIT_TO_GRAMS: dict[str, float] = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1000.0,
    "kgs": 1000.0,
    "kilogram": 1000.0,
    "kilograms": 1000.0,
    "lb": 453.59237,
    "lbs": 453.59237,
    "pound": 453.59237,
    "pounds": 453.59237,
    "oz": 28.3495231,
    "ounce": 28.3495231,
    "ounces": 28.3495231,
}
_WARRANTY_UNIT_DAYS: dict[str, float] = {
    "year": 365.25,
    "years": 365.25,
    "yr": 365.25,
    "yrs": 365.25,
    "month": 30.44,
    "months": 30.44,
    "day": 1.0,
    "days": 1.0,
}
_WARRANTY_LIFETIME_DAYS = 36500.0

# Bounded numeric run + optional unit token. Mirrors ``_WEIGHT_VALUE_UNIT_RE``
# in parsing.py but anchored to the full string so the validator only accepts
# tightly-shaped scalar payloads (not free-text descriptions). MEM029 ReDoS
# contract: ``\d{1,8}(?:\.\d{1,4})?`` is bounded.
_WEIGHT_STR_RE = re.compile(
    r"^\s*(\d{1,8}(?:\.\d{1,4})?)\s*([A-Za-z]+)?\s*$",
)
_WARRANTY_STR_RE = re.compile(
    r"^\s*(\d{1,4}(?:\.\d{1,4})?)\s*([A-Za-z]+)?\s*$",
)
_WHITESPACE_RE = re.compile(r"\s+")
_FITMENT_NOTES_MAX_LEN = 500


class CategorySpec(BaseModel):
    """
    Abstract base for category-specific extraction schemas.

    Subclasses define the typed value fields for a single sub-category
    (e.g. coilover, brake, turbo) and must keep ``extra='forbid'`` so unknown
    keys raise ``ValidationError``. See module docstring for the confidence-flag
    companion convention and the universal-field inheritance contract.
    """

    model_config = ConfigDict(extra="forbid")

    # Universal fields (M002/S02) — populated by extract_universal_fields()
    # against the raw HTML; every concrete spec inherits these automatically.
    weight_grams: Optional[float] = None
    weight_grams_confidence: Optional[Literal["high", "medium", "low"]] = None

    material: Optional[str] = None
    material_confidence: Optional[Literal["high", "medium", "low"]] = None

    finish: Optional[str] = None
    finish_confidence: Optional[Literal["high", "medium", "low"]] = None

    warranty_days: Optional[float] = None
    warranty_days_confidence: Optional[Literal["high", "medium", "low"]] = None

    fitment_notes: Optional[str] = None
    fitment_notes_confidence: Optional[Literal["high", "medium", "low"]] = None

    manufacturer_part_number: Optional[str] = None
    manufacturer_part_number_confidence: Optional[Literal["high", "medium", "low"]] = None

    # ------------------------------------------------------------------ #
    # Before-validator coercion for universal fields (M004/S05).         #
    # Each validator inherits to every concrete CategorySpec subclass    #
    # via Pydantic v2's documented inheritance behavior. None always     #
    # passes through; unrecognizable strings raise ValueError so the     #
    # ingest fail-soft hook drops specifications to None (MEM015).       #
    # ------------------------------------------------------------------ #

    @field_validator("weight_grams", mode="before")
    @classmethod
    def _coerce_weight_grams(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            match = _WEIGHT_STR_RE.match(value)
            if match is None:
                raise ValueError(
                    f"weight_grams string did not match '<num>[ unit]' shape: {value!r}"
                )
            number_str, unit = match.group(1), match.group(2)
            number = float(number_str)
            if unit is None:
                return number
            factor = _WEIGHT_UNIT_TO_GRAMS.get(unit.lower())
            if factor is None:
                raise ValueError(
                    f"weight_grams string carries unknown unit suffix: {value!r}"
                )
            return number * factor
        raise ValueError(
            f"weight_grams must be int/float/str/None, got {type(value).__name__}"
        )

    @field_validator("material", mode="before")
    @classmethod
    def _coerce_material(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                f"material must be str/None, got {type(value).__name__}"
            )
        normalized = _WHITESPACE_RE.sub(" ", value.strip()).lower()
        if not normalized:
            raise ValueError("material string is empty after normalization")
        return normalized

    @field_validator("finish", mode="before")
    @classmethod
    def _coerce_finish(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                f"finish must be str/None, got {type(value).__name__}"
            )
        normalized = _WHITESPACE_RE.sub(" ", value.strip()).lower()
        if not normalized:
            raise ValueError("finish string is empty after normalization")
        return normalized

    @field_validator("warranty_days", mode="before")
    @classmethod
    def _coerce_warranty_days(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.lower() == "lifetime":
                return _WARRANTY_LIFETIME_DAYS
            match = _WARRANTY_STR_RE.match(stripped)
            if match is None:
                raise ValueError(
                    f"warranty_days string did not match '<num>[ unit]' shape: {value!r}"
                )
            number_str, unit = match.group(1), match.group(2)
            number = float(number_str)
            if unit is None:
                return number
            factor = _WARRANTY_UNIT_DAYS.get(unit.lower())
            if factor is None:
                raise ValueError(
                    f"warranty_days string carries unknown unit suffix: {value!r}"
                )
            return number * factor
        raise ValueError(
            f"warranty_days must be int/float/str/None, got {type(value).__name__}"
        )

    @field_validator("fitment_notes", mode="before")
    @classmethod
    def _coerce_fitment_notes(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                f"fitment_notes must be str/None, got {type(value).__name__}"
            )
        normalized = _WHITESPACE_RE.sub(" ", value.strip())
        if not normalized:
            raise ValueError("fitment_notes string is empty after normalization")
        if len(normalized) > _FITMENT_NOTES_MAX_LEN:
            normalized = normalized[:_FITMENT_NOTES_MAX_LEN]
        return normalized

    @field_validator("manufacturer_part_number", mode="before")
    @classmethod
    def _coerce_manufacturer_part_number(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                f"manufacturer_part_number must be str/None, got {type(value).__name__}"
            )
        normalized = _WHITESPACE_RE.sub(" ", value.strip()).upper()
        if not normalized:
            raise ValueError("manufacturer_part_number string is empty after normalization")
        return normalized
