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
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


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
