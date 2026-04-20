"""
Tests for ecstuning.com adapter.

ECS Tuning product pages are expected behind Cloudflare Bot Management
(``site_problem_notes/ecstuning.md``), so we have not captured a real product
page yet. These tests exercise the adapter against *synthetic* HTML modeled on
a generic schema.org ``Product`` block, plus the URL-derived brand/part-number
fallback — ECS's ``/b-<brand>-parts/<slug>/<sku>/`` URL shape carries both
fields and is the last-resort path when HTML parsing fails.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier2_browser.ecstuning import (
    ECSTuningAdapter,
    _brand_and_sku_from_url,
)

SAMPLE_URL = "https://www.ecstuning.com/b-genuine-bmw-parts/thermostat-housing-assembly/11538635689/"


def _json_ld_html(
    *,
    name: str = "Genuine BMW Thermostat Housing Assembly - E82 E90 E92 N54",
    brand: str = "Genuine BMW",
    sku: str = "11538635689",
    price: str = "189.99",
    description: str = "Genuine BMW thermostat housing for N54-equipped E82/E90/E92.",
    image: str = "https://www.ecstuning.com/images/products/11538635689.jpg",
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
    def test_host_maps_to_ecstuning(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "ecstuning"

    def test_bare_host_also_maps(self) -> None:
        assert adapter_name_for_product_url("https://ecstuning.com/b-genuine-bmw-parts/foo/1234/") == "ecstuning"

    def test_catalog_id_host_also_maps(self) -> None:
        assert adapter_name_for_product_url("https://www.ecstuning.com/es1234567/") == "ecstuning"

    def test_unrelated_host_does_not_map(self) -> None:
        assert adapter_name_for_product_url("https://example.com/b-genuine-bmw-parts/x/1/") != "ecstuning"


class TestFetcherTier:
    def test_declares_browser_tier(self) -> None:
        assert ECSTuningAdapter.FETCHER_TIER == "browser"


class TestDiscoverStub:
    def test_yields_no_urls(self) -> None:
        # Bypass __init__ to avoid constructing a FlareSolverr fetcher in tests.
        adapter = ECSTuningAdapter.__new__(ECSTuningAdapter)
        assert list(adapter.discover_product_urls()) == []


class TestBrandAndSkuFromUrl:
    def test_genuine_bmw_strips_prefix(self) -> None:
        brand, sku = _brand_and_sku_from_url(SAMPLE_URL)
        # "genuine-bmw" → "BMW" (drop the retailer-qualifier token, upper-case short make).
        assert brand == "BMW"
        assert sku == "11538635689"

    def test_oem_audi_strips_prefix(self) -> None:
        brand, sku = _brand_and_sku_from_url("https://www.ecstuning.com/b-oem-audi-parts/timing-belt-kit/06h109119l/")
        assert brand == "Audi"
        assert sku == "06h109119l".upper() or sku == "06H109119L" or sku == "06h109119l"

    def test_multi_word_brand_title_cased(self) -> None:
        brand, sku = _brand_and_sku_from_url("https://www.ecstuning.com/b-schwaben-parts/filter-wrench/014778sch01a/")
        # "schwaben" → "Schwaben" (not a prefix token, kept, title-cased).
        assert brand == "Schwaben"
        assert sku is not None

    def test_catalog_id_yields_none(self) -> None:
        # /es<digits>/ format: nothing derivable from path.
        assert _brand_and_sku_from_url("https://www.ecstuning.com/es1234567/") == (None, None)

    def test_unrelated_path_yields_none(self) -> None:
        assert _brand_and_sku_from_url("https://www.ecstuning.com/contact/") == (None, None)


class TestParseProductPage:
    def _adapter(self) -> ECSTuningAdapter:
        return ECSTuningAdapter.__new__(ECSTuningAdapter)

    def test_json_ld_parses(self) -> None:
        result = self._adapter().parse_product_page(_json_ld_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Genuine BMW Thermostat")
        # JSON-LD brand wins over URL-derived brand.
        assert result.part_manufacturer == "Genuine BMW"
        assert result.part_number == "11538635689"
        assert result.price_cents == 18999
        assert result.product_url == SAMPLE_URL
        assert result.image_urls is not None and len(result.image_urls) >= 1

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        html = """
        <html><head>
          <meta property="og:title" content="Thermostat Housing - BMW N54">
          <meta property="og:description" content="Thermostat housing for BMW N54.">
          <meta property="og:price:amount" content="189.99">
        </head><body>
          <h1>Thermostat Housing - BMW N54</h1>
          <p>SKU: 11538635689</p>
        </body></html>
        """
        result = self._adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert "Thermostat Housing" in result.name
        assert result.part_number == "11538635689"
        assert result.price_cents == 18999

    def test_url_fallback_when_html_minimal(self) -> None:
        # Minimal HTML missing JSON-LD and SKU — the URL-derived fallback must
        # fill in brand + part_number so cross-retailer dedupe still works.
        html = """
        <html><head>
          <meta property="og:title" content="Thermostat Housing Assembly">
        </head><body><h1>Thermostat Housing Assembly</h1></body></html>
        """
        result = self._adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "11538635689"
        # "genuine-bmw" → "BMW" via URL-derived brand fallback.
        assert result.part_manufacturer == "BMW"

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert self._adapter().parse_product_page(html, SAMPLE_URL) is None
