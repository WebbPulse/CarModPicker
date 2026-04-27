"""M002/S03/T03: pin the ``category_targets`` declaration on every registered adapter.

This module is the PR-time gate for the S03 compliance contract — it surfaces
a concrete ``adapter_slug`` in the failure line whenever a future adapter PR
forgets to declare ``category_targets``. Four tests:

1. ``test_every_adapter_declares_category_targets`` — parametrized over the
   live ``ADAPTER_REGISTRY``; failure line names the offending adapter slug
   directly via the pytest id.
2. ``test_every_category_target_resolves_via_registry`` — same parametrize;
   makes the slug-resolution contract explicit in pytest output even though
   ``RetailerCrawlerAdapter.__init_subclass__`` already enforces it at import.
3. ``test_specialist_adapters_declare_concrete_slugs`` — explicit spot-check
   per the S03 demo (brake / coilover / turbo specialist mappings).
4. ``test_total_compliance_count_matches_registry`` — catches a future PR
   that *removes* the declaration from one adapter without dropping the
   adapter itself.

Pure-import assertions — no fixtures, parallel-safe under ``pytest -n auto``.
"""

from __future__ import annotations

import pytest

from app.crawlers.adapters import ADAPTER_REGISTRY
from app.crawlers.specs import default_registry

_REGISTRY_ITEMS = sorted(ADAPTER_REGISTRY.items())


@pytest.mark.parametrize(
    ("adapter_name", "adapter_cls"),
    _REGISTRY_ITEMS,
    ids=lambda nc: nc[0] if isinstance(nc, tuple) else str(nc),
)
def test_every_adapter_declares_category_targets(adapter_name, adapter_cls) -> None:
    """Every registered adapter declares a non-empty list/tuple of string ``category_targets``.

    The pytest id is the adapter slug, so a CI failure line like
    ``test_every_adapter_declares_category_targets[wilwood] FAILED`` points at
    the offender directly.
    """
    targets = getattr(adapter_cls, "category_targets", None)
    assert isinstance(targets, (list, tuple)), (
        f"{adapter_name}: category_targets is not a list/tuple " f"(got {type(targets).__name__})"
    )
    assert len(targets) >= 1, (
        f"{adapter_name}: category_targets is empty; declare at least " f"one slug (e.g. 'universal')"
    )
    for entry in targets:
        assert isinstance(entry, str) and entry.strip(), (
            f"{adapter_name}: invalid category_targets entry {entry!r}; " f"each entry must be a non-empty string"
        )


@pytest.mark.parametrize(
    ("adapter_name", "adapter_cls"),
    _REGISTRY_ITEMS,
    ids=lambda nc: nc[0] if isinstance(nc, tuple) else str(nc),
)
def test_every_category_target_resolves_via_registry(adapter_name, adapter_cls) -> None:
    """Every declared ``category_targets`` entry resolves via ``default_registry``.

    Belt-and-suspenders for ``RetailerCrawlerAdapter.__init_subclass__`` —
    surfaces the contract in pytest output so a typo lands as a named test
    failure, not just an import-time ``TypeError``.
    """
    for entry in getattr(adapter_cls, "category_targets", []):
        assert default_registry.resolve(entry) is not None, (
            f"{adapter_name}: category_targets entry {entry!r} does not " f"resolve via default_registry"
        )


def test_specialist_adapters_declare_concrete_slugs() -> None:
    """Spot-check the brake / coilover / turbo specialist mappings per S03 demo."""
    expected: dict[str, tuple[str, ...]] = {
        "girodisc": ("brake",),
        "essexparts": ("brake",),
        "wilwood": ("brake",),
        "bcracing": ("coilover",),
        "kwsuspensions": ("coilover",),
        "fortuneauto": ("coilover",),
        "tein": ("coilover",),
        "stanceusa": ("coilover",),
        "atpturbo": ("turbo",),
        "fullrace": ("turbo",),
    }
    missing: list[str] = []
    for slug, required_specialties in expected.items():
        cls = ADAPTER_REGISTRY.get(slug)
        if cls is None:
            missing.append(f"{slug}: not registered in ADAPTER_REGISTRY")
            continue
        targets = list(getattr(cls, "category_targets", []))
        for specialty in required_specialties:
            if specialty not in targets:
                missing.append(f"{slug}: expected {specialty!r} in category_targets, got {targets!r}")
    assert missing == [], "Specialist mapping drift:\n  " + "\n  ".join(missing)


def test_total_compliance_count_matches_registry() -> None:
    """Catches a PR that *removes* ``category_targets`` from one adapter without dropping it."""
    total = len(ADAPTER_REGISTRY)
    compliant = sum(
        1
        for cls in ADAPTER_REGISTRY.values()
        if isinstance(getattr(cls, "category_targets", None), (list, tuple))
        and len(getattr(cls, "category_targets")) >= 1
    )
    assert compliant == total, (
        f"Compliance drift: {compliant}/{total} adapters declare category_targets. "
        f"Run `python -m app.crawlers.compliance_audit` from backend/ for the offender list."
    )
