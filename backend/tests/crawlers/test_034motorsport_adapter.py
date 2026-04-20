"""Tests for 034motorsport.com adapter: JSON-LD Product parsing + brand normalization + DOM fallback."""

from app.crawlers.adapters.tier0_http.motorsport034 import (
    Motorsport034Adapter,
    _looks_like_product_url,
    _normalize_part_manufacturer,
)

SAMPLE_URL = "https://www.034motorsport.com/034motorsport-m10-main-stud-kit-ea837-3-0t.html"


def _product_page_html(
    *,
    name: str = "034Motorsport M10 Main Stud Kit EA837 3.0T",
    brand: str = "034Motorsport",
    sku: str = "034-201-5038",
    price: str = "407.00",
    description: str = (
        "As power levels increase, the bottom end must be capable of handling sustained torque. "
        "The 034Motorsport M10 Main Stud Kit for EA837 3.0T reinforces the engine foundation."
    ),
    image: str = (
        "https://www.034motorsport.com/media/catalog/product/cache/b9cc29fef90c7cfb7041f226d4b1c753/"
        "0/3/034motorsport-m10-main-stud-kit-ea837-3-0t-034-201-5038-1.jpg"
    ),
) -> str:
    """Minimal page that mirrors 034's Magento Product JSON-LD shape."""
    return f"""
    <html><head>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{description}">
      <meta property="og:image" content="{image}">
      <meta property="product:price:amount" content="{price}">
      <meta property="product:price:currency" content="USD">
      <script type="application/ld+json">
      {{
        "@context": "http://schema.org",
        "@type": "Product",
        "name": "{name}",
        "sku": "{sku}",
        "brand": {{"@type": "Brand", "name": "{brand}"}},
        "model": "{name}",
        "description": "{description}",
        "gtin8": "{sku}",
        "offers": {{
          "@type": "Offer",
          "url": "{SAMPLE_URL}",
          "price": "{price}",
          "priceCurrency": "USD",
          "sku": "{sku}"
        }}
      }}
      </script>
    </head><body><h1>{name}</h1></body></html>
    """


class TestNormalizePartManufacturer:
    """The site is (almost) 100% house-brand; normalize collapses obvious variants
    and rescues the car-make false positive (Audi/VW/Porsche/BMW in title)."""

    def test_empty_brand_defaults_to_034motorsport(self) -> None:
        assert _normalize_part_manufacturer("") == "034Motorsport"
        assert _normalize_part_manufacturer(None) == "034Motorsport"

    def test_brand_variants_collapse(self) -> None:
        for variant in ("034Motorsport", "034 Motorsport", "034Motorsports", "034", "034MOTORSPORT"):
            assert _normalize_part_manufacturer(variant) == "034Motorsport", variant

    def test_car_make_as_brand_rescued(self) -> None:
        # Title heuristic may pick up a car make — the catalog is Audi/VW/Porsche.
        assert _normalize_part_manufacturer("Audi") == "034Motorsport"
        assert _normalize_part_manufacturer("Volkswagen") == "034Motorsport"
        assert _normalize_part_manufacturer("Porsche") == "034Motorsport"
        assert _normalize_part_manufacturer("BMW") == "034Motorsport"

    def test_third_party_brand_passes_through(self) -> None:
        # Rare, but the site does list some third-party brands (tools, fluids).
        assert _normalize_part_manufacturer("Motul") == "Motul"


class TestLooksLikeProductUrl:
    """Sitemap contains product pages and CMS pages on the same flat namespace."""

    def test_product_url_accepted(self) -> None:
        assert _looks_like_product_url("https://www.034motorsport.com/034motorsport-m10-main-stud-kit-ea837-3-0t.html")

    def test_cms_pages_rejected(self) -> None:
        for bad in (
            "https://www.034motorsport.com/home",
            "https://www.034motorsport.com/privacy-policy",
            "https://www.034motorsport.com/contact-us",
            "https://www.034motorsport.com/blog/latest-news.html",
        ):
            assert not _looks_like_product_url(bad), bad

    def test_non_html_rejected(self) -> None:
        assert not _looks_like_product_url("https://www.034motorsport.com/category/brakes")
        assert not _looks_like_product_url("https://www.034motorsport.com/")


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape HTML → ScrapedPayload."""

    def test_full_page_parses(self) -> None:
        result = Motorsport034Adapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "034Motorsport M10 Main Stud Kit EA837 3.0T"
        assert result.part_manufacturer == "034Motorsport"
        assert result.part_number == "034-201-5038"
        assert result.price_cents == 40700
        assert result.product_url == SAMPLE_URL
        # gtin8 on this site actually holds the SKU (not a real 8-digit GTIN);
        # the adapter must not let that reach the payload as a GTIN.
        assert result.gtin is None
        assert result.image_urls and "media/catalog/product" in result.image_urls[0]

    def test_brand_missing_in_jsonld_defaults_to_034(self) -> None:
        html = _product_page_html(brand="")
        result = Motorsport034Adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "034Motorsport"

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD — adapter should still pull title / description / price
        # from og: meta tags (product:price:amount is the Magento convention).
        html = """
        <html><head>
          <meta property="og:title" content="034Motorsport Billet Dogbone Mount Insert Kit, 8V/8S Audi/VW MQB">
          <meta property="og:description" content="Eliminates factory dogbone mount deflection under load.">
          <meta property="product:price:amount" content="129.00">
          <meta property="og:image" content="https://www.034motorsport.com/media/catalog/product/cache/abc/d/o/dogbone-1.jpg">
        </head><body>
          <h1>034Motorsport Billet Dogbone Mount Insert Kit, 8V/8S Audi/VW MQB</h1>
          <p>SKU: 034-509-1015</p>
        </body></html>
        """
        result = Motorsport034Adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert "Dogbone Mount" in result.name
        assert result.part_number == "034-509-1015"
        assert result.price_cents == 12900
        assert result.part_manufacturer == "034Motorsport"

    def test_missing_name_returns_none(self) -> None:
        # No JSON-LD, no og:title, no h1 → cannot identify product.
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert Motorsport034Adapter().parse_product_page(html, SAMPLE_URL) is None
