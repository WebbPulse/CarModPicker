"""
Tests for jegs.com adapter.

JEGS product pages are behind a Cloudflare managed JS challenge
(``site_problem_notes/jegs.md``), so we have not captured a real product page yet.
These tests exercise the adapter against synthetic HTML and verify the
URL-derived brand/part-number fallback — the JEGS URL shape
``/i/<brand>/<mfr-prefix>/<mfr-sku>/<internal>/-1`` carries both fields and
is a useful last-resort path when HTML parsing fails.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier2_browser.jegs import JegsAdapter, _brand_and_sku_from_url

SAMPLE_URL = "https://www.jegs.com/i/JEGS/555/513001/10002/-1"


def _json_ld_html(
    *,
    name: str = "JEGS Aluminum Cylinder Heads",
    brand: str = "JEGS",
    sku: str = "555-513001",
    price: str = "999.99",
    description: str = "JEGS aluminum cylinder heads for small-block Chevy. 64cc combustion chambers.",
    image: str = "https://www.jegs.com/images/dealerstemplate/555-513001.jpg",
) -> str:
    return f"""
    <html><head>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{description}">
      <meta property="og:image" content="{image}">
      <meta property="og:price:amount" content="{price}">
      <meta property="og:price:currency" content="USD">
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "{name}",
        "description": "{description}",
        "brand": {{"@type": "Brand", "name": "{brand}"}},
        "sku": "{sku}",
        "mpn": "{sku}",
        "image": ["{image}"],
        "offers": {{
          "@type": "Offer",
          "price": "{price}",
          "priceCurrency": "USD",
          "availability": "https://schema.org/InStock"
        }}
      }}
      </script>
    </head><body><h1>{name}</h1></body></html>
    """


class TestAdapterRegistration:
    def test_host_maps_to_jegs(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "jegs"

    def test_bare_host_also_maps(self) -> None:
        assert adapter_name_for_product_url("https://jegs.com/i/JEGS/555/513001/10002/-1") == "jegs"

    def test_unrelated_host_does_not_map(self) -> None:
        assert adapter_name_for_product_url("https://example.com/i/JEGS/555/513001/10002/-1") != "jegs"


class TestFetcherTier:
    def test_declares_browser_tier(self) -> None:
        assert JegsAdapter.FETCHER_TIER == "browser"


class TestDiscoverStub:
    def test_yields_no_urls(self) -> None:
        adapter = JegsAdapter.__new__(JegsAdapter)
        assert list(adapter.discover_product_urls()) == []


class TestBrandAndSkuFromUrl:
    """URL-derived fallback: the product URL carries brand + part number."""

    def test_canonical_url_yields_brand_and_sku(self) -> None:
        brand, part_number = _brand_and_sku_from_url(SAMPLE_URL)
        assert brand == "JEGS"
        assert part_number == "555-513001"

    def test_third_party_brand_in_url(self) -> None:
        # JEGS carries many brands; the first URL segment carries the brand.
        brand, part_number = _brand_and_sku_from_url("https://www.jegs.com/i/Edelbrock/350/2701/10002/-1")
        assert brand == "Edelbrock"
        assert part_number == "350-2701"

    def test_unrelated_path_yields_nothing(self) -> None:
        brand, part_number = _brand_and_sku_from_url("https://www.jegs.com/about-us")
        assert brand is None
        assert part_number is None


class TestParseProductPage:
    def _adapter(self) -> JegsAdapter:
        return JegsAdapter.__new__(JegsAdapter)

    def test_json_ld_parses(self) -> None:
        result = self._adapter().parse_product_page(_json_ld_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("JEGS Aluminum")
        assert result.part_manufacturer == "JEGS"
        assert result.part_number == "555-513001"
        assert result.price_cents == 99999
        assert result.product_url == SAMPLE_URL

    def test_url_fallback_when_html_has_no_jsonld(self) -> None:
        # No JSON-LD and no SKU in the body — adapter should still produce a
        # usable brand + part number from the URL path.
        html = """
        <html><head>
          <meta property="og:title" content="JEGS Aluminum Cylinder Heads">
          <meta property="og:description" content="JEGS aluminum heads for small-block Chevy.">
        </head><body>
          <h1>JEGS Aluminum Cylinder Heads</h1>
        </body></html>
        """
        result = self._adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "JEGS"
        assert result.part_number == "555-513001"

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert self._adapter().parse_product_page(html, SAMPLE_URL) is None
