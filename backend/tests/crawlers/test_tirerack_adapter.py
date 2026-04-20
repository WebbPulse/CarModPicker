"""
Tests for tirerack.com adapter.

Tire Rack product pages are behind an aggressive anti-bot stack
(``site_problem_notes/tirerack.md``), so we have not captured a real
product page yet. These tests exercise the adapter against *synthetic*
HTML modeled on the JSON-LD ``Product`` schema we expect Tire Rack to
emit. Once a real capture lands under ``backend/tests/crawlers/fixtures/``,
replace the synthetic HTML with the fixture and tighten the assertions
against the actual DOM (tire size, load rating, wheel fitment data).
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier2_browser.tirerack import TireRackAdapter

SAMPLE_TIRE_URL = "https://www.tirerack.com/tires/Michelin/Pilot-Sport-4-S/"
SAMPLE_WHEEL_URL = "https://www.tirerack.com/wheels/WheelDetail.jsp?wheelMake=Enkei&wheelModel=RPF1&partnum=18RPF1"


def _json_ld_html(
    *,
    name: str = "Michelin Pilot Sport 4 S 245/35ZR19 (93Y) XL",
    brand: str = "Michelin",
    sku: str = "MIC-PS4S-2453519",
    price: str = "329.99",
    description: str = "Max Performance Summer tire, 245/35ZR19 (93Y) XL load rating, asymmetric tread.",
    image: str = "https://www.tirerack.com/images/tires/Michelin/PilotSport4S.jpg",
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
    def test_host_maps_to_tirerack(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_TIRE_URL) == "tirerack"

    def test_legacy_wheel_url_also_maps(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_WHEEL_URL) == "tirerack"

    def test_bare_host_also_maps(self) -> None:
        assert adapter_name_for_product_url("https://tirerack.com/tires/Some/Slug/") == "tirerack"

    def test_unrelated_host_does_not_map(self) -> None:
        assert adapter_name_for_product_url("https://example.com/tires/Michelin/PS4S") != "tirerack"


class TestFetcherTier:
    def test_declares_browser_tier(self) -> None:
        assert TireRackAdapter.FETCHER_TIER == "browser"


class TestDiscoverStub:
    def test_yields_no_urls(self) -> None:
        # Bypass __init__ to avoid constructing a FlareSolverr fetcher in tests.
        adapter = TireRackAdapter.__new__(TireRackAdapter)
        assert list(adapter.discover_product_urls()) == []


class TestParseProductPage:
    def _adapter(self) -> TireRackAdapter:
        return TireRackAdapter.__new__(TireRackAdapter)

    def test_json_ld_parses(self) -> None:
        result = self._adapter().parse_product_page(_json_ld_html(), SAMPLE_TIRE_URL)
        assert result is not None
        assert result.name.startswith("Michelin Pilot Sport")
        assert result.part_manufacturer == "Michelin"
        assert result.part_number == "MIC-PS4S-2453519"
        assert result.price_cents == 32999
        assert result.product_url == SAMPLE_TIRE_URL
        assert result.image_urls is not None and len(result.image_urls) >= 1

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        html = """
        <html><head>
          <meta property="og:title" content="Michelin Pilot Sport 4 S - 245/35ZR19">
          <meta property="og:description" content="Michelin Pilot Sport 4 S max performance summer tire.">
          <meta property="og:price:amount" content="329.99">
        </head><body>
          <h1>Michelin Pilot Sport 4 S - 245/35ZR19</h1>
          <p>Part Number: MIC-PS4S-2453519</p>
        </body></html>
        """
        result = self._adapter().parse_product_page(html, SAMPLE_TIRE_URL)
        assert result is not None
        assert "Michelin Pilot Sport" in result.name
        assert result.part_number == "MIC-PS4S-2453519"
        assert result.price_cents == 32999

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert self._adapter().parse_product_page(html, SAMPLE_TIRE_URL) is None
