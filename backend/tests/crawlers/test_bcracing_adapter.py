"""
Tests for shop.bcracing-na.com adapter: host routing, URL shape guard,
brand collapse, JSON-LD parsing, and DOM/og fallback.

BC Racing NA runs the Shopify default theme on the ``shop.`` subdomain
(see ``adapters/RETAILER_BACKLOG.md``: "Shopify likely. Tier-0."). Tests
run against synthetic HTML modeled on the schema.org ``Product`` block
Shopify emits by default, plus the inline ``var meta = {...}``
analytics blob used as an SKU fallback.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.bcracing import (
    BCRacingAdapter,
    _is_product_url,
    _is_products_child_sitemap,
    _normalize_bcracing_brand,
)

SAMPLE_URL = "https://shop.bcracing-na.com/products/premium-spanner-wrench-set"


def _product_html(
    *,
    name: str = "Premium Spanner Wrench Set",
    brand: str = "BC Racing",
    sku: str = "PREM-SPW-BLK",
    price: str = "69.95",
    description: str = (
        "Don't Get Caught Without Spanner Wrenches! BC Racing is proud to release the premium "
        "spanner wrench! Made out of 6061 aluminum, these new wrenches are designed to "
        "interface with our standard lock rings and provide increased leverage."
    ),
    image: str = "https://shop.bcracing-na.com/cdn/shop/files/Black-Studio-Square.jpg?v=1699972035",
) -> str:
    """Minimal page mirroring Shopify's default schema.org Product JSON-LD block."""
    brand_field = f'"brand":{{"@type":"Brand","name":"{brand}"}},' if brand else ""
    return f"""
    <html><head>
      <meta property="og:title" content="{name}">
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
      <script>
        var meta = {{"product":{{"id":8315663188224,"vendor":"{brand}","handle":"premium-spanner-wrench-set","variants":[{{"id":44063729877248,"price":6995,"sku":"{sku}"}}]}}}};
      </script>
      <media-gallery>
        <img src="{image}">
      </media-gallery>
    </body></html>
    """


class TestAdapterRegistration:
    """The host-to-adapter map routes every bcracing-na.com page through this adapter."""

    def test_shop_subdomain_routes_to_bcracing(self) -> None:
        # The actual Shopify storefront lives on the shop.* subdomain; this
        # is what a Chrome-extension capture will hit most of the time.
        assert adapter_name_for_product_url(SAMPLE_URL) == "bcracing"

    def test_bare_host_routes_to_bcracing(self) -> None:
        # The marketing site at bcracing-na.com also maps here so the
        # archive rescrape pipeline can re-parse any BC Racing-hosted page.
        assert adapter_name_for_product_url("https://bcracing-na.com/products/foo") == "bcracing"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        # The hyphen in "bcracing-na" is load-bearing: a host containing
        # "bcracing" without the "-na" suffix should not be mapped here.
        assert adapter_name_for_product_url("https://example.com/bcracing") == "generic"


class TestProductUrlGuard:
    """Shape guard: any bcracing-na.com URL with ``/products/`` in the path is a product page."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_bare_host_is_product_shape(self) -> None:
        assert _is_product_url("https://bcracing-na.com/products/some-handle")

    def test_non_product_path_rejected(self) -> None:
        # Collections / CMS / cart pages do not have /products/ in the path.
        assert not _is_product_url("https://shop.bcracing-na.com/collections/coilovers")
        assert not _is_product_url("https://bcracing-na.com/series/br-series/")
        assert not _is_product_url("https://shop.bcracing-na.com/cart")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/products/foo")


class TestNormalizeBrand:
    """
    BC's Shopify vendor field shows up as ``BC Racing`` on new SKUs, ``BC``
    on older ones, and occasionally as a slug (``bcracing-na``). All of
    those collapse to the single canonical brand. Third-party vendors
    (rare — spring and top-mount resales) survive unchanged.
    """

    def test_empty_brand_defaults_to_bc_racing(self) -> None:
        assert _normalize_bcracing_brand("") == "BC Racing"
        assert _normalize_bcracing_brand(None) == "BC Racing"

    def test_bc_variants_all_collapse(self) -> None:
        for variant in (
            "BC",
            "BC Racing",
            "bc",
            "bc racing",
            "bcracing",
            "BC-Racing",
            "BCRacing-NA",
            "BC Racing North America",
        ):
            assert _normalize_bcracing_brand(variant) == "BC Racing", variant

    def test_third_party_brand_passes_through(self) -> None:
        # Rare, but BC ships some Swift spring upgrade packages and a few
        # OEM-brand top mounts. A JSON-LD brand that isn't a BC self-
        # spelling must survive so the global part-manufacturer table gets
        # a real third-party row rather than being swallowed under BC.
        assert _normalize_bcracing_brand("Swift Springs") == "Swift Springs"
        assert _normalize_bcracing_brand("Eibach") == "Eibach"

    def test_whitespace_around_variant_still_collapses(self) -> None:
        assert _normalize_bcracing_brand("  BC Racing  ") == "BC Racing"


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape Shopify HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = BCRacingAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "Premium Spanner Wrench Set"
        assert result.part_manufacturer == "BC Racing"
        assert result.part_number == "PREM-SPW-BLK"
        assert result.price_cents == 6995
        assert result.product_url == SAMPLE_URL
        assert result.image_urls and result.image_urls[0].startswith("https://shop.bcracing-na.com/cdn/shop/")

    def test_brand_variant_collapsed_to_canonical(self) -> None:
        # Vendor field spelled "BC" on this product — still maps to the
        # single canonical "BC Racing" row.
        html = _product_html(brand="BC")
        result = BCRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "BC Racing"

    def test_missing_brand_defaults_to_bc_racing(self) -> None:
        # JSON-LD brand absent — the first-party default kicks in rather
        # than running the title-first-word heuristic (which would pick up
        # product words like "BR" / "DS" / "Premium").
        html = _product_html(brand="")
        result = BCRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "BC Racing"

    def test_third_party_brand_passed_through(self) -> None:
        # Co-branded spring upgrade — the third-party brand survives verbatim.
        html = _product_html(brand="Swift Springs", name="Swift 62ID Spring Upgrade - BR Series")
        result = BCRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Swift Springs"

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape pipeline must not feed CMS/collection URLs here.
        result = BCRacingAdapter().parse_product_page(
            _product_html(),
            "https://shop.bcracing-na.com/collections/coilovers",
        )
        assert result is None

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD — adapter should still pull title / description / price
        # from og: meta tags and default the manufacturer to BC Racing.
        html = """
        <html><head>
          <meta property="og:title" content="BR Series Coilovers - BMW E46 M3">
          <meta property="og:description" content="BR Series 30-way damping adjustable coilovers for the BMW E46 M3.">
          <meta property="og:image" content="https://shop.bcracing-na.com/cdn/shop/files/br-e46.jpg">
          <meta property="og:price:amount" content="1195.00">
        </head><body>
          <h1>BR Series Coilovers - BMW E46 M3</h1>
          <script>
            var meta = {"product":{"vendor":"BC Racing","variants":[{"sku":"I-08-BR"}]}};
          </script>
        </body></html>
        """
        result = BCRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("BR Series")
        assert result.part_manufacturer == "BC Racing"
        assert result.part_number == "I-08-BR"
        assert result.price_cents == 119500

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert BCRacingAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestSitemapDiscovery:
    """BC Racing's sitemap.xml index points at sitemap_products / pages /
    collections / blogs siblings; we only want the products children."""

    def test_only_products_sitemaps_match(self) -> None:
        assert _is_products_child_sitemap(
            "https://shop.bcracing-na.com/sitemap_products_1.xml?from=1469290152048&to=6554419757237"
        )
        assert _is_products_child_sitemap("https://shop.bcracing-na.com/sitemap_products_5.xml?from=1&to=2")

    def test_other_sitemaps_skipped(self) -> None:
        for url in (
            "https://shop.bcracing-na.com/sitemap_pages_1.xml?from=1&to=2",
            "https://shop.bcracing-na.com/sitemap_collections_1.xml?from=1&to=2",
            "https://shop.bcracing-na.com/sitemap_blogs_1.xml",
        ):
            assert not _is_products_child_sitemap(url), url


class TestAdapterFetcherTier:
    """BC Racing starts on plain HTTP (tier0); promote to ``tls`` if Cloudflare fires."""

    def test_declares_http_tier(self) -> None:
        # Default tier — BC Racing's Shopify storefront is not TLS-
        # fingerprint-blocked today. If that changes, flip FETCHER_TIER to
        # "tls" and switch the adapter's discover_product_urls to use
        # self.fetcher.
        assert BCRacingAdapter.FETCHER_TIER == "http"
