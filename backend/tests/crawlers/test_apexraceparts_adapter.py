"""
Tests for apexraceparts.com adapter: host routing, URL shape guard,
manufacturer collapse, JSON-LD parsing, and DOM/og fallback.

Apex is a modern Shopify storefront (see RETAILER_BACKLOG.md: "Shopify.
Tier-0."). Tests run against synthetic HTML modeled on the schema.org
``Product`` block Shopify emits by default.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.apexraceparts import (
    ApexRacePartsAdapter,
    _is_product_url,
    _normalize_part_manufacturer,
)

SAMPLE_URL = "https://www.apexraceparts.com/products/arc-8-forged"


def _product_html(
    *,
    name: str = "Apex ARC-8 Forged Wheel - 18x10 ET25 - Satin Bronze",
    brand: str = "Apex Race Parts",
    sku: str = "ARC8-18X10-ET25-SB",
    price: str = "849.00",
    description: str = "ARC-8 forged monoblock wheel for BMW M2/M3/M4 track builds.",
    image: str = "https://cdn.shopify.com/s/files/1/0001/apex-arc8-18x10.jpg",
) -> str:
    """Minimal page mirroring Shopify's default schema.org Product JSON-LD block."""
    brand_field = f'"brand":{{"@type":"Brand","name":"{brand}"}},' if brand else ""
    return f"""
    <html><head>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{description}">
      <meta property="og:image" content="{image}">
      <meta property="product:price:amount" content="{price}">
      <meta property="og:price:currency" content="USD">
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "{name}",
        "description": "{description}",
        {brand_field}
        "sku": "{sku}",
        "image": ["{image}"],
        "offers": {{
          "@type": "Offer",
          "price": "{price}",
          "priceCurrency": "USD",
          "availability": "https://schema.org/InStock"
        }}
      }}
      </script>
    </head><body>
      <h1>{name}</h1>
      <media-gallery>
        <img src="{image}">
      </media-gallery>
    </body></html>
    """


class TestAdapterRegistration:
    """The host-to-adapter map routes every apexraceparts.com page through this adapter."""

    def test_www_host_routes_to_apexraceparts(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "apexraceparts"

    def test_bare_host_routes_to_apexraceparts(self) -> None:
        assert adapter_name_for_product_url("https://apexraceparts.com/products/foo") == "apexraceparts"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        # A host that merely contains "apex" (without the full apexraceparts
        # suffix) must not be mapped here — the FCP Apex BMW pads collection,
        # for example, lives on a different retailer.
        assert adapter_name_for_product_url("https://example.com/apex-pads") == "generic"


class TestProductUrlGuard:
    """Shape guard: any apexraceparts.com URL with ``/products/`` in the path is a product page."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_bare_host_is_product_shape(self) -> None:
        assert _is_product_url("https://apexraceparts.com/products/some-handle")

    def test_non_product_path_rejected(self) -> None:
        # Collections / CMS / cart pages do not have /products/ in the path.
        assert not _is_product_url("https://www.apexraceparts.com/collections/wheels")
        assert not _is_product_url("https://www.apexraceparts.com/pages/about")
        assert not _is_product_url("https://www.apexraceparts.com/cart")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/products/foo")


class TestNormalizePartManufacturer:
    """
    Apex's Shopify vendor field is inconsistent (``Apex``, ``APEX``,
    ``Apex Race Parts``, empty). ``_normalize_part_manufacturer`` collapses
    all self-spellings to a single canonical brand without losing the rare
    resold third-party SKU (PFC, G-LOC, Motul).
    """

    def test_empty_brand_defaults_to_apex_race_parts(self) -> None:
        assert _normalize_part_manufacturer("") == "Apex Race Parts"
        assert _normalize_part_manufacturer(None) == "Apex Race Parts"

    def test_apex_variants_all_collapse(self) -> None:
        for variant in (
            "Apex",
            "APEX",
            "apex",
            "Apex Race Parts",
            "APEX RACE PARTS",
            "apex race parts",
            "apex-race-parts",
            "apexraceparts",
        ):
            assert _normalize_part_manufacturer(variant) == "Apex Race Parts", variant

    def test_third_party_brand_passes_through(self) -> None:
        # Apex resells a small number of track consumables under their
        # original brand. Those must survive as their own manufacturer row
        # rather than being swallowed under Apex's name.
        assert _normalize_part_manufacturer("PFC") == "PFC"
        assert _normalize_part_manufacturer("G-LOC") == "G-LOC"
        assert _normalize_part_manufacturer("Motul") == "Motul"

    def test_whitespace_around_variant_still_collapses(self) -> None:
        assert _normalize_part_manufacturer("  Apex Race Parts  ") == "Apex Race Parts"


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape Shopify HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = ApexRacePartsAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Apex ARC-8")
        assert result.part_manufacturer == "Apex Race Parts"
        assert result.part_number == "ARC8-18X10-ET25-SB"
        assert result.price_cents == 84900
        assert result.product_url == SAMPLE_URL
        assert result.image_urls and result.image_urls[0].startswith("https://cdn.shopify.com/")

    def test_brand_variant_collapsed_to_canonical(self) -> None:
        # Vendor field spelled "APEX" on this product — still maps to the
        # single canonical "Apex Race Parts" row.
        html = _product_html(brand="APEX")
        result = ApexRacePartsAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Apex Race Parts"

    def test_missing_brand_defaults_to_apex_race_parts(self) -> None:
        # JSON-LD brand absent — the default kicks in rather than running
        # the title-first-word heuristic (which would pick "Apex" from the
        # title, still correct here, but defensive for product lines named
        # after a wheel model like "ARC-8" or "EC-7" that lead the title).
        html = _product_html(brand="")
        result = ApexRacePartsAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Apex Race Parts"

    def test_third_party_brand_passed_through(self) -> None:
        # Resold SKU — the third-party brand survives verbatim.
        html = _product_html(brand="PFC", name="PFC 08 Compound Brake Pads for BMW F8x M3/M4 Front")
        result = ApexRacePartsAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "PFC"

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape pipeline must not feed CMS/collection URLs here.
        result = ApexRacePartsAdapter().parse_product_page(
            _product_html(),
            "https://www.apexraceparts.com/collections/wheels",
        )
        assert result is None

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD — adapter should still pull title / description / price
        # from og: meta tags and default the manufacturer to Apex Race Parts.
        html = """
        <html><head>
          <meta property="og:title" content="Apex EC-7 Flow-Formed Wheel - 18x9.5 ET35">
          <meta property="og:description" content="EC-7 flow-formed wheel for Porsche Cayman track builds.">
          <meta property="og:image" content="https://cdn.shopify.com/s/files/1/0001/apex-ec7-18x95.jpg">
          <meta property="product:price:amount" content="399.00">
        </head><body>
          <h1>Apex EC-7 Flow-Formed Wheel - 18x9.5 ET35</h1>
          <p>SKU: EC7-18X95-ET35</p>
        </body></html>
        """
        result = ApexRacePartsAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Apex EC-7")
        assert result.part_manufacturer == "Apex Race Parts"
        assert result.part_number == "EC7-18X95-ET35"
        assert result.price_cents == 39900

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert ApexRacePartsAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """Apex starts on plain HTTP (tier0); promote to ``tls`` if Cloudflare fires."""

    def test_declares_http_tier(self) -> None:
        # Default tier — Apex's Shopify storefront is not TLS-fingerprint-
        # blocked today. If that changes, flip FETCHER_TIER to "tls" and
        # switch the adapter's discover_product_urls to use self.fetcher.
        assert ApexRacePartsAdapter.FETCHER_TIER == "http"
