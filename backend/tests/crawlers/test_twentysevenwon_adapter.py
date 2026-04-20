"""
Tests for 27won.com adapter: host routing, URL shape guard, manufacturer
collapse, JSON-LD parsing, and DOM/og fallback.

27WON is a modern Shopify storefront (see RETAILER_BACKLOG.md: "Shopify.
Tier-0."). Tests run against synthetic HTML modeled on the schema.org
``Product`` block Shopify emits by default.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.twentysevenwon import (
    TwentySevenWonAdapter,
    _is_product_url,
    _normalize_part_manufacturer,
)

SAMPLE_URL = "https://www.27won.com/products/fk8-civic-type-r-intake-manifold"


def _product_html(
    *,
    name: str = "27WON FK8 Civic Type R Intake Manifold",
    brand: str = "27WON Performance",
    sku: str = "27W-IM-FK8-001",
    price: str = "899.00",
    description: str = "Cast-aluminum intake manifold for the FK8 Civic Type R, developed with 27WON's FL5 program.",
    image: str = "https://cdn.shopify.com/s/files/1/0001/27won-fk8-manifold.jpg",
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
    """The host-to-adapter map routes every 27won.com page through this adapter."""

    def test_www_host_routes_to_27won(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "27won"

    def test_bare_host_routes_to_27won(self) -> None:
        assert adapter_name_for_product_url("https://27won.com/products/foo") == "27won"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        # A host containing "27won" as a substring but not the actual domain
        # must not be mapped here.
        assert adapter_name_for_product_url("https://example.com/27won") == "generic"


class TestProductUrlGuard:
    """Shape guard: any 27won.com URL with ``/products/`` in the path is a product page."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_bare_host_is_product_shape(self) -> None:
        assert _is_product_url("https://27won.com/products/some-handle")

    def test_non_product_path_rejected(self) -> None:
        # Collections / CMS / cart pages do not have /products/ in the path.
        assert not _is_product_url("https://www.27won.com/collections/civic-type-r")
        assert not _is_product_url("https://www.27won.com/pages/about")
        assert not _is_product_url("https://www.27won.com/cart")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/products/foo")


class TestNormalizePartManufacturer:
    """
    27WON's Shopify vendor field is inconsistent (``27WON``, ``27WON Performance``,
    ``27 WON``, empty). ``_normalize_part_manufacturer`` collapses all self-
    spellings to a single canonical brand without losing rare co-branded SKUs.
    """

    def test_empty_brand_defaults_to_27won_performance(self) -> None:
        assert _normalize_part_manufacturer("") == "27WON Performance"
        assert _normalize_part_manufacturer(None) == "27WON Performance"

    def test_27won_variants_all_collapse(self) -> None:
        for variant in (
            "27WON",
            "27won",
            "27 WON",
            "27-WON",
            "27WON Performance",
            "27won performance",
            "27 Won Performance",
            "27WON Performance Inc",
            "27WON Performance, Inc.",
        ):
            assert _normalize_part_manufacturer(variant) == "27WON Performance", variant

    def test_third_party_brand_passes_through(self) -> None:
        # 27WON has shipped co-branded / collab SKUs with other Honda vendors.
        # A JSON-LD brand that isn't a 27WON self-spelling must survive so the
        # global part-manufacturer table gets a real third-party row rather
        # than being swallowed under 27WON's name.
        assert _normalize_part_manufacturer("Hondata") == "Hondata"
        assert _normalize_part_manufacturer("PRL Motorsports") == "PRL Motorsports"

    def test_whitespace_around_variant_still_collapses(self) -> None:
        assert _normalize_part_manufacturer("  27WON Performance  ") == "27WON Performance"


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape Shopify HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = TwentySevenWonAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("27WON FK8")
        assert result.part_manufacturer == "27WON Performance"
        assert result.part_number == "27W-IM-FK8-001"
        assert result.price_cents == 89900
        assert result.product_url == SAMPLE_URL
        assert result.image_urls and result.image_urls[0].startswith("https://cdn.shopify.com/")

    def test_brand_variant_collapsed_to_canonical(self) -> None:
        # Vendor field spelled "27WON" on this product — still maps to the
        # single canonical "27WON Performance" row.
        html = _product_html(brand="27WON")
        result = TwentySevenWonAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "27WON Performance"

    def test_missing_brand_defaults_to_27won_performance(self) -> None:
        # JSON-LD brand absent — the default kicks in rather than running the
        # title-first-word heuristic (which would pick "27WON" from the title,
        # still correct here, but defensive for product lines that lead with a
        # product word like "Billet" or "Short").
        html = _product_html(brand="")
        result = TwentySevenWonAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "27WON Performance"

    def test_third_party_brand_passed_through(self) -> None:
        # Co-branded SKU — the third-party brand survives verbatim so the
        # part lands on the real manufacturer row rather than being swallowed
        # under 27WON's name.
        html = _product_html(brand="Hondata", name="Hondata FlashPro for FK8 Civic Type R")
        result = TwentySevenWonAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Hondata"

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape pipeline must not feed CMS/collection URLs here.
        result = TwentySevenWonAdapter().parse_product_page(
            _product_html(),
            "https://www.27won.com/collections/civic-type-r",
        )
        assert result is None

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD — adapter should still pull title / description / price
        # from og: meta tags and default the manufacturer to 27WON Performance.
        html = """
        <html><head>
          <meta property="og:title" content="27WON FL5 Civic Type R Short Shifter">
          <meta property="og:description" content="CNC-machined short shifter for the 2023+ FL5 Civic Type R 6-speed.">
          <meta property="og:image" content="https://cdn.shopify.com/s/files/1/0001/27won-fl5-shifter.jpg">
          <meta property="product:price:amount" content="329.00">
        </head><body>
          <h1>27WON FL5 Civic Type R Short Shifter</h1>
          <p>SKU: 27W-SS-FL5-001</p>
        </body></html>
        """
        result = TwentySevenWonAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("27WON FL5")
        assert result.part_manufacturer == "27WON Performance"
        assert result.part_number == "27W-SS-FL5-001"
        assert result.price_cents == 32900

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert TwentySevenWonAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """27WON starts on plain HTTP (tier0); promote to ``tls`` if Cloudflare fires."""

    def test_declares_http_tier(self) -> None:
        # Default tier — 27WON's Shopify storefront is not TLS-fingerprint-
        # blocked today. If that changes, flip FETCHER_TIER to "tls" and
        # switch the adapter's discover_product_urls to use self.fetcher.
        assert TwentySevenWonAdapter.FETCHER_TIER == "http"
