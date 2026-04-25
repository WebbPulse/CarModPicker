"""
M002/S03 adapter compliance audit.

Run from ``backend/``::

    python -m app.crawlers.compliance_audit

Reads ``ADAPTER_REGISTRY`` (populated at import time by the discovery walk in
``app/crawlers/adapters/__init__.py``), buckets each registered adapter class
by ``cls.FETCHER_TIER`` (``http`` → T0, ``tls`` → T1, ``browser`` → T2), and
checks that ``cls.category_targets`` is a non-empty list/tuple of strings.

Stdout contract (consumed by S04 — keep stable)::

    M002/S03 adapter compliance audit
      T0 (http):    <n0>/<total0> compliant
      T1 (tls):     <n1>/<total1> compliant
      T2 (browser): <n2>/<total2> compliant
      Total:        <n>/<total> compliant

When all compliant, prints ``OK — every adapter declares at least one
category_targets entry`` and exits 0. When any adapter is non-compliant,
prepends a ``Non-compliant adapters:`` block (one ``- <slug> [<tier>]: declares
no category_targets`` per offender) and exits 1.

The slug-resolution check (each ``category_targets`` entry must resolve via
``default_registry``) already happens at class-definition time inside
``RetailerCrawlerAdapter.__init_subclass__`` — if a bad slug shipped, the
discovery walk would have raised before we got here. The audit's job is the
binary compliance count.
"""

from __future__ import annotations

import sys
from typing import Type

from app.crawlers.adapters import ADAPTER_REGISTRY
from app.crawlers.adapters.base import RetailerCrawlerAdapter

_TIER_LABELS: dict[str, tuple[str, str]] = {
    "http": ("T0", "T0 (http):    "),
    "tls": ("T1", "T1 (tls):     "),
    "browser": ("T2", "T2 (browser): "),
}


def _classify_tier(cls: Type[RetailerCrawlerAdapter]) -> str:
    """Return the canonical ``FETCHER_TIER`` string for ``cls``.

    Defaults to ``"http"`` to match ``RetailerCrawlerAdapter.FETCHER_TIER``;
    any unrecognized value is returned verbatim so the caller can surface it
    as a separate bucket if a new tier is ever introduced.
    """
    return getattr(cls, "FETCHER_TIER", "http")


def _is_compliant(cls: Type[RetailerCrawlerAdapter]) -> bool:
    """``True`` iff ``cls.category_targets`` is a non-empty list/tuple of strings.

    Mirrors the validation already enforced in
    ``RetailerCrawlerAdapter.__init_subclass__`` so the audit signal stays
    aligned with what the base class will accept.
    """
    targets = getattr(cls, "category_targets", [])
    if not isinstance(targets, (list, tuple)):
        return False
    if len(targets) < 1:
        return False
    return all(isinstance(entry, str) and bool(entry.strip()) for entry in targets)


def audit() -> int:
    """Run the audit and print the report. Return ``0`` if all compliant, ``1`` otherwise."""
    # Buckets keyed by tier label (T0/T1/T2 + any unknown tier verbatim).
    by_tier: dict[str, list[tuple[str, Type[RetailerCrawlerAdapter]]]] = {
        "http": [],
        "tls": [],
        "browser": [],
    }

    for slug, cls in ADAPTER_REGISTRY.items():
        tier = _classify_tier(cls)
        by_tier.setdefault(tier, []).append((slug, cls))

    offenders: list[tuple[str, str]] = []  # (slug, tier)
    for tier, items in by_tier.items():
        for slug, cls in items:
            if not _is_compliant(cls):
                offenders.append((slug, tier))

    output_lines: list[str] = []

    if offenders:
        output_lines.append("Non-compliant adapters:")
        for slug, tier in sorted(offenders):
            output_lines.append(f"  - {slug} [{tier}]: declares no category_targets")
        output_lines.append("")

    output_lines.append("M002/S03 adapter compliance audit")

    total_compliant = 0
    total_count = 0
    # Print T0/T1/T2 in canonical order with stable column widths.
    for tier_key in ("http", "tls", "browser"):
        items = by_tier.get(tier_key, [])
        n_compliant = sum(1 for _, cls in items if _is_compliant(cls))
        n_total = len(items)
        total_compliant += n_compliant
        total_count += n_total
        prefix = _TIER_LABELS[tier_key][1]
        output_lines.append(f"  {prefix}{n_compliant}/{n_total} compliant")

    # Surface any unknown tiers (none expected today; defensive in case a
    # future fetcher tier lands before this script is updated).
    for tier_key in sorted(k for k in by_tier.keys() if k not in _TIER_LABELS):
        items = by_tier[tier_key]
        n_compliant = sum(1 for _, cls in items if _is_compliant(cls))
        n_total = len(items)
        total_compliant += n_compliant
        total_count += n_total
        output_lines.append(f"  ?? ({tier_key}):  {n_compliant}/{n_total} compliant")

    output_lines.append(f"  Total:        {total_compliant}/{total_count} compliant")

    if not offenders:
        output_lines.append("OK — every adapter declares at least one category_targets entry")

    print("\n".join(output_lines))
    return 0 if not offenders else 1


if __name__ == "__main__":
    sys.exit(audit())
