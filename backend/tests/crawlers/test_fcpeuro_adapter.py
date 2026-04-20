"""
Tests for fcpeuro.com adapter.

FCP Euro product pages are behind a Cloudflare managed JS challenge
(``site_problem_notes/fcpeuro.md``), so we have not captured a real product page
yet. These tests exercise the adapter against *synthetic* HTML modeled on
Shopify's JSON-LD ``Product`` shape. Once a real capture lands under
``backend/tests/crawlers/fixtures/``, replace the synthetic HTML with the
fixture and tighten the assertions against the actual DOM.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier2_browser.fcpeuro import FCPEuroAdapter

SAMPLE_URL = "https://www.fcpeuro.com/products/bmw-brake-kit-shw-34112284101ktfr33"


def _json_ld_html(
    *,
    name: str = "BMW Brake Kit - Front (E82, E90, E92) - Shaw 34112284101KTFR",
    brand: str = "Shaw",
    sku: str = "34112284101KTFR",
    price: str = "299.99",
    description: str = "Front brake kit for BMW E82/E90/E92 — Shaw-supplied OE replacement rotors and pads.",
    image: str = "https://cdn.shopify.com/s/files/1/0001/0001/products/shaw-brake-kit.jpg",
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
    def test_host_maps_to_fcpeuro(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "fcpeuro"

    def test_bare_host_also_maps(self) -> None:
        assert adapter_name_for_product_url("https://fcpeuro.com/products/some-slug") == "fcpeuro"

    def test_unrelated_host_does_not_map(self) -> None:
        assert adapter_name_for_product_url("https://example.com/products/bmw-brake-kit") != "fcpeuro"


class TestFetcherTier:
    def test_declares_browser_tier(self) -> None:
        assert FCPEuroAdapter.FETCHER_TIER == "browser"


class TestDiscoverStub:
    def test_yields_no_urls(self) -> None:
        # Bypass __init__ to avoid constructing a FlareSolverr fetcher in tests.
        adapter = FCPEuroAdapter.__new__(FCPEuroAdapter)
        assert list(adapter.discover_product_urls()) == []


class TestParseProductPage:
    def _adapter(self) -> FCPEuroAdapter:
        return FCPEuroAdapter.__new__(FCPEuroAdapter)

    def test_json_ld_parses(self) -> None:
        result = self._adapter().parse_product_page(_json_ld_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("BMW Brake Kit")
        assert result.part_manufacturer == "Shaw"
        assert result.part_number == "34112284101KTFR"
        assert result.price_cents == 29999
        assert result.product_url == SAMPLE_URL
        assert result.image_urls is not None and len(result.image_urls) >= 1

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        html = """
        <html><head>
          <meta property="og:title" content="Shaw Brake Kit - BMW E90">
          <meta property="og:description" content="Shaw front brake kit for BMW E90.">
          <meta property="og:price:amount" content="299.99">
        </head><body>
          <h1>Shaw Brake Kit - BMW E90</h1>
          <p>SKU: 34112284101KTFR</p>
        </body></html>
        """
        result = self._adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert "Shaw Brake Kit" in result.name
        assert result.part_number == "34112284101KTFR"
        assert result.price_cents == 29999

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert self._adapter().parse_product_page(html, SAMPLE_URL) is None
