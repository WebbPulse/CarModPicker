"""
Tests for the A90 Shop variant-splitting hook.

Wix product pages on a90shop.com embed an ``"options":[{...selections:[...]}]``
JSON block. Many selections carry ``+$NN`` price deltas in the label
(``"Matte +$22"``, ``"JB4PRO +$300"``) or describe a categorically-different
SKU (turbo choice, brake-pad position). The adapter's ``extract_variants``
hook parses that block and emits one extra ``ScrapedPayload`` per non-default
selection that passes the delta-or-categorical filter, so the catalog stops
collapsing eight $200–$1500 SKUs into one row at one price.

These tests stay at the helper level — they exercise
``_a90_extract_variant_payloads`` against synthetic Wix HTML rather than
mocking the runner / DB ingest path. Behavior the helper must guarantee:

  * Default selection (first in the list) is NOT emitted — base payload covers it.
  * Numeric ``+$NN`` deltas above the floor become priced variants.
  * Sub-floor numeric deltas ($1–$4) collapse unless the option is categorical.
  * Categorical-axis selections (turbo, side, position, type) split at $0 delta.
  * Color/finish-only options with no delta and non-categorical title collapse.
  * Pages with no ``"options":[...]`` block return ``[]``.
"""

from __future__ import annotations

import json

from app.crawlers.adapters.tier0_http.a90shop import (
    _a90_extract_variant_payloads,
    _label_without_price,
    _parse_price_delta_cents,
    _slugify_variant,
    A90ShopAdapter,
)
from app.crawlers.base import ScrapedPayload


def _wix_html(options: list[dict]) -> str:
    """Wrap a Wix-shape options array in just enough HTML to locate the block."""
    payload = json.dumps({"options": options})
    return f"""
<html>
<head><title>A90Shop Test</title></head>
<body>
<script>
var productData = {payload};
</script>
</body>
</html>
""".strip()


def _base_payload(**overrides) -> ScrapedPayload:
    defaults = {
        "name": "Rexpeed V3 Spoiler MKV Supra A90",
        "product_url": "https://www.a90shop.com/product-page/rexpeed-v3-carbon-spoiler-supra",
        "price_cents": 50000,
        "part_manufacturer": "Rexpeed",
        "part_number": "TS24",
    }
    defaults.update(overrides)
    return ScrapedPayload(**defaults)


# --- helper unit tests ---


def test_parse_price_delta_cents_handles_plus_dollar() -> None:
    assert _parse_price_delta_cents("Matte +$22") == 2200


def test_parse_price_delta_cents_handles_thousands_with_comma() -> None:
    assert _parse_price_delta_cents("Yes $1,004.99") == 100499


def test_parse_price_delta_cents_returns_none_when_no_dollar() -> None:
    # "V2" / "Stage 3" are NOT prices — must not be misread as delta.
    assert _parse_price_delta_cents("Gloss") is None
    assert _parse_price_delta_cents("V2 Wing") is None
    assert _parse_price_delta_cents("288 / 288 Stage 3") is None


def test_label_without_price_drops_trailing_delta() -> None:
    assert _label_without_price("Matte +$22") == "Matte"
    assert _label_without_price("JB4PRO +$300 (fuel options)") == "JB4PRO (fuel options)"


def test_slugify_variant_strips_dollar_and_collapses() -> None:
    assert _slugify_variant("Matte +$22") == "matte"
    assert _slugify_variant("JB4PRO +$300 (fuel options)") == "jb4pro-fuel-options"


# --- helper integration tests against synthetic Wix HTML ---


def test_no_options_block_yields_no_variants() -> None:
    html = "<html><body>no wix options here</body></html>"
    assert _a90_extract_variant_payloads(html, _base_payload()) == []


def test_single_finish_delta_emits_one_variant() -> None:
    html = _wix_html(
        [
            {
                "title": "Clear Coat Finish",
                "selections": [
                    {"value": "Gloss"},
                    {"value": "Matte +$22"},
                ],
            }
        ]
    )
    variants = _a90_extract_variant_payloads(html, _base_payload())
    assert len(variants) == 1
    v = variants[0]
    assert v.name == "Rexpeed V3 Spoiler MKV Supra A90 (Clear Coat Finish: Matte)"
    assert v.product_url == (
        "https://www.a90shop.com/product-page/rexpeed-v3-carbon-spoiler-supra?variant=matte"
    )
    assert v.part_number == "TS24-matte"
    assert v.price_cents == 50000 + 2200
    assert v.part_manufacturer == "Rexpeed"


def test_color_only_no_delta_collapses() -> None:
    """Pure color/finish options without a delta should NOT split — the
    canonical part covers them. Color names like 'Black' aren't categorical."""
    html = _wix_html(
        [
            {
                "title": "Color",
                "selections": [
                    {"value": "Chrome Silver"},
                    {"value": "Diamond Black"},
                ],
            }
        ]
    )
    assert _a90_extract_variant_payloads(html, _base_payload()) == []


def test_sub_floor_delta_collapses() -> None:
    """A $2 delta is below the floor and the option is non-categorical, so collapse."""
    html = _wix_html(
        [
            {
                "title": "Color",
                "selections": [
                    {"value": "Black"},
                    {"value": "Red +$2"},
                ],
            }
        ]
    )
    assert _a90_extract_variant_payloads(html, _base_payload()) == []


def test_categorical_axis_splits_at_zero_delta() -> None:
    """``Side``, ``Turbo Choice``, etc. describe genuinely-different SKUs and
    must split even when the label carries no ``+$NN`` token."""
    html = _wix_html(
        [
            {
                "title": "Side",
                "selections": [
                    {"value": "Driver"},
                    {"value": "Passenger"},
                    {"value": "Both"},
                ],
            }
        ]
    )
    variants = _a90_extract_variant_payloads(html, _base_payload())
    # First selection is the default (covered by base); two extras emitted.
    assert {v.name.split("(")[-1].rstrip(")") for v in variants} == {
        "Side: Passenger",
        "Side: Both",
    }
    # No price delta means each variant inherits the base price.
    assert all(v.price_cents == 50000 for v in variants)
    assert {v.product_url for v in variants} == {
        "https://www.a90shop.com/product-page/rexpeed-v3-carbon-spoiler-supra?variant=passenger",
        "https://www.a90shop.com/product-page/rexpeed-v3-carbon-spoiler-supra?variant=both",
    }


def test_turbo_kit_categorical_with_priced_addons_splits() -> None:
    """JB4 vs JB4PRO is categorical (option title contains 'Version'); also
    has a +$300 delta. Should split with the resolved price."""
    html = _wix_html(
        [
            {
                "title": "Which Version JB4 Tuner?",
                "selections": [
                    {"value": "JB4"},
                    {"value": "JB4PRO +$300 (fuel options)"},
                ],
            }
        ]
    )
    variants = _a90_extract_variant_payloads(html, _base_payload(price_cents=89900))
    assert len(variants) == 1
    v = variants[0]
    assert v.price_cents == 89900 + 30000
    assert v.product_url.endswith("?variant=jb4pro-fuel-options")
    assert v.part_number == "TS24-jb4pro-fuel-options"


def test_multi_axis_emits_per_option_not_cross_product() -> None:
    """Two axes with two non-default selections each → 4 emitted variants
    (per-axis split), NOT 2x2=4 cross-product combos. Same outward count
    here, but the emitted *names* prove we did per-axis: each name carries
    exactly one option label."""
    html = _wix_html(
        [
            {
                "title": "Clear Coat Finish",
                "selections": [
                    {"value": "Gloss"},
                    {"value": "Matte +$22"},
                ],
            },
            {
                "title": "Graphene Coating",
                "selections": [
                    {"value": "No"},
                    {"value": "Yes +$50"},
                ],
            },
        ]
    )
    variants = _a90_extract_variant_payloads(html, _base_payload())
    assert len(variants) == 2
    names = {v.name for v in variants}
    assert any("Clear Coat Finish: Matte" in n for n in names)
    assert any("Graphene Coating: Yes" in n for n in names)
    # Per-axis split: no name carries BOTH option labels.
    assert all(not ("Clear Coat Finish" in n and "Graphene Coating" in n) for n in names)


def test_max_variants_cap_respected() -> None:
    """A pathological page with many priced options should clamp at the cap
    so one bad URL can't fan out into dozens of part rows."""
    selections = [{"value": "Default"}] + [
        {"value": f"Choice {i} +${(i + 1) * 10}"} for i in range(20)
    ]
    html = _wix_html(
        [
            {
                "title": "Turbo Choice",
                "selections": selections,
            }
        ]
    )
    variants = _a90_extract_variant_payloads(html, _base_payload())
    # _MAX_VARIANTS_PER_PAGE = 12
    assert len(variants) == 12


def test_variant_urls_are_unique() -> None:
    """Two selections that slugify to the same string must not produce two
    listings with the same product_url — the dedup filter inside the helper
    catches it."""
    html = _wix_html(
        [
            {
                "title": "Side",
                "selections": [
                    {"value": "Driver"},
                    {"value": "passenger"},
                    {"value": "Passenger"},  # duplicate slug
                ],
            }
        ]
    )
    variants = _a90_extract_variant_payloads(html, _base_payload())
    urls = [v.product_url for v in variants]
    assert len(urls) == len(set(urls))


def test_adapter_method_delegates_to_helper() -> None:
    """The class method just calls the module helper — sanity check."""
    html = _wix_html(
        [
            {
                "title": "Side",
                "selections": [
                    {"value": "Driver"},
                    {"value": "Passenger"},
                ],
            }
        ]
    )
    adapter = A90ShopAdapter()
    base = _base_payload()
    via_method = adapter.extract_variants(html, base.product_url, base)
    via_helper = _a90_extract_variant_payloads(html, base)
    assert len(via_method) == len(via_helper) == 1
    assert via_method[0].product_url == via_helper[0].product_url


def test_base_without_part_number_yields_variant_without_part_number() -> None:
    """When the base part has no SKU, derived variants must not invent one."""
    html = _wix_html(
        [
            {
                "title": "Side",
                "selections": [
                    {"value": "Left"},
                    {"value": "Right"},
                ],
            }
        ]
    )
    variants = _a90_extract_variant_payloads(html, _base_payload(part_number=None))
    assert len(variants) == 1
    assert variants[0].part_number is None
