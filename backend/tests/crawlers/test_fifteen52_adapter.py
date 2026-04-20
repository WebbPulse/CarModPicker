"""
Tests for fifteen52.com adapter: host routing, URL shape guard, manufacturer
collapse, JSON-LD parsing, and DOM/og fallback.

fifteen52 is a modern Shopify storefront (RETAILER_BACKLOG: "direct forged
wheels"). Tests run against synthetic HTML modeled on the real JSON-LD
``Product`` block and ``var meta`` analytics the live storefront emits.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.fifteen52 import (
    Fifteen52Adapter,
    _is_product_url,
    _normalize_part_manufacturer,
)

SAMPLE_URL = "https://fifteen52.com/products/107mm-classic-hd-cap-_-asphalt-black"


def _product_html(
    *,
    name: str = "107mm Classic HD Cap _ Asphalt Black",
    brand: str = "fifteen52",
    sku: str = "52-HD-CAPL-AB-CL",
    price: str = "30.00",
    description: str = "Classic locking hub-style cap with FIFTEEN52 branding.",
    image: str = "https://fifteen52.com/cdn/shop/files/107_NEW_HD_CAPS.939.png?v=1767753068&width=1920",
) -> str:
    """Minimal page mirroring Shopify's default schema.org Product JSON-LD block."""
    brand_field = f'"brand":{{"@type":"Brand","name":"{brand}"}},' if brand else ""
    return f"""
    <html><head>
      <meta property="og:url" content="{SAMPLE_URL}">
      <meta property="og:title" content="{name}">
      <meta property="og:type" content="product">
      <meta property="og:description" content="{description}">
      <meta property="og:image" content="{image}">
      <meta property="og:price:amount" content="{price}">
      <meta property="og:price:currency" content="USD">
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "{name}",
        "description": "{description}",
        {brand_field}
        "sku": "{sku}",
        "image": "{image}",
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
    """Host-to-adapter routing covers fifteen52.com apex and the www subdomain."""

    def test_apex_host_routes_to_fifteen52(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "fifteen52"

    def test_www_host_routes_to_fifteen52(self) -> None:
        # The apex 301s to www in some environments; the reverse also happens
        # in the wild. Both hosts must land on the same adapter.
        assert adapter_name_for_product_url("https://www.fifteen52.com/products/foo") == "fifteen52"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/products/fifteen52") == "generic"


class TestProductUrlGuard:
    """Any fifteen52.com URL with ``/products/`` in the path is a product page."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_www_host_is_product_shape(self) -> None:
        assert _is_product_url("https://www.fifteen52.com/products/some-handle")

    def test_non_product_path_rejected(self) -> None:
        # Collections / CMS / cart pages don't live under /products/.
        assert not _is_product_url("https://fifteen52.com/collections/wheels")
        assert not _is_product_url("https://fifteen52.com/pages/about")
        assert not _is_product_url("https://fifteen52.com/cart")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/products/foo")


class TestNormalizePartManufacturer:
    """
    fifteen52's vendor field is usually all-lowercase (matching the brand's
    styling), occasionally title-case or uppercase. All self-spellings collapse
    to one canonical row so the global part-manufacturer table stays clean.
    """

    def test_empty_brand_defaults_to_fifteen52(self) -> None:
        assert _normalize_part_manufacturer("") == "fifteen52"
        assert _normalize_part_manufacturer(None) == "fifteen52"

    def test_fifteen52_variants_all_collapse(self) -> None:
        for variant in ("fifteen52", "Fifteen52", "FIFTEEN52", "fifteen 52", "fifteen-52", "fifteen52 wheels"):
            assert _normalize_part_manufacturer(variant) == "fifteen52", variant

    def test_third_party_brand_passes_through(self) -> None:
        # Co-branded SKUs — Project 6GR (R35 GT-R wheels) or OE hardware —
        # must survive so the global part-manufacturer table gets a real
        # third-party row rather than being swallowed under fifteen52's name.
        assert _normalize_part_manufacturer("Project 6GR") == "Project 6GR"
        assert _normalize_part_manufacturer("52offroad") == "52offroad"

    def test_whitespace_around_variant_still_collapses(self) -> None:
        assert _normalize_part_manufacturer("  fifteen52  ") == "fifteen52"


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape fifteen52 HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = Fifteen52Adapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "107mm Classic HD Cap _ Asphalt Black"
        assert result.part_manufacturer == "fifteen52"
        assert result.part_number == "52-HD-CAPL-AB-CL"
        assert result.price_cents == 3000
        assert result.product_url == SAMPLE_URL
        assert result.image_urls and result.image_urls[0].startswith("https://fifteen52.com/cdn/shop/")

    def test_brand_variant_collapsed_to_canonical(self) -> None:
        # JSON-LD brand uses the title-case spelling on this product — still
        # maps to the single canonical all-lowercase brand row.
        html = _product_html(brand="Fifteen52")
        result = Fifteen52Adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "fifteen52"

    def test_missing_brand_defaults_to_fifteen52(self) -> None:
        # JSON-LD brand absent — default kicks in rather than leaving the row
        # without a manufacturer.
        html = _product_html(brand="")
        result = Fifteen52Adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "fifteen52"

    def test_third_party_brand_passed_through(self) -> None:
        # Co-branded R35 GT-R wheel — Project 6GR survives verbatim so the
        # cross-brand row lands on the real manufacturer.
        html = _product_html(
            brand="Project 6GR",
            name="Project 6GR x fifteen52 R35 GT-R Forged Wheel",
            sku="P6GR-52-GTR-R35-01",
        )
        result = Fifteen52Adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Project 6GR"
        assert result.part_number == "P6GR-52-GTR-R35-01"

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape pipeline must not feed CMS / collection URLs here.
        result = Fifteen52Adapter().parse_product_page(
            _product_html(),
            "https://fifteen52.com/collections/wheels",
        )
        assert result is None

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD — adapter should still pull title / description / price
        # from og: meta tags and default the manufacturer to fifteen52.
        html = """
        <html><head>
          <meta property="og:title" content="Tarmac Silverstone Grey 17x7 ET42 4x100">
          <meta property="og:description" content="Rally-inspired cast wheel for Fiesta ST, Focus ST, and MINI fitments.">
          <meta property="og:image" content="https://fifteen52.com/cdn/shop/files/tarmac-silverstone.jpg">
          <meta property="product:price:amount" content="245.00">
        </head><body>
          <h1>Tarmac Silverstone Grey 17x7 ET42 4x100</h1>
          <p>SKU: 52-TAR-1770-42-4100-SG</p>
        </body></html>
        """
        result = Fifteen52Adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Tarmac Silverstone Grey")
        assert result.part_manufacturer == "fifteen52"
        assert result.part_number == "52-TAR-1770-42-4100-SG"
        assert result.price_cents == 24500

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Sold out.</p></body></html>"
        assert Fifteen52Adapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """fifteen52's Shopify store works on plain HTTP (tier0)."""

    def test_declares_http_tier(self) -> None:
        # fifteen52.com is Cloudflare-fronted Shopify but serves robots.txt,
        # sitemap, and product pages to plain ``requests`` + crawler UA today.
        # Promote to ``tls`` if ``cf-mitigated: challenge`` starts appearing.
        assert Fifteen52Adapter.FETCHER_TIER == "http"
