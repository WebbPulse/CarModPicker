"""
Tests for fortuneauto-na.com adapter: Shopify JSON-LD Product parsing with
the first-party brand normalized to "Fortune Auto", plus OG/ShopifyAnalytics
fallbacks for pages that ship without JSON-LD.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.fortuneauto import (
    FORTUNEAUTO_BRAND,
    FortuneAutoAdapter,
    _is_product_url,
    _normalize_fortuneauto_brand,
    _part_number_from_shopify_meta,
)

SAMPLE_URL = "https://fortuneauto-na.com/products/500-series-coilovers-bmw-e46-m3"


def _product_page_html(
    *,
    name: str = "500 Series Coilovers - BMW E46 M3",
    sku: str = "FA-500-BMW-E46M3",
    brand: str = "Fortune Auto",
    description: str = (
        "The 500 Series coilover is a monotube shock with external height "
        "adjustment and 24-click rebound damping for your BMW E46 M3."
    ),
    price: str = "1395.00",
    image_url: str = "https://fortuneauto-na.com/cdn/shop/files/500-series.jpg?v=1700000000",
    include_product: bool = True,
) -> str:
    """Minimal Shopify-shape page with a single JSON-LD Product block."""
    product_block = (
        f"""<script type="application/ld+json">
        {{
          "@context": "https://schema.org/",
          "@type": "Product",
          "name": "{name}",
          "sku": "{sku}",
          "description": "{description}",
          "image": "{image_url}",
          "brand": {{"@type": "Brand", "name": "{brand}"}},
          "offers": {{
            "@type": "Offer",
            "price": "{price}",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
          }}
        }}
        </script>"""
        if include_product
        else ""
    )
    return f"""
    <html><head>
      <title>{name}</title>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{description}">
      <meta property="og:image" content="{image_url}">
      <meta property="og:price:amount" content="{price}">
      <meta property="product:price:amount" content="{price}">
      {product_block}
      <script>
        var meta = {{"product":{{"id":1,"vendor":"{brand}","variants":[{{"id":2,"price":139500,"sku":"{sku}"}}]}}}};
      </script>
    </head><body>
      <h1>{name}</h1>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_bare_host_routes_to_fortuneauto(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "fortuneauto"

    def test_www_host_routes_to_fortuneauto(self) -> None:
        assert adapter_name_for_product_url("https://www.fortuneauto-na.com/products/510-coilovers") == "fortuneauto"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/fortuneauto") == "generic"

    def test_other_fortune_auto_host_not_matched(self) -> None:
        # The adapter is keyed to the -na.com storefront only. A hypothetical
        # fortuneauto.com (parent global site, different storefront) would not
        # share this parser's assumptions, so it must NOT route here.
        assert adapter_name_for_product_url("https://fortuneauto.com/products/thing") == "generic"


class TestIsProductUrl:
    """``/products/<handle>`` on the Fortune Auto host is the only valid shape."""

    def test_bare_product_path_accepted(self) -> None:
        assert _is_product_url("https://fortuneauto-na.com/products/500-series-coilovers")

    def test_www_host_accepted(self) -> None:
        assert _is_product_url("https://www.fortuneauto-na.com/products/510-series-coilovers")

    def test_collection_path_rejected(self) -> None:
        assert not _is_product_url("https://fortuneauto-na.com/collections/bmw")

    def test_pages_path_rejected(self) -> None:
        assert not _is_product_url("https://fortuneauto-na.com/pages/about")

    def test_unrelated_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/products/something")


class TestNormalizeBrand:
    """First-party storefront: every ``fortune auto …`` variant collapses to the canonical form."""

    def test_canonical_name_passes_through(self) -> None:
        assert _normalize_fortuneauto_brand("Fortune Auto") == FORTUNEAUTO_BRAND

    def test_usa_suffix_normalized(self) -> None:
        assert _normalize_fortuneauto_brand("Fortune Auto USA") == FORTUNEAUTO_BRAND

    def test_performance_suffix_normalized(self) -> None:
        assert _normalize_fortuneauto_brand("Fortune Auto Performance") == FORTUNEAUTO_BRAND

    def test_case_insensitive(self) -> None:
        assert _normalize_fortuneauto_brand("fortune auto") == FORTUNEAUTO_BRAND
        assert _normalize_fortuneauto_brand("FORTUNE AUTO USA") == FORTUNEAUTO_BRAND

    def test_empty_defaults_to_canonical(self) -> None:
        # Storefront is first-party so a missing vendor still maps to Fortune Auto.
        assert _normalize_fortuneauto_brand("") == FORTUNEAUTO_BRAND
        assert _normalize_fortuneauto_brand(None) == FORTUNEAUTO_BRAND

    def test_unrelated_brand_preserved(self) -> None:
        # If a co-branded SKU ever ships, keep its real vendor string.
        assert _normalize_fortuneauto_brand("SwiftSprings") == "SwiftSprings"


class TestPartNumberFromShopifyMeta:
    """SKU fallback pulls the first ``sku`` key out of the ShopifyAnalytics meta blob."""

    def test_extracts_sku(self) -> None:
        html = 'var meta = {"product":{"variants":[{"sku":"FA-500-BMW-E46M3"}]}};'
        assert _part_number_from_shopify_meta(html) == "FA-500-BMW-E46M3"

    def test_first_sku_wins(self) -> None:
        # Multi-variant product — we key price/SKU off the first variant.
        html = 'var meta = {"variants":[{"sku":"FA-500-A"},{"sku":"FA-500-B"}]};'
        assert _part_number_from_shopify_meta(html) == "FA-500-A"

    def test_returns_none_when_missing(self) -> None:
        assert _part_number_from_shopify_meta("<html>no meta blob here</html>") is None


class TestParseProductPage:
    """End-to-end parsing against a real-shape Fortune Auto Shopify page."""

    def test_full_page_parses(self) -> None:
        result = FortuneAutoAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "500 Series Coilovers - BMW E46 M3"
        assert result.part_manufacturer == FORTUNEAUTO_BRAND
        assert result.part_number == "FA-500-BMW-E46M3"
        assert result.price_cents == 139500
        assert result.image_urls == ["https://fortuneauto-na.com/cdn/shop/files/500-series.jpg?v=1700000000"]

    def test_brand_suffix_normalized_to_canonical(self) -> None:
        html = _product_page_html(brand="Fortune Auto USA")
        result = FortuneAutoAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == FORTUNEAUTO_BRAND

    def test_non_product_url_returns_none(self) -> None:
        # A collection page captured by mistake — URL filter rejects before parsing.
        bad_url = "https://fortuneauto-na.com/collections/bmw"
        assert FortuneAutoAdapter().parse_product_page(_product_page_html(), bad_url) is None

    def test_missing_json_ld_falls_back_to_og(self) -> None:
        # Rare Shopify theme variant ships without JSON-LD Product — the adapter
        # should still recover name/price/image from OG meta and the Shopify
        # analytics blob so archive rescrapes don't drop the page entirely.
        html = _product_page_html(include_product=False)
        result = FortuneAutoAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name == "500 Series Coilovers - BMW E46 M3"
        assert result.part_manufacturer == FORTUNEAUTO_BRAND
        assert result.part_number == "FA-500-BMW-E46M3"
        assert result.price_cents == 139500

    def test_page_without_name_returns_none(self) -> None:
        # Soft-404 / shell page with no h1, no og:title, no JSON-LD — nothing
        # to build a payload from.
        html = "<html><head><title>Not found</title></head><body></body></html>"
        assert FortuneAutoAdapter().parse_product_page(html, SAMPLE_URL) is None
