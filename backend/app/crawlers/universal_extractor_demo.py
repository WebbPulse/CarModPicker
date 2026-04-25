"""
CLI demo: run the S02 universal extractor over five tracked product-page
fixtures and print one summary line per adapter.

Designed as a manual-inspection surface for tuning extractor confidence
levels in S03. Wraps the same code path production ingest runs:

    parse_product_page(html, url) → apply_universal_extraction(html, payload)

so what the demo prints is exactly what the runner would persist.

Invocation
----------
    cd backend && python -m app.crawlers.universal_extractor_demo

Output is a single line per adapter:

    <adapter_slug>: <field>=<value> (<conf>), <field>=<value> (<conf>), ...

When no universal field extracts cleanly, the line ends with
``(no universal fields extracted)`` — useful when an adapter's archived page
is missing universal signals entirely.

Exit codes
----------
* ``0`` on full success.
* ``1`` on any exception (missing adapter, missing fixture, raised parse).

Why ``sys.exit`` rather than ``raise``: the test
``test_universal_extractor_demo_cli`` asserts on ``returncode == 0``; using
``sys.exit(1)`` keeps the failure-surface explicit and inspectable from the
shell as well as from the test.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Iterable, List, Tuple

# Module-import order: ADAPTER_REGISTRY only finishes populating after the
# adapters package has been walked. Importing the registry here forces that.
from app.crawlers.adapters import ADAPTER_REGISTRY


# Adapter slugs to demo against — each must have a tracked product.html
# fixture under tests/crawlers/fixtures/<slug>/. Keep in lockstep with the
# slice plan and the subprocess test in test_universal_extractor.py.
DEMO_ADAPTERS: Tuple[str, ...] = (
    "amsperformance",
    "briantooleyracing",
    "cobbtuning",
    "subispeed",
    "texasspeed",
)


def _fixtures_root() -> Path:
    """
    Locate ``backend/tests/crawlers/fixtures``.

    Module path: ``backend/app/crawlers/universal_extractor_demo.py``
    parents[0] = backend/app/crawlers
    parents[1] = backend/app
    parents[2] = backend
    """
    return Path(__file__).resolve().parents[2] / "tests" / "crawlers" / "fixtures"


def _format_field(name: str, value: object, confidence: object) -> str:
    """
    Render one field as ``name=value (confidence)``. Floats are trimmed to a
    single decimal so the line stays scannable; everything else is repr-ed.
    """
    if isinstance(value, float):
        value_str = f"{value:.1f}"
    elif isinstance(value, str):
        # Cap long strings (e.g. fitment_notes 300-char windows) so the line
        # remains a single visible row.
        value_str = value if len(value) <= 80 else value[:77] + "..."
    else:
        value_str = repr(value)
    return f"{name}={value_str} ({confidence})"


def _summary_for_adapter(adapter_slug: str, fixtures_root: Path) -> str:
    """
    Return the one-line summary for an adapter, or raise so the top-level
    handler can convert the failure to ``sys.exit(1)``.
    """
    if adapter_slug not in ADAPTER_REGISTRY:
        raise KeyError(
            f"adapter {adapter_slug!r} not in ADAPTER_REGISTRY; "
            f"known: {sorted(ADAPTER_REGISTRY)[:8]}..."
        )
    fixture_path = fixtures_root / adapter_slug / "product.html"
    if not fixture_path.is_file():
        raise FileNotFoundError(f"fixture missing: {fixture_path}")

    html = fixture_path.read_text(encoding="utf-8")
    fixture_url = f"https://example.com/fixtures/{adapter_slug}/product"

    adapter_cls = ADAPTER_REGISTRY[adapter_slug]
    # Construct the adapter without a fetcher — parse_product_page is pure
    # over (html, url) and never calls self.fetcher. The lazy-fetcher pattern
    # in RetailerCrawlerAdapter.__init__ keeps construction free of network
    # config.
    adapter = adapter_cls()

    payload = adapter.parse_product_page(html, fixture_url)
    if payload is None:
        return f"{adapter_slug}: (parse_product_page returned None)"

    payload = adapter.apply_universal_extraction(html, payload)
    if payload is None or not payload.specifications:
        return f"{adapter_slug}: (no universal fields extracted)"

    universal_fields = (
        "weight_grams",
        "material",
        "finish",
        "warranty_days",
        "fitment_notes",
    )
    rendered: List[str] = []
    for name in universal_fields:
        if name not in payload.specifications:
            continue
        value = payload.specifications.get(name)
        confidence = payload.specifications.get(f"{name}_confidence", "?")
        rendered.append(_format_field(name, value, confidence))

    if not rendered:
        return f"{adapter_slug}: (no universal fields extracted)"
    return f"{adapter_slug}: " + ", ".join(rendered)


def _run(adapter_slugs: Iterable[str]) -> int:
    """Print one summary line per adapter. Returns 0 on success, 1 on any failure."""
    fixtures_root = _fixtures_root()
    if not fixtures_root.is_dir():
        print(f"FATAL: fixtures dir missing at {fixtures_root}", file=sys.stderr)
        return 1

    failures = 0
    for slug in adapter_slugs:
        try:
            print(_summary_for_adapter(slug, fixtures_root))
        except Exception:  # noqa: BLE001 — demo CLI surfaces all failures
            failures += 1
            print(f"{slug}: FAIL", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    return 0 if failures == 0 else 1


def main() -> int:
    return _run(DEMO_ADAPTERS)


if __name__ == "__main__":  # pragma: no cover — covered via subprocess test
    sys.exit(main())
