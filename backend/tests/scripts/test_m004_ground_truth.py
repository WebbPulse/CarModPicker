"""Unit tests for ``backend/scripts/m004_ground_truth.py``.

Pure-function tests with inline HTML strings as fixtures — no external files,
no DB, no network. Each test exercises one of the contracts laid out in
T03-PLAN.md:

* well-formed JSON-LD Product
* malformed JSON-LD (silently degrades)
* JSON-LD with no brand → microdata fallback
* microdata-only fallback
* OpenGraph-only fallback
* all three present (precedence: JSON-LD > microdata > OG)
* empty / None HTML
* oversized input (>5MB cap)
* harness never raises out of ``truth_from_html``

The output dict shape is the public contract scoring depends on, so every
test asserts the three required keys (car_triples / manufacturer / category)
regardless of which branch fired.
"""

from __future__ import annotations

import logging

import pytest

from scripts.m004_ground_truth import (
    HTML_SIZE_CAP_BYTES,
    extract_jsonld_product,
    extract_microdata_brand,
    extract_opengraph_brand,
    truth_from_html,
)


# ---------------------------------------------------------------------------
# Output-shape contract: every call returns the same four keys.
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {"car_triples", "manufacturer", "category"}


def _assert_shape(out: dict) -> None:
    assert isinstance(out, dict)
    assert set(out.keys()) >= REQUIRED_KEYS, f"missing keys: {REQUIRED_KEYS - set(out.keys())}"
    assert isinstance(out["car_triples"], list)
    for triple in out["car_triples"]:
        assert isinstance(triple, tuple) and len(triple) == 3
        assert all(isinstance(p, str) for p in triple)
    assert out["manufacturer"] is None or isinstance(out["manufacturer"], str)
    assert out["category"] is None or isinstance(out["category"], str)


# ---------------------------------------------------------------------------
# extract_jsonld_product helper
# ---------------------------------------------------------------------------


class TestExtractJsonLdProduct:
    def test_well_formed_product(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Product",
         "name": "Bilstein B16 Coilover Kit", "brand": {"@type": "Brand", "name": "Bilstein"},
         "category": "Suspension > Coilovers"}
        </script></head><body></body></html>
        """
        item = extract_jsonld_product(html)
        assert item is not None
        assert item["name"] == "Bilstein B16 Coilover Kit"
        assert item["brand"]["name"] == "Bilstein"

    def test_malformed_json_returns_none(self) -> None:
        html = '<script type="application/ld+json">{not json,,,}</script>'
        assert extract_jsonld_product(html) is None

    def test_no_product_returns_none(self) -> None:
        html = '<script type="application/ld+json">{"@type": "Article"}</script>'
        assert extract_jsonld_product(html) is None

    def test_empty_html_returns_none(self) -> None:
        assert extract_jsonld_product("") is None
        assert extract_jsonld_product("<html></html>") is None


# ---------------------------------------------------------------------------
# extract_microdata_brand helper
# ---------------------------------------------------------------------------


class TestExtractMicrodataBrand:
    def test_itemprop_brand_string(self) -> None:
        html = """
        <div itemscope itemtype="https://schema.org/Product">
          <span itemprop="brand">AC Schnitzer</span>
        </div>
        """
        assert extract_microdata_brand(html) == "AC Schnitzer"

    def test_itemprop_manufacturer_fallback(self) -> None:
        html = """
        <div itemscope itemtype="https://schema.org/Product">
          <meta itemprop="manufacturer" content="Rogue Engineering" />
        </div>
        """
        assert extract_microdata_brand(html) == "Rogue Engineering"

    def test_nested_brand_with_name_itemprop(self) -> None:
        # schema.org Brand pattern: <span itemprop="brand"><span itemprop="name">X</span></span>
        html = """
        <div itemscope itemtype="https://schema.org/Product">
          <span itemprop="brand" itemscope itemtype="https://schema.org/Brand">
            <span itemprop="name">VF-Engineering</span>
          </span>
        </div>
        """
        assert extract_microdata_brand(html) == "VF-Engineering"

    def test_no_microdata_returns_none(self) -> None:
        assert extract_microdata_brand("<html><body><p>nothing here</p></body></html>") is None
        assert extract_microdata_brand("") is None

    def test_empty_brand_value_returns_none(self) -> None:
        html = '<div itemprop="brand"></div>'
        assert extract_microdata_brand(html) is None


# ---------------------------------------------------------------------------
# extract_opengraph_brand helper
# ---------------------------------------------------------------------------


class TestExtractOpenGraphBrand:
    def test_og_brand(self) -> None:
        html = '<head><meta property="og:brand" content="Bilstein" /></head>'
        assert extract_opengraph_brand(html) == "Bilstein"

    def test_product_brand(self) -> None:
        # Some retailers use product:brand instead of og:brand
        html = '<meta property="product:brand" content="Studio RSR" />'
        assert extract_opengraph_brand(html) == "Studio RSR"

    def test_no_brand_meta_returns_none(self) -> None:
        html = '<meta property="og:title" content="A part" />'
        assert extract_opengraph_brand(html) is None

    def test_empty_content_returns_none(self) -> None:
        html = '<meta property="og:brand" content="" />'
        assert extract_opengraph_brand(html) is None


# ---------------------------------------------------------------------------
# truth_from_html — main entry point
# ---------------------------------------------------------------------------


class TestTruthFromHtmlWellFormedJsonLd:
    def test_pulls_brand_and_category_from_jsonld(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Product",
         "name": "B16 Damptronic Coilovers",
         "brand": {"@type": "Brand", "name": "Bilstein"},
         "category": "Suspension > Coilovers",
         "weight": {"value": "12", "unitText": "kg"}}
        </script></head><body></body></html>
        """
        out = truth_from_html(html)
        _assert_shape(out)
        assert out["manufacturer"] == "Bilstein"
        assert out["category"] == "Suspension > Coilovers"

    def test_brand_as_bare_string(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": "AC Schnitzer"}
        </script>
        """
        out = truth_from_html(html)
        _assert_shape(out)
        assert out["manufacturer"] == "AC Schnitzer"


class TestTruthFromHtmlMalformedJsonLd:
    def test_malformed_jsonld_falls_through_silently(self, caplog: pytest.LogCaptureFixture) -> None:
        html = """
        <script type="application/ld+json">{not valid json,,,}</script>
        <div itemscope itemtype="https://schema.org/Product">
          <span itemprop="brand">Rogue Engineering</span>
        </div>
        """
        with caplog.at_level(logging.DEBUG):
            out = truth_from_html(html)
        _assert_shape(out)
        # Microdata fallback wins because JSON-LD failed to parse
        assert out["manufacturer"] == "Rogue Engineering"

    def test_jsonld_with_no_brand_falls_through_to_microdata(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "Some part"}
        </script>
        <div itemscope itemtype="https://schema.org/Product">
          <span itemprop="brand">Rogue Engineering</span>
        </div>
        """
        out = truth_from_html(html)
        _assert_shape(out)
        assert out["manufacturer"] == "Rogue Engineering"


class TestTruthFromHtmlMicrodataOnly:
    def test_microdata_brand_picked_up(self) -> None:
        html = """
        <div itemscope itemtype="https://schema.org/Product">
          <span itemprop="brand">AC Schnitzer</span>
          <span itemprop="category">Wheels</span>
        </div>
        """
        out = truth_from_html(html)
        _assert_shape(out)
        assert out["manufacturer"] == "AC Schnitzer"
        assert out["category"] == "Wheels"


class TestTruthFromHtmlOpenGraphOnly:
    def test_og_brand_picked_up(self) -> None:
        html = """
        <head>
          <meta property="og:brand" content="Bilstein" />
          <meta property="product:category" content="Suspension" />
        </head>
        """
        out = truth_from_html(html)
        _assert_shape(out)
        assert out["manufacturer"] == "Bilstein"
        assert out["category"] == "Suspension"


class TestTruthFromHtmlPrecedence:
    def test_jsonld_wins_over_microdata_and_og(self) -> None:
        html = """
        <head>
          <meta property="og:brand" content="OG-Brand" />
        </head>
        <body>
          <script type="application/ld+json">
          {"@type": "Product", "name": "p", "brand": "JSONLD-Brand"}
          </script>
          <div itemscope itemtype="https://schema.org/Product">
            <span itemprop="brand">Microdata-Brand</span>
          </div>
        </body>
        """
        out = truth_from_html(html)
        _assert_shape(out)
        assert out["manufacturer"] == "JSONLD-Brand"

    def test_microdata_wins_over_og_when_no_jsonld(self) -> None:
        html = """
        <head>
          <meta property="og:brand" content="OG-Brand" />
        </head>
        <body>
          <div itemscope itemtype="https://schema.org/Product">
            <span itemprop="brand">Microdata-Brand</span>
          </div>
        </body>
        """
        out = truth_from_html(html)
        _assert_shape(out)
        assert out["manufacturer"] == "Microdata-Brand"


class TestTruthFromHtmlEmptyOrNone:
    def test_empty_string_returns_empty_truth(self) -> None:
        out = truth_from_html("")
        _assert_shape(out)
        assert out["car_triples"] == []
        assert out["manufacturer"] is None
        assert out["category"] is None

    def test_none_html_returns_empty_truth(self) -> None:
        # Per the defensive contract, None input must NOT raise.
        out = truth_from_html(None)  # type: ignore[arg-type]
        _assert_shape(out)
        assert out["manufacturer"] is None

    def test_whitespace_only_html(self) -> None:
        out = truth_from_html("   \n\t  ")
        _assert_shape(out)
        assert out["manufacturer"] is None


class TestTruthFromHtmlOversized:
    def test_oversized_input_returns_empty_with_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Construct an HTML payload just over the 5MB cap. We intentionally
        # embed a real JSON-LD block — if the cap WEREN'T enforced, we'd
        # parse and find a brand. The cap forces an early empty return.
        oversized_pad = "x" * (HTML_SIZE_CAP_BYTES + 1)
        html = (
            '<script type="application/ld+json">'
            '{"@type": "Product", "name": "n", "brand": "ShouldNotBeFound"}'
            "</script>" + oversized_pad
        )
        with caplog.at_level(logging.WARNING):
            out = truth_from_html(html)
        _assert_shape(out)
        assert out["manufacturer"] is None
        # Log carries the structured failure reason.
        assert any(
            "truth_extraction_skipped" in r.message or "truth_extraction_skipped" in str(r)
            for r in caplog.records
        ) or any(
            "truth_extraction_skipped" in str(r.args) for r in caplog.records if r.args
        )

    def test_just_under_cap_still_processes(self) -> None:
        # Sanity check: a payload one byte under the cap should still parse.
        small_payload = (
            '<script type="application/ld+json">'
            '{"@type": "Product", "name": "n", "brand": "Bilstein"}'
            "</script>"
        )
        # Pad to just under cap with safe whitespace inside <body>.
        pad_size = HTML_SIZE_CAP_BYTES - len(small_payload) - 50
        if pad_size > 0:
            small_payload = small_payload + "<body>" + (" " * pad_size) + "</body>"
        out = truth_from_html(small_payload)
        _assert_shape(out)
        assert out["manufacturer"] == "Bilstein"


class TestTruthFromHtmlNeverRaises:
    @pytest.mark.parametrize(
        "broken",
        [
            "<html><script type=\"application/ld+json\">{",  # truncated JSON-LD, no closing tags
            "<<<>>>",  # garbage
            "<script type=\"application/ld+json\">null</script>",  # JSON null
            "<script type=\"application/ld+json\">[]</script>",  # JSON empty array
            '<script type="application/ld+json">{"@type": "Product", "brand": null}</script>',
            '<div itemprop="brand">' * 200,  # deeply repeated open tags
        ],
    )
    def test_defensive_inputs(
        self, broken: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            out = truth_from_html(broken)
        _assert_shape(out)


class TestTruthFromHtmlRetailerHints:
    def test_retailer_arg_is_accepted(self) -> None:
        # Explicitly exercise the retailer keyword so we keep the signature stable.
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "X", "brand": "Bilstein"}
        </script>
        """
        out = truth_from_html(html, retailer="bilstein-direct")
        _assert_shape(out)
        assert out["manufacturer"] == "Bilstein"

    def test_unknown_retailer_does_not_raise(self) -> None:
        out = truth_from_html("<html></html>", retailer="some-unknown-retailer")
        _assert_shape(out)
        assert out["manufacturer"] is None
