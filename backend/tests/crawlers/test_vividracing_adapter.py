"""Tests for vividracing.com adapter: URL pattern, JSON-LD parse, DOM fallback, slug manufacturer."""

from app.crawlers.adapters.tier1_tls.vividracing import (
    VividRacingAdapter,
    _is_product_url,
    _manufacturer_from_slug,
    _slug_from_url,
)

SAMPLE_URL = "https://www.vividracing.com/agency-power-oval-taper-air-filter-wrap-enclosed-top-tapers-bottom-tall-p-152475800.html"


def _product_html(
    *,
    name: str = "Agency Power Oval Taper Air Filter Wrap",
    brand: str = "Agency Power",
    sku: str = "AP-AIR-WRAP-001",
    price: str = "79.99",
    description: str = "Oval taper air filter wrap, enclosed top, tapers on bottom.",
    image: str = "https://cdn.vividracing.com/product/agency-power-air-filter-wrap-large.jpg",
) -> str:
    """Minimal page mirroring a plain schema.org Product JSON-LD block."""
    return f"""
    <html><head>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{description}">
      <meta property="og:image" content="{image}">
      <meta property="product:price:amount" content="{price}">
      <meta property="og:price:currency" content="USD">
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org",
        "@type": "Product",
        "brand": {{"@type": "Brand", "name": "{brand}"}},
        "sku": "{sku}",
        "mpn": "{sku}",
        "description": "{description}",
        "name": "{name}",
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


class TestProductUrlRegex:
    """The canonical product path is /<slug>-p-<digits>.html and must reject any URL with
    a query string (robots.txt bans /*?*). It also guards the sitemap walker and the
    parse entry point against being fed non-product URLs."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_numeric_id_required(self) -> None:
        # Slugged page that's not a product (no -p-<digits>.html suffix).
        assert not _is_product_url("https://www.vividracing.com/agency-power-catalog.html")

    def test_query_string_rejected(self) -> None:
        # robots.txt disallows /*?* — we must never feed query-stringed URLs back in.
        assert not _is_product_url(SAMPLE_URL + "?ref=google")

    def test_other_host_rejected(self) -> None:
        url = "https://www.example.com/agency-power-oval-taper-p-123.html"
        assert not _is_product_url(url)

    def test_slug_extraction(self) -> None:
        assert _slug_from_url(SAMPLE_URL).startswith("agency-power-oval-taper")


class TestManufacturerFromSlug:
    """Last-resort fallback: derive manufacturer from slug leading tokens."""

    def test_picks_leading_tokens(self) -> None:
        # agency-power-oval-... → leading "agency power" (stops at generic word)
        assert _manufacturer_from_slug("agency-power-oval-taper-air-filter") == "Agency Power"

    def test_stops_at_car_make(self) -> None:
        # BMW is a car make, not a manufacturer; should be rejected.
        assert _manufacturer_from_slug("bmw-m3-intake-kit") is None

    def test_stops_at_digits(self) -> None:
        # Once we hit a year/model number, stop — "agency-power" is the brand,
        # "2018" / "wrx" / etc. are vehicle details.
        assert _manufacturer_from_slug("agency-power-2018-wrx-intake") == "Agency Power"

    def test_empty_slug(self) -> None:
        assert _manufacturer_from_slug("") is None


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = VividRacingAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Agency Power")
        assert result.part_manufacturer == "Agency Power"
        assert result.part_number == "AP-AIR-WRAP-001"
        assert result.price_cents == 7999
        assert result.product_url == SAMPLE_URL
        assert result.image_urls and result.image_urls[0].endswith(".jpg")

    def test_non_product_url_returns_none(self) -> None:
        # Guard: the entry check rejects URLs that aren't product pages so the
        # archive rescrape pipeline can't feed Vivid category pages through this adapter.
        result = VividRacingAdapter().parse_product_page(
            _product_html(),
            "https://www.vividracing.com/category/air-filters.html",
        )
        assert result is None

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD at all — adapter should still pull title / description /
        # price from og: meta tags and manufacturer from the URL slug.
        html = """
        <html><head>
          <meta property="og:title" content="Agency Power Oval Taper Air Filter Wrap">
          <meta property="og:description" content="Air filter wrap for GR Corolla.">
          <meta property="og:image" content="https://cdn.vividracing.com/img/ap-airfilter.jpg">
          <meta property="product:price:amount" content="89.00">
        </head><body>
          <h1>Agency Power Oval Taper Air Filter Wrap</h1>
          <p>SKU: AP-AIR-002</p>
        </body></html>
        """
        result = VividRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Agency Power")
        # Multi-word brand match in part_manufacturer_from_title catches the
        # full "Agency Power" before the first-token scan would split it at
        # the space — keeps the real brand intact instead of writing a junk
        # "Agency" row.
        assert result.part_manufacturer == "Agency Power"
        assert result.part_number == "AP-AIR-002"
        assert result.price_cents == 8900

    def test_never_uses_vivid_internal_id_as_part_number(self) -> None:
        # "p-152475800" is Vivid's internal product id. Even when neither
        # JSON-LD nor DOM expose an SKU, we must not write that digit string
        # as part_number — it's useless for cross-retailer dedup.
        html = """
        <html><head>
          <meta property="og:title" content="Agency Power Oval Taper Air Filter Wrap">
          <meta property="og:image" content="https://cdn.vividracing.com/img/x.jpg">
        </head><body><h1>Agency Power Oval Taper Air Filter Wrap</h1></body></html>
        """
        result = VividRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number != "152475800"
        # Either None (no SKU found) or a real part code from the title, but
        # definitely not the internal URL id.
        if result.part_number is not None:
            assert "152475800" not in result.part_number

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert VividRacingAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """Vivid must declare the TLS fetcher tier so the runner hands it curl_cffi."""

    def test_declares_tls_tier(self) -> None:
        assert VividRacingAdapter.FETCHER_TIER == "tls"
