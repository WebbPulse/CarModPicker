"""
Shared test utilities for the crawler test suite.

Two reusable surfaces live here so M002/S01/T05+ contract tests stay focused on
the scenario rather than payload boilerplate or filesystem plumbing:

1. ``load_fixture_html(adapter_slug, filename='product.html')`` — read a tracked
   HTML fixture from ``tests/crawlers/fixtures/<adapter_slug>/<filename>``. Only
   reads paths under the git-tracked ``fixtures/`` tree; never touches ``.gsd/``
   or other gitignored directories.

2. ``make_scraped_payload`` (pytest fixture) — returns a callable factory that
   constructs a ``ScrapedPayload`` with sensible defaults plus arbitrary
   ``**overrides``. Used by spec-contract tests so each assertion line states
   only the fields that matter to that scenario.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

import pytest

from app.crawlers.base import ScrapedPayload

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture_html(adapter_slug: str, filename: str = "product.html") -> str:
    """
    Return the UTF-8 contents of a tracked HTML fixture for the given adapter.

    Looks up ``tests/crawlers/fixtures/<adapter_slug>/<filename>``. Raises
    ``FileNotFoundError`` with the resolved absolute path if the fixture is
    missing — makes test failures actionable when an adapter slug is mistyped.
    """
    path = _FIXTURES_DIR / adapter_slug / filename
    if not path.is_file():
        raise FileNotFoundError(f"Fixture not found: {path.resolve()}")
    return path.read_text(encoding="utf-8")


@pytest.fixture
def make_scraped_payload() -> Callable[..., ScrapedPayload]:
    """
    Factory fixture: return a callable that builds ``ScrapedPayload`` instances
    with sensible defaults plus arbitrary field overrides.

    Defaults match the minimal happy-path payload an adapter would emit; tests
    only override the fields relevant to the scenario they're exercising.
    """

    def _factory(
        name: str = "Test Part",
        product_url: str = "https://example.com/p",
        description: Optional[str] = None,
        price_cents: Optional[int] = None,
        part_manufacturer: Optional[str] = None,
        part_number: Optional[str] = None,
        image_urls: Optional[list[str]] = None,
        gtin: Optional[str] = None,
        **overrides: Any,
    ) -> ScrapedPayload:
        return ScrapedPayload(
            name=name,
            product_url=product_url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls,
            gtin=gtin,
            **overrides,
        )

    return _factory
