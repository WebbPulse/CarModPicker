"""CRAWL-01/02/03: pin ADAPTER_REGISTRY produced by pkgutil discovery + __init_subclass__ enforcement.

These are the canonical CI guards for the adapter auto-discovery machinery.

- ``test_adapter_count_baseline``: pins DISC-01 (83 tier0 + 15 tier1 + 10 tier2 = 108).
  Dropping an adapter accidentally -> count drift -> CI red.
- ``test_no_import_errors``: asserts ``_IMPORT_ERRORS == []`` per D-05 / D-06.
  A malformed adapter module (import-time ``SyntaxError`` / ``NameError`` / etc.) is
  caught by the discovery scan and appended to ``_IMPORT_ERRORS`` rather than
  raising at app-import time (Pitfall AD-03) -- this test is the single CI
  enforcement point for that signal.
- ``test_all_adapters_have_non_empty_name``: defense in depth for D-02.
- ``test_adapter_names_are_unique``: defense in depth against accidental slug
  collisions (T-03-01-02 in the plan threat register).

Pure-import assertions -- no fixtures or conftest -- inherently worker-safe under
``pytest -n auto --dist=loadfile``.
"""

from __future__ import annotations


def test_adapter_count_baseline() -> None:
    """CRAWL-01: ADAPTER_REGISTRY holds exactly 108 entries (83 tier0 + 15 tier1 + 10 tier2)."""
    from app.crawlers.adapters import ADAPTER_REGISTRY

    actual = len(ADAPTER_REGISTRY)
    assert actual == 108, (
        f"Adapter count drift: got {actual}. "
        f"If intentional, bump the expected count in THIS test."
    )


def test_no_import_errors() -> None:
    """CRAWL-03: discovery scan surfaces zero import failures in a clean tree (D-05 / D-06)."""
    from app.crawlers.adapters import _IMPORT_ERRORS

    assert _IMPORT_ERRORS == [], (
        f"Adapter discovery accumulated import errors: {_IMPORT_ERRORS!r}. "
        f"See logs for traceback -- each failing adapter module must fix its import."
    )


def test_all_adapters_have_non_empty_name() -> None:
    """CRAWL-02: every registered adapter declares a non-empty ADAPTER_NAME."""
    from app.crawlers.adapters import ADAPTER_REGISTRY

    missing = [
        cls.__module__ + "." + cls.__qualname__
        for cls in ADAPTER_REGISTRY.values()
        if not isinstance(getattr(cls, "ADAPTER_NAME", None), str)
        or not cls.ADAPTER_NAME.strip()
    ]
    assert missing == [], (
        f"Adapters with missing/empty ADAPTER_NAME: {missing!r}. See D-02."
    )


def test_adapter_names_are_unique() -> None:
    """CRAWL-02: ADAPTER_REGISTRY keys are unique (T-03-01-02 defense)."""
    from app.crawlers.adapters import ADAPTER_REGISTRY

    keys = list(ADAPTER_REGISTRY.keys())
    assert len(keys) == len(set(keys)), (
        f"Duplicate ADAPTER_NAME slugs detected: keys={keys!r}"
    )
