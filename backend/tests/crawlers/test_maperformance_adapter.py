"""Tests for maperformance.com adapter: ProductGroup JSON-LD parsing + DOM fallback."""

from app.crawlers.adapters.tier0_http.maperformance import (
    MAPerformanceAdapter,
    _extract_product_group_from_json_ld,
    _payload_from_product_group,
    _strip_map_supplier_prefix,
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
        # MAP's internal "PER PSP-ENG-630" is normalised to the manufacturer's
        # real SKU "PSP-ENG-630" — what Perrin and every other retailer use.
        assert payload.part_number == "PSP-ENG-630"
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
        # PER prefix stripped → manufacturer SKU.
        assert result.part_number == "PSP-ENG-630"
        assert result.price_cents == 4845
        assert result.gtin is None
        assert result.image_urls and len(result.image_urls) == 1

    def test_third_party_brand_passes_through(self) -> None:
        # MAP carries many brands; each should keep its own identity.
        html = _product_group_html(brand="COBB Tuning", sku="COB AP3-SUB-004")
        result = MAPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "COBB Tuning"
        # COB prefix stripped → COBB's actual AccessPort SKU.
        assert result.part_number == "AP3-SUB-004"

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


class TestSupplierPrefixStrip:
    """
    MAP encodes the brand it buys from as a 2–4-letter prefix on every SKU
    (``WHI W53382`` for Whiteline, ``WIS 6501M775`` for Wiseco). Stored
    part_numbers must be the manufacturer's real SKU so build-list dedupe
    matches across retailers.
    """

    def test_three_letter_prefix_stripped(self) -> None:
        assert _strip_map_supplier_prefix("WHI W53382") == "W53382"

    def test_two_letter_prefix_stripped(self) -> None:
        assert _strip_map_supplier_prefix("KN 33-2304") == "33-2304"

    def test_four_letter_prefix_stripped(self) -> None:
        assert _strip_map_supplier_prefix("MISH MMTC-WRX-08") == "MMTC-WRX-08"

    def test_pure_letter_tail_left_alone(self) -> None:
        # When the tail has no digit, the leading word is more likely the
        # actual SKU than a supplier prefix; keep the original.
        assert _strip_map_supplier_prefix("ABC DEF") == "ABC DEF"

    def test_no_prefix_passes_through(self) -> None:
        assert _strip_map_supplier_prefix("PSP-ENG-630") == "PSP-ENG-630"

    def test_lowercase_prefix_not_stripped(self) -> None:
        # MAP's prefix is always uppercase; lowercase is part of the SKU.
        assert _strip_map_supplier_prefix("ks 12345") == "ks 12345"

    def test_none_passes_through(self) -> None:
        assert _strip_map_supplier_prefix(None) is None

    def test_five_letter_prefix_not_stripped(self) -> None:
        # MAP prefixes max out at 4 letters; longer leading words are part
        # of the SKU.
        assert _strip_map_supplier_prefix("ABCDE 12345") == "ABCDE 12345"
