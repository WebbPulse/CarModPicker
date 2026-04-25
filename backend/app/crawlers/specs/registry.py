"""
SpecRegistry — runtime lookup table mapping category slugs to CategorySpec subclasses.

Adapters declare which sub-categories they target via ``category_targets`` and
the ingest pipeline calls ``default_registry.resolve(slug)`` to find the right
schema for validation. Slugs (e.g. ``'coilover'``, ``'brake'``, ``'turbo'``)
are stable across environments; UUIDs are not — slugs are the registry key.

The registry is a class with method-level access (not a module-level dict) so
tests can construct an isolated ``SpecRegistry()`` without monkeypatching a
global. The module also exposes ``default_registry`` — a singleton with the
project-shipped specs pre-registered (population happens in ``__init__.py`` to
avoid circular imports between this module and the concrete spec modules).
"""

from typing import Dict, Optional, Type

from app.crawlers.specs.base import CategorySpec


class SpecRegistry:
    """
    Registry of category-slug → CategorySpec subclass.

    Construct an isolated instance for tests; use ``default_registry`` for the
    production-shipped lookup table.
    """

    def __init__(self) -> None:
        self._specs: Dict[str, Type[CategorySpec]] = {}

    def register(self, slug: str, model: Type[CategorySpec]) -> None:
        """
        Register ``model`` under ``slug``. Re-registering the same slug overwrites
        the previous binding — useful for tests that swap in a stub schema.
        """
        self._specs[slug] = model

    def resolve(self, slug: str) -> Optional[Type[CategorySpec]]:
        """
        Return the spec class for ``slug``, or ``None`` if no spec is registered.
        Returning ``None`` (rather than raising) lets callers route
        unregistered categories through the legacy free-form path without a
        try/except wrapper.
        """
        return self._specs.get(slug)


default_registry = SpecRegistry()
