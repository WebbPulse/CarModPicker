"""
Tests for speedindustry.com adapter.

Speed Industry pages are gated behind a Cloudflare managed JS challenge (see
``app/crawlers/site_problem_notes/speedindustry.md``), so we have not captured a real
product page yet. These tests exercise the adapter against *synthetic* HTML
modeled on the generic JSON-LD ``Product`` shape most e-com platforms emit —
enough to verify the parse path and platform-agnostic fallbacks. Once a real
HTML capture lands under ``backend/tests/crawlers/fixtures/``, replace the
synthetic HTML with the fixture and tighten the assertions.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier2_browser.speedindustry import SpeedIndustryAdapter

SAMPLE_URL = "https://speedindustry.com/hks-hi-power-catback-exhaust-a90-mkv-supra-gr-2020-titanium-tips-dual-exit"


def _json_ld_html(
    *,
    name: str = "HKS Hi-Power Catback Exhaust A90 MKV Supra GR 2020+ Titanium Tips Dual Exit",
    brand: str = "HKS",
    sku: str = "31014-AT015",
    price: str = "1895.00",
    description: str = (
        "HKS Hi-Power catback exhaust system for the A90 MKV Toyota Supra GR 2020+. "
        "Dual exit with titanium tips; T304 stainless construction throughout."
    ),
    image: str = "https://speedindustry.com/cdn/shop/products/hks-hi-power-catback.jpg",
) -> str:
    """Minimal page with a JSON-LD Product block — the shape Shopify / WooCommerce / BigCommerce all emit."""
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
    """Ensure speedindustry.com is routed to this adapter, not the generic fallback."""

    def test_host_maps_to_speedindustry(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "speedindustry"

    def test_www_host_also_maps(self) -> None:
        assert adapter_name_for_product_url("https://www.speedindustry.com/some-slug") == "speedindustry"

    def test_unrelated_host_does_not_map(self) -> None:
        assert adapter_name_for_product_url("https://example.com/some-slug") != "speedindustry"


class TestFetcherTier:
    """Live crawling requires FlareSolverr; adapter must declare the browser tier."""

    def test_declares_browser_tier(self) -> None:
        assert SpeedIndustryAdapter.FETCHER_TIER == "browser"


class TestDiscoverStub:
    """Discovery is intentionally a no-op until FlareSolverr is wired up."""

    def test_yields_no_urls(self) -> None:
        # A fetcher is only constructed if the adapter actually fetches, and
        # FlareSolverr isn't configured in the test env. Bypass __init__ by
        # passing a dummy so we don't trip on FlareSolverrNotConfiguredError.
        adapter = SpeedIndustryAdapter.__new__(SpeedIndustryAdapter)
        assert list(adapter.discover_product_urls()) == []


class TestParseProductPage:
    """End-to-end parse: synthetic HTML → ScrapedPayload."""

    def _adapter(self) -> SpeedIndustryAdapter:
        # Skip fetcher construction; these tests never hit the network.
        return SpeedIndustryAdapter.__new__(SpeedIndustryAdapter)

    def test_json_ld_parses(self) -> None:
        result = self._adapter().parse_product_page(_json_ld_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("HKS Hi-Power Catback Exhaust")
        assert result.part_manufacturer == "HKS"
        assert result.part_number == "31014-AT015"
        assert result.price_cents == 189500
        assert result.product_url == SAMPLE_URL
        assert result.image_urls is not None and len(result.image_urls) >= 1

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD; OG meta + h1 carry the product name and price.
        html = """
        <html><head>
          <meta property="og:title" content="HKS Hi-Power Catback Exhaust - A90 Supra">
          <meta property="og:description" content="HKS Hi-Power catback for A90 Supra.">
          <meta property="og:price:amount" content="1895.00">
        </head><body>
          <h1>HKS Hi-Power Catback Exhaust - A90 Supra</h1>
          <p>SKU: 31014-AT015</p>
        </body></html>
        """
        result = self._adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert "HKS Hi-Power" in result.name
        assert result.part_number == "31014-AT015"
        assert result.price_cents == 189500
        assert result.part_manufacturer == "HKS"

    def test_missing_name_returns_none(self) -> None:
        # No JSON-LD, no og:title, no h1 → nothing to identify the product with.
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert self._adapter().parse_product_page(html, SAMPLE_URL) is None
