"""SAFE-07 characterization for AMSPerformanceAdapter.

Pins the current ``parse_product_page()`` output shape against a committed
product HTML fixture. If the parse output changes intentionally, regenerate
``expected.json`` using the one-liner at the bottom of this file.

Per D-22 we test ONLY ``parse_product_page()``, NOT ``discover_product_urls()``.
Per D-23 we key by class name (not ADAPTER_NAME, which doesn't land until
Phase 3 CRAWL-02).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.crawlers.adapters.tier0_http.amsperformance import AMSPerformanceAdapter

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "amsperformance"
HTML_PATH = FIXTURE_DIR / "product.html"
EXPECTED_PATH = FIXTURE_DIR / "expected.json"


def _payload_to_dict(payload: Any) -> dict:
    return asdict(payload)


def test_parse_product_page_matches_expected() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))

    adapter = AMSPerformanceAdapter()
    payload = adapter.parse_product_page(html, expected["product_url"])

    assert payload is not None, "parse_product_page returned None — fixture / adapter mismatch"
    actual = _payload_to_dict(payload)

    # image_urls: compare as SETS (order is CDN-dependent, not contract-stable).
    actual_images = set(actual.pop("image_urls") or [])
    expected_images = set(expected.pop("image_urls") or [])
    assert actual_images == expected_images, f"image_urls drift: actual={actual_images} expected={expected_images}"
    assert actual == expected, f"parse output drift: {actual!r} vs {expected!r}"


# To regenerate expected.json after an intentional parse change:
#
#   cd backend && python -c "
#   import json
#   from dataclasses import asdict
#   from pathlib import Path
#   from app.crawlers.adapters.tier0_http.amsperformance import AMSPerformanceAdapter
#   FIXTURE = Path('tests/crawlers/fixtures/amsperformance')
#   html = (FIXTURE/'product.html').read_text()
#   expected = json.loads((FIXTURE/'expected.json').read_text())
#   payload = AMSPerformanceAdapter().parse_product_page(html, expected['product_url'])
#   (FIXTURE/'expected.json').write_text(json.dumps(asdict(payload), indent=2, sort_keys=True) + '\n')
#   "
