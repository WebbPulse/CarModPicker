"""
Tests for awe-tuning.com adapter: host routing, URL shape guard, manufacturer
collapse, JSON-LD parsing, and DOM/og fallback.

AWE is a modern Shopify storefront (see RETAILER_BACKLOG.md: "Modern
Shopify-style. Tier-0/1."). Tests run against synthetic HTML modeled on the
schema.org ``Product`` block Shopify emits by default.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.awetuning import (
    AWETuningAdapter,
    _is_product_url,
    _normalize_part_manufacturer,
)

SAMPLE_URL = "https://www.awe-tuning.com/products/awe-track-edition-exhaust-for-audi-b9-s4-102mm"


def _product_html(
    *,
    name: str = "AWE Track Edition Exhaust for Audi B9 S4 - Chrome Silver 102mm Tips",
    brand: str = "AWE Tuning",
    sku: str = "3010-42052",
    price: str = "1325.00",
    description: str = "AWE Track Edition Exhaust for the Audi B9 S4, tuned for aggressive sound.",
    image: str = "https://cdn.shopify.com/s/files/1/0001/awe-track-b9-s4.jpg",
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
    """The host-to-adapter map routes every awe-tuning.com page through this adapter."""

    def test_www_host_routes_to_awetuning(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "awetuning"

    def test_bare_host_routes_to_awetuning(self) -> None:
        assert adapter_name_for_product_url("https://awe-tuning.com/products/foo") == "awetuning"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        # The dash in "awe-tuning" is load-bearing: a host containing "awe"
        # without the "awe-tuning" suffix should not be mapped here.
        assert adapter_name_for_product_url("https://example.com/awe-tuning") == "generic"


class TestProductUrlGuard:
    """Shape guard: any awe-tuning.com URL with ``/products/`` in the path is a product page."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_bare_host_is_product_shape(self) -> None:
        assert _is_product_url("https://awe-tuning.com/products/some-handle")

    def test_non_product_path_rejected(self) -> None:
        # Collections / CMS / cart pages do not have /products/ in the path.
        assert not _is_product_url("https://www.awe-tuning.com/collections/audi")
        assert not _is_product_url("https://www.awe-tuning.com/pages/about-us")
        assert not _is_product_url("https://www.awe-tuning.com/cart")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/products/foo")


class TestNormalizePartManufacturer:
    """
    AWE's Shopify vendor field is inconsistent (``AWE``, ``AWE Tuning``, empty).
    ``_normalize_part_manufacturer`` collapses all self-spellings to a single
    canonical brand without losing the rare co-branded third-party SKU.
    """

    def test_empty_brand_defaults_to_awe_tuning(self) -> None:
        assert _normalize_part_manufacturer("") == "AWE Tuning"
        assert _normalize_part_manufacturer(None) == "AWE Tuning"

    def test_awe_variants_all_collapse(self) -> None:
        for variant in ("AWE", "AWE Tuning", "awe", "awe tuning", "AWE-TUNING", "awe-tuning"):
            assert _normalize_part_manufacturer(variant) == "AWE Tuning", variant

    def test_third_party_brand_passes_through(self) -> None:
        # Rare, but AWE has sold co-branded kits in the past. A JSON-LD brand
        # that isn't an AWE self-spelling must survive so the global part-
        # manufacturer table gets a real third-party row rather than being
        # swallowed under AWE's name.
        assert _normalize_part_manufacturer("Giac") == "Giac"
        assert _normalize_part_manufacturer("BMC") == "BMC"

    def test_whitespace_around_variant_still_collapses(self) -> None:
        assert _normalize_part_manufacturer("  AWE Tuning  ") == "AWE Tuning"


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape Shopify HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = AWETuningAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("AWE Track Edition")
        assert result.part_manufacturer == "AWE Tuning"
        assert result.part_number == "3010-42052"
        assert result.price_cents == 132500
        assert result.product_url == SAMPLE_URL
        assert result.image_urls and result.image_urls[0].startswith("https://cdn.shopify.com/")

    def test_brand_variant_collapsed_to_canonical(self) -> None:
        # Vendor field spelled "AWE" on this product — still maps to the
        # single canonical "AWE Tuning" row.
        html = _product_html(brand="AWE")
        result = AWETuningAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "AWE Tuning"

    def test_missing_brand_defaults_to_awe_tuning(self) -> None:
        # JSON-LD brand absent — the default kicks in rather than running the
        # title-first-word heuristic (which would pick "AWE" from the title,
        # still correct here, but defensive for product lines like
        # "Track Edition..." that lead with a product word).
        html = _product_html(brand="")
        result = AWETuningAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "AWE Tuning"

    def test_third_party_brand_passed_through(self) -> None:
        # Co-branded SKU — the third-party brand survives verbatim.
        html = _product_html(brand="Giac", name="GIAC Stage 2 Tune for Audi B9 S4")
        result = AWETuningAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Giac"

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape pipeline must not feed CMS/collection URLs here.
        result = AWETuningAdapter().parse_product_page(
            _product_html(),
            "https://www.awe-tuning.com/collections/audi",
        )
        assert result is None

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD — adapter should still pull title / description / price
        # from og: meta tags and default the manufacturer to AWE Tuning.
        html = """
        <html><head>
          <meta property="og:title" content="AWE Touring Edition Exhaust for BMW F8x M3/M4">
          <meta property="og:description" content="Refined exhaust note, OEM-style fitment for the BMW F8x M3/M4.">
          <meta property="og:image" content="https://cdn.shopify.com/s/files/1/0001/awe-touring-f8x.jpg">
          <meta property="product:price:amount" content="1625.00">
        </head><body>
          <h1>AWE Touring Edition Exhaust for BMW F8x M3/M4</h1>
          <p>SKU: 3015-43046</p>
        </body></html>
        """
        result = AWETuningAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("AWE Touring")
        assert result.part_manufacturer == "AWE Tuning"
        assert result.part_number == "3015-43046"
        assert result.price_cents == 162500

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert AWETuningAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """AWE starts on plain HTTP (tier0); promote to ``tls`` if Cloudflare fires."""

    def test_declares_http_tier(self) -> None:
        # Default tier — AWE's Shopify storefront is not TLS-fingerprint-
        # blocked today. If that changes, flip FETCHER_TIER to "tls" and
        # switch the adapter's discover_product_urls to use self.fetcher.
        assert AWETuningAdapter.FETCHER_TIER == "http"
