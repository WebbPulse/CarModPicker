"""
Tests for greddy.com adapter: host routing, URL shape guard, manufacturer
collapse, JSON-LD parsing, and DOM/og fallback.

GReddy is a Shopify storefront on a custom theme (see RETAILER_BACKLOG.md).
JSON-LD ``Product`` is emitted by default. Tests run against synthetic HTML
modeled on the schema.org ``Product`` block Shopify emits for first-party
SKUs, with the gallery wrapped in the theme's custom ``<product-gallery>``
element (not Dawn's ``<media-gallery>``).
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.greddy import (
    GReddyAdapter,
    _is_product_url,
    _normalize_part_manufacturer,
    _strip_greddy_catalog_suffix,
)

SAMPLE_URL = "https://www.greddy.com/products/greddy-supreme-sp-cat-back-honda-ef-crx-civic"


def _product_html(
    *,
    name: str = "GReddy Supreme-SP Cat-Back System - Honda EF CRX/Civic",
    brand: str = "GReddy",
    sku: str = "10158220",
    price: str = "1195.00",
    description: str = "GReddy Supreme SP 2.5 inch full cat-back exhaust for the Honda EF Civic / CRX.",
    image: str = "https://www.greddy.com/cdn/shop/files/IMG_1378_7f3cb896-9625-4192-aa18-b25c7cd92bdc.jpg?v=1776468157&width=2048",
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
      <product-gallery class="product-gallery">
        <div class="product-gallery__media" data-media-type="image">
          <img src="{image}">
        </div>
      </product-gallery>
    </body></html>
    """


class TestAdapterRegistration:
    """The host-to-adapter map routes every greddy.com page through this adapter."""

    def test_www_host_routes_to_greddy(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "greddy"

    def test_bare_host_routes_to_greddy(self) -> None:
        assert adapter_name_for_product_url("https://greddy.com/products/foo") == "greddy"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        # A host that merely contains "greddy" in the path must not route here.
        assert adapter_name_for_product_url("https://example.com/greddy/foo") == "generic"


class TestProductUrlGuard:
    """Shape guard: any greddy.com URL with ``/products/`` in the path is a product page."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_bare_host_is_product_shape(self) -> None:
        assert _is_product_url("https://greddy.com/products/some-handle")

    def test_non_product_path_rejected(self) -> None:
        # Collections / CMS / cart pages do not have /products/ in the path.
        assert not _is_product_url("https://www.greddy.com/collections/exhausts")
        assert not _is_product_url("https://www.greddy.com/pages/about-us")
        assert not _is_product_url("https://www.greddy.com/cart")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/products/foo")


class TestNormalizePartManufacturer:
    """
    GReddy's vendor field shows up as several spellings (``GReddy``, ``Greddy``,
    ``GReddy Performance Products``, ``GPP``, and the JDM parent brand
    ``Trust``). ``_normalize_part_manufacturer`` collapses all of these to the
    single canonical brand without losing rare co-branded third-party SKUs.
    """

    def test_empty_brand_defaults_to_greddy(self) -> None:
        assert _normalize_part_manufacturer("") == "GReddy"
        assert _normalize_part_manufacturer(None) == "GReddy"

    def test_self_variants_all_collapse(self) -> None:
        for variant in (
            "GReddy",
            "Greddy",
            "GREDDY",
            "GReddy Performance Products",
            "GReddy Performance Products, Inc.",
            "GPP",
            "Trust",
            "GReddy / Trust",
            "greddy/trust",
            # Shopify storefront emits ``"brand": "CATALOG"`` on every product —
            # an internal feed tag, not a real manufacturer. Collapses too.
            "CATALOG",
            "catalog",
            "shopgreddy",
        ):
            assert _normalize_part_manufacturer(variant) == "GReddy", variant

    def test_third_party_brand_passes_through(self) -> None:
        # Co-branded SKUs (rare — GReddy is overwhelmingly direct) keep their
        # actual brand so the global part-manufacturer table gets a real
        # third-party row rather than being swallowed under GReddy's name.
        assert _normalize_part_manufacturer("HKS") == "HKS"
        assert _normalize_part_manufacturer("Tomei") == "Tomei"

    def test_whitespace_around_variant_still_collapses(self) -> None:
        assert _normalize_part_manufacturer("  GReddy Performance Products  ") == "GReddy"


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape Shopify HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = GReddyAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("GReddy Supreme-SP")
        assert result.part_manufacturer == "GReddy"
        assert result.part_number == "10158220"
        assert result.price_cents == 119500
        assert result.product_url == SAMPLE_URL
        assert result.image_urls and "cdn/shop/files/" in result.image_urls[0]

    def test_brand_variant_collapsed_to_canonical(self) -> None:
        # Vendor field spelled "Trust" on this product (the JDM parent brand)
        # — still maps to the single canonical "GReddy" row.
        html = _product_html(brand="Trust")
        result = GReddyAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "GReddy"

    def test_long_self_spelling_collapsed(self) -> None:
        html = _product_html(brand="GReddy Performance Products")
        result = GReddyAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "GReddy"

    def test_missing_brand_defaults_to_greddy(self) -> None:
        # JSON-LD brand absent — the default kicks in rather than running the
        # title-first-word heuristic (which would incorrectly pull product
        # words like "Supreme" / "Profec" out of GReddy product titles).
        html = _product_html(brand="")
        result = GReddyAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "GReddy"

    def test_third_party_brand_passed_through(self) -> None:
        # Co-branded SKU — the third-party brand survives verbatim.
        html = _product_html(brand="HKS", name="HKS Hipermax IV GT Coilovers")
        result = GReddyAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "HKS"

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape pipeline must not feed CMS/collection URLs here.
        result = GReddyAdapter().parse_product_page(
            _product_html(),
            "https://www.greddy.com/collections/exhausts",
        )
        assert result is None

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD — adapter should still pull title / description / price
        # from og: meta tags and default the manufacturer to GReddy.
        html = """
        <html><head>
          <meta property="og:title" content="GReddy Spectrum Elite Cat-Back Exhaust - 2017+ Honda Civic Si">
          <meta property="og:description" content="Lightweight stainless cat-back exhaust system for the 10th-gen Civic Si.">
          <meta property="og:image" content="https://www.greddy.com/cdn/shop/files/spectrum-civic-si.jpg?v=1700000000&width=2048">
          <meta property="product:price:amount" content="895.00">
        </head><body>
          <h1>GReddy Spectrum Elite Cat-Back Exhaust - 2017+ Honda Civic Si</h1>
          <p>SKU: 10158901</p>
        </body></html>
        """
        result = GReddyAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("GReddy Spectrum")
        assert result.part_manufacturer == "GReddy"
        assert result.part_number == "10158901"
        assert result.price_cents == 89500

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert GReddyAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_image_chrome_filtered_out(self) -> None:
        # Theme-asset SVGs (cursors, checkmarks, logos) and YouTube preview
        # thumbnails (``/preview_images/``) live in ``/cdn/shop/`` paths but
        # aren't product media — they must not leak into image_urls.
        html = """
        <html><head>
          <meta property="og:image" content="https://www.greddy.com/cdn/shop/files/product-hero.jpg?v=1&width=2048">
          <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "GReddy Oil Cooler Kit - 2JZ-GTE",
            "sku": "12024601",
            "brand": {"@type": "Brand", "name": "GReddy"},
            "image": ["https://www.greddy.com/cdn/shop/files/product-hero.jpg"],
            "offers": {"@type": "Offer", "price": "595.00", "priceCurrency": "USD"}
          }
          </script>
        </head><body>
          <product-gallery>
            <div class="product-gallery__media" data-media-type="image">
              <img src="//www.greddy.com/cdn/shop/files/product-hero.jpg?v=1&width=2048">
            </div>
            <div class="product-gallery__media" data-media-type="image">
              <img src="//www.greddy.com/cdn/shop/files/oil-cooler-side.jpg?v=1&width=2048">
            </div>
            <div class="product-gallery__media" data-media-type="external_video">
              <img src="//www.greddy.com/cdn/shop/files/preview_images/hqdefault.jpg?v=1&width=480">
            </div>
          </product-gallery>
          <img src="//www.greddy.com/cdn/shop/t/26/assets/cursor-zoom-in.svg?v=1">
        </body></html>
        """
        result = GReddyAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        for url in result.image_urls:
            assert "/preview_images/" not in url
            assert "/assets/" not in url
            assert "cursor" not in url.lower()
        # The two real product images should both make it through.
        assert any("product-hero" in u for u in result.image_urls)
        assert any("oil-cooler-side" in u for u in result.image_urls)


class TestStripCatalogSuffix:
    """
    GReddy's storefront mirrors the part_number into JSON-LD ``sku`` with a
    trailing ``" - CTLG"`` (catalog) marker. The suffix is internal feed
    metadata; the adapter strips it before normalize so 800+ products don't
    surface PNs like ``"16520701 - CTLG"``.
    """

    def test_strips_ctlg_suffix(self) -> None:
        assert _strip_greddy_catalog_suffix("16520701 - CTLG") == "16520701"

    def test_strips_full_catalog_suffix(self) -> None:
        assert _strip_greddy_catalog_suffix("12058002 - CATALOG") == "12058002"

    def test_case_insensitive(self) -> None:
        assert _strip_greddy_catalog_suffix("12058002 - ctlg") == "12058002"
        assert _strip_greddy_catalog_suffix("12058002-CTLG") == "12058002"

    def test_no_suffix_returns_unchanged(self) -> None:
        assert _strip_greddy_catalog_suffix("10158220") == "10158220"

    def test_none_returns_none(self) -> None:
        assert _strip_greddy_catalog_suffix(None) is None
        assert _strip_greddy_catalog_suffix("") == ""

    def test_full_page_strips_ctlg_from_jsonld_sku(self) -> None:
        # End-to-end: a real product page where Shopify emits ``sku``
        # carrying the ``" - CTLG"`` suffix. Adapter must strip before
        # storing, so the part_number is just the bare code.
        html = _product_html(brand="CATALOG", sku="16520701 - CTLG")
        result = GReddyAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "16520701"
        assert result.part_manufacturer == "GReddy"


class TestAdapterFetcherTier:
    """GReddy starts on plain HTTP (tier0); promote to ``tls`` if Cloudflare fires."""

    def test_declares_http_tier(self) -> None:
        # Default tier — GReddy's Shopify storefront is not TLS-fingerprint-
        # blocked today. If that changes, flip FETCHER_TIER to "tls" and
        # switch the adapter's discover_product_urls to use self.fetcher.
        assert GReddyAdapter.FETCHER_TIER == "http"
