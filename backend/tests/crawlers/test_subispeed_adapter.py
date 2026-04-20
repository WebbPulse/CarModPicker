"""Tests for subispeed.com adapter: plain Product JSON-LD parsing + DOM fallback + multi-brand pass-through."""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.subispeed import (
    SubispeedAdapter,
    _is_products_child_sitemap,
)

SAMPLE_URL = "https://www.subispeed.com/products/cus-660-911-set-cusco-engine-transmission-mount"


def _shopify_product_html(
    *,
    name: str = "Cusco Motor & Transmission Mount - 2002–2005 Subaru WRX",
    brand: str = "Cusco",
    sku: str = "CUS660 911 SET",
    price: str = "328.50",
    description: str = (
        "This 3 piece mount set is a complete bolt on solution. "
        "It will stiffen up the connection between the engine/transmission and chassis."
    ),
    image: str = (
        "https://www.subispeed.com/cdn/shop/products/" "e437058044f304d95dbe45ac04deee92.jpg?v=1689335397&width=1920"
    ),
) -> str:
    """Minimal page that mirrors Subispeed's plain Product JSON-LD shape."""
    return f"""
    <html><head>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{description}">
      <meta property="og:price:amount" content="{price}">
      <meta property="og:price:currency" content="USD">
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org/",
        "@type": "Product",
        "brand": {{"@type": "Brand", "name": "{brand}"}},
        "category": "Engine Mounts",
        "description": "{description}",
        "image": "{image}",
        "name": "{name}",
        "offers": {{
          "@type": "Offer",
          "availability": "https://schema.org/InStock",
          "price": "{price}",
          "priceCurrency": "USD",
          "url": "{SAMPLE_URL}"
        }},
        "sku": "{sku}",
        "url": "{SAMPLE_URL}"
      }}
      </script>
    </head><body><h1>{name}</h1><media-gallery></media-gallery></body></html>
    """


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape Subispeed HTML → ScrapedPayload."""

    def test_full_page_parses(self) -> None:
        result = SubispeedAdapter().parse_product_page(_shopify_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Cusco Motor")
        assert result.part_manufacturer == "Cusco"
        # Internal space is meaningful on Subispeed SKUs and must be preserved.
        assert result.part_number == "CUS660 911 SET"
        assert result.price_cents == 32850
        assert result.product_url == SAMPLE_URL
        assert result.image_urls and result.image_urls[0].startswith("https://www.subispeed.com/cdn/shop/products/")

    def test_third_party_brands_pass_through(self) -> None:
        # Subispeed is a multi-brand reseller — Perrin, GrimmSpeed, OpenFlash
        # all need to keep their own identity in the catalog (no normalization
        # to a "Subispeed" house brand).
        for brand, sku in (
            ("Perrin Performance", "PER PSP-ENG-630"),
            ("GrimmSpeed", "GRM 060073"),
            ("OpenFlash Performance", "OFT2-FA20-WRX"),
        ):
            html = _shopify_product_html(brand=brand, sku=sku)
            result = SubispeedAdapter().parse_product_page(html, SAMPLE_URL)
            assert result is not None, brand
            assert result.part_manufacturer == brand, brand
            assert result.part_number == sku, brand

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD at all — adapter should still pull title / description /
        # price from og: meta tags. (Production Subispeed pages always emit
        # JSON-LD Product, so this path is just defensive.)
        html = """
        <html><head>
          <meta property="og:title" content="GrimmSpeed Cold Air Intake | 2022-2024 Subaru WRX">
          <meta property="og:description" content="GrimmSpeed cold air intake replaces the factory airbox.">
          <meta property="og:price:amount" content="425.00">
        </head><body>
          <h1>GrimmSpeed Cold Air Intake | 2022-2024 Subaru WRX</h1>
          <p>SKU: GRM060073</p>
        </body></html>
        """
        result = SubispeedAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert "Cold Air Intake" in result.name
        assert result.part_number == "GRM060073"
        assert result.price_cents == 42500

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert SubispeedAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestSitemapDiscovery:
    """Subispeed's sitemap.xml index points at sitemap_products / pages /
    collections / blogs siblings; we only want the products children."""

    def test_only_products_sitemaps_match(self) -> None:
        assert _is_products_child_sitemap(
            "https://www.subispeed.com/sitemap_products_1.xml?from=8363175543073&to=8733126000929"
        )
        assert _is_products_child_sitemap("https://www.subispeed.com/sitemap_products_2.xml?from=1&to=2")

    def test_other_sitemaps_skipped(self) -> None:
        for url in (
            "https://www.subispeed.com/sitemap_pages_1.xml?from=1&to=2",
            "https://www.subispeed.com/sitemap_collections_1.xml?from=1&to=2",
            "https://www.subispeed.com/sitemap_blogs_1.xml",
        ):
            assert not _is_products_child_sitemap(url), url


class TestUrlMapping:
    """Subispeed product URLs route to the subispeed adapter."""

    def test_subispeed_hosts(self) -> None:
        assert adapter_name_for_product_url("https://subispeed.com/products/foo") == "subispeed"
        assert adapter_name_for_product_url("https://www.subispeed.com/products/foo") == "subispeed"
