"""
UniversalSpec — catch-all CategorySpec for parts whose inferred category has no
registered spec model.

The M002/S02 ingest path bridges ``infer_category()`` DB-name output (e.g.
``"suspension"``) to a SpecRegistry sub-slug (e.g. ``"coilover"``) before
calling ``default_registry.resolve()``. When the bridge cannot map the
inferred category to a known sub-slug, it falls through to ``'universal'``
so the universal extractor's output (weight, material, finish, warranty,
fitment_notes) can still be validated and persisted instead of silently dropped
at the registry pass-through.

UniversalSpec declares no fields of its own — it inherits the five universal
value+confidence pairs from ``CategorySpec`` and keeps ``extra='forbid'`` so
any unexpected category-specific keys still surface as a ``ValidationError``.
The bridge + universal fallback is the contract that makes the S01 validation
hook fire in production for the long tail of categories that don't yet have a
dedicated spec model.
"""

from app.crawlers.specs.base import CategorySpec


class UniversalSpec(CategorySpec):
    """
    Catch-all schema for unmapped sub-categories.

    Inherits the five universal fields from ``CategorySpec`` and adds nothing.
    Registered under the ``'universal'`` slug in ``app.crawlers.specs.__init__``.
    """
