"""
Per-category structured extraction schemas + the SpecRegistry contract.

Adapters declare which sub-categories they target via a ``category_targets``
class attribute (added in a later S01 task) and the ingest pipeline calls
``default_registry.resolve(slug)`` to find the right schema for validation.

Importing this package eagerly registers the project-shipped specs into
``default_registry`` — keep registration here (not at the bottom of each
spec module) so the spec modules themselves stay free of side effects and
remain safe to import in isolation (e.g. from a test that wants to
construct an empty ``SpecRegistry()``).
"""

from app.crawlers.specs.base import CategorySpec
from app.crawlers.specs.brake import BrakeSpec
from app.crawlers.specs.coilover import CoiloverSpec
from app.crawlers.specs.registry import SpecRegistry, default_registry
from app.crawlers.specs.turbo import TurboSpec
from app.crawlers.specs.universal import UniversalSpec

default_registry.register("coilover", CoiloverSpec)
default_registry.register("brake", BrakeSpec)
default_registry.register("turbo", TurboSpec)
default_registry.register("universal", UniversalSpec)

__all__ = [
    "CategorySpec",
    "SpecRegistry",
    "default_registry",
    "CoiloverSpec",
    "BrakeSpec",
    "TurboSpec",
    "UniversalSpec",
]
