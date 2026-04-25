"""
CategorySpec — abstract base for per-category structured-extraction schemas.

Every concrete spec (CoiloverSpec, BrakeSpec, TurboSpec, ...) subclasses
CategorySpec and uses Pydantic v2 with ``ConfigDict(extra='forbid')`` so any
unrecognized field surfaces as a ``ValidationError`` at the adapter boundary
instead of being silently swallowed at ingest. That hard barrier between
"adapter tried to extract" and "ingest got something useful" is the contract
this slice locks in.

Confidence-flag convention
--------------------------
Every value field ``X`` may carry a companion field ``X_confidence`` typed as
``Optional[Literal['high', 'medium', 'low']]``. Universal extraction (S02) will
populate these companions when a value is heuristically derived; adapter-coded
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

from pydantic import BaseModel, ConfigDict


class CategorySpec(BaseModel):
    """
    Abstract base for category-specific extraction schemas.

    Subclasses define the typed value fields for a single sub-category
    (e.g. coilover, brake, turbo) and must keep ``extra='forbid'`` so unknown
    keys raise ``ValidationError``. See module docstring for the confidence-flag
    companion convention.
    """

    model_config = ConfigDict(extra="forbid")
