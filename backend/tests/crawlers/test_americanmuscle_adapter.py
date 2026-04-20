"""
Tests for americanmuscle.com adapter.

American Muscle product pages are expected behind heavy anti-bot
(``site_problem_notes/americanmuscle.md``), so we have not captured a real
product page yet. These tests exercise the adapter against *synthetic* HTML
modeled on a generic schema.org ``Product`` block. Once a real capture lands
under ``backend/tests/crawlers/fixtures/americanmuscle/``, replace the
synthetic HTML with the fixture and tighten the assertions against the actual
DOM (SKU block, fitment data, price formatting).

Unlike the JEGS / ECS adapters, American Muscle does *not* do URL-derived
brand/SKU fallback — AM slugs are freeform marketing strings (see the
adapter module docstring), so there is no regex test here.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier2_browser.americanmuscle import AmericanMuscleAdapter

SAMPLE_URL = "https://www.americanmuscle.com/mmd-slotted-hood-07-09.html"


def _json_ld_html(
    *,
    name: str = "MMD Slotted Hood (07-09 GT)",
    brand: str = "MMD",
    sku: str = "J110088",
    price: str = "549.99",
    description: str = "MMD slotted hood for 2007-2009 Mustang GT. Functional heat-extraction vents.",
    image: str = "https://www.americanmuscle.com/images/products/J110088.jpg",
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
    def test_host_maps_to_americanmuscle(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "americanmuscle"

    def test_bare_host_also_maps(self) -> None:
        assert (
            adapter_name_for_product_url("https://americanmuscle.com/borla-s-type-axleback-exhaust-11-12gt.html")
            == "americanmuscle"
        )

    def test_unrelated_host_does_not_map(self) -> None:
        assert adapter_name_for_product_url("https://example.com/mmd-slotted-hood-07-09.html") != "americanmuscle"


class TestFetcherTier:
    def test_declares_browser_tier(self) -> None:
        assert AmericanMuscleAdapter.FETCHER_TIER == "browser"


class TestDiscoverStub:
    def test_yields_no_urls(self) -> None:
        # Bypass __init__ to avoid constructing a FlareSolverr fetcher in tests.
        adapter = AmericanMuscleAdapter.__new__(AmericanMuscleAdapter)
        assert list(adapter.discover_product_urls()) == []


class TestParseProductPage:
    def _adapter(self) -> AmericanMuscleAdapter:
        return AmericanMuscleAdapter.__new__(AmericanMuscleAdapter)

    def test_json_ld_parses(self) -> None:
        result = self._adapter().parse_product_page(_json_ld_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("MMD Slotted Hood")
        assert result.part_manufacturer == "MMD"
        assert result.part_number == "J110088"
        assert result.price_cents == 54999
        assert result.product_url == SAMPLE_URL
        assert result.image_urls is not None and len(result.image_urls) >= 1

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        html = """
        <html><head>
          <meta property="og:title" content="Borla S-Type Axle-Back Exhaust (11-12 GT)">
          <meta property="og:description" content="Borla S-Type axle-back for 2011-2012 Mustang GT.">
          <meta property="og:price:amount" content="699.99">
        </head><body>
          <h1>Borla S-Type Axle-Back Exhaust (11-12 GT)</h1>
          <p>SKU: 11825</p>
        </body></html>
        """
        result = self._adapter().parse_product_page(
            html, "https://www.americanmuscle.com/borla-s-type-axleback-exhaust-11-12gt.html"
        )
        assert result is not None
        assert "Borla S-Type" in result.name
        assert result.part_number == "11825"
        assert result.price_cents == 69999

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert self._adapter().parse_product_page(html, SAMPLE_URL) is None
