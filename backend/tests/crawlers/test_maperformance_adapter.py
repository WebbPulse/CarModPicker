"""Tests for maperformance.com adapter: ProductGroup JSON-LD parsing + DOM fallback."""

from app.crawlers.adapters.maperformance import (
    MAPerformanceAdapter,
    _extract_product_group_from_json_ld,
    _payload_from_product_group,
)

SAMPLE_URL = "https://www.maperformance.com/products/" "perrin-turbo-sump-restrictor-2018-2023-subaru-wrx-psp-eng-630"


def _product_group_html(
    *,
    name: str = "Perrin Turbo Sump Restrictor | 2018-2023 Subaru WRX (PSP-ENG-630)",
    brand: str = "Perrin Performance",
    sku: str = "PER PSP-ENG-630",
    price: str = "48.45",
    description: str = "2018-2023 Subaru WRX Turbo Sump Restrictor by Perrin. Eliminates burning oil.",
    image: str = (
        "https://www.maperformance.com/cdn/shop/products/"
        "perrin-performance-per-psp-eng-630-30026619191366.jpg?v=1751467331&width=480"
    ),
) -> str:
    """Minimal page that mirrors MAP's ProductGroup-with-hasVariant JSON-LD shape."""
    return f"""
    <html><head>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{description}">
      <meta property="og:price:amount" content="{price}">
      <meta property="og:price:currency" content="USD">
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org",
        "@type": "ProductGroup",
        "brand": {{"@type": "Brand", "name": "{brand}"}},
        "productID": "{sku}",
        "description": "{description}",
        "url": "{SAMPLE_URL}",
        "name": "{name}",
        "image": ["{image}"],
        "hasVariant": [{{
          "@type": "Product",
          "name": "{name}",
          "image": "{image}",
          "description": "{description}",
          "sku": "{sku}",
          "mpn": "{sku}",
          "gtin": null,
          "offers": [{{
            "@type": "Offer",
            "price": "{price}",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
          }}]
        }}]
      }}
      </script>
    </head><body><h1>{name}</h1></body></html>
    """


class TestProductGroupExtraction:
    """The shared extract_json_ld_product only matches @type=Product, so MAP needs
    its own ProductGroup-aware extractor that drills into hasVariant for sku/price."""

    def test_finds_product_group_block(self) -> None:
        group = _extract_product_group_from_json_ld(_product_group_html())
        assert group is not None
        assert group.get("@type") == "ProductGroup"
        assert isinstance(group.get("hasVariant"), list)

    def test_payload_pulls_variant_fields(self) -> None:
        group = _extract_product_group_from_json_ld(_product_group_html())
        assert group is not None
        payload = _payload_from_product_group(group, SAMPLE_URL)
        assert payload is not None
        assert payload.name.startswith("Perrin Turbo Sump Restrictor")
        assert payload.part_manufacturer == "Perrin Performance"
        assert payload.part_number == "PER PSP-ENG-630"
        assert payload.price_cents == 4845
        assert payload.product_url == SAMPLE_URL
        assert payload.image_urls and payload.image_urls[0].startswith(
            "https://www.maperformance.com/cdn/shop/products/"
        )

    def test_no_product_group_returns_none(self) -> None:
        html = '<html><head><script type="application/ld+json">'
        html += '{"@type": "WebPage", "name": "x"}'
        html += "</script></head></html>"
        assert _extract_product_group_from_json_ld(html) is None


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape HTML → ScrapedPayload."""

    def test_full_page_parses(self) -> None:
        result = MAPerformanceAdapter().parse_product_page(_product_group_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Perrin Turbo Sump Restrictor")
        assert result.part_manufacturer == "Perrin Performance"
        assert result.part_number == "PER PSP-ENG-630"
        assert result.price_cents == 4845
        assert result.gtin is None
        assert result.image_urls and len(result.image_urls) == 1

    def test_third_party_brand_passes_through(self) -> None:
        # MAP carries many brands; each should keep its own identity.
        html = _product_group_html(brand="COBB Tuning", sku="COB AP3-SUB-004")
        result = MAPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "COBB Tuning"
        assert result.part_number == "COB AP3-SUB-004"

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD at all — adapter should still pull title / description /
        # price from og: meta tags. (Production MAP pages always emit JSON-LD
        # ProductGroup, so this path is just defensive.)
        html = """
        <html><head>
          <meta property="og:title" content="Perrin Cold Air Intake | 2022-2024 Subaru WRX">
          <meta property="og:description" content="Perrin cold air intake replaces the restrictive factory airbox.">
          <meta property="og:price:amount" content="395.00">
        </head><body>
          <h1>Perrin Cold Air Intake | 2022-2024 Subaru WRX</h1>
          <p>SKU: PSP-INT-330</p>
        </body></html>
        """
        result = MAPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert "Cold Air Intake" in result.name
        assert result.part_number == "PSP-INT-330"
        assert result.price_cents == 39500

    def test_missing_name_returns_none(self) -> None:
        # No JSON-LD, no og:title, no h1 → cannot identify product.
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert MAPerformanceAdapter().parse_product_page(html, SAMPLE_URL) is None
