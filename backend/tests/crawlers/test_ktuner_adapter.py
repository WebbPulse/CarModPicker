"""
Tests for ktuner.com adapter: single-page WordPress catalog where every
product lives inline on ``/products/`` separated by ``<hr />`` rules. Covers
host routing, the ``?sku=<slug>`` virtual-URL scheme, section splitting,
inline-MPN extraction (FFC100) with slug fallback for units that don't
print an SKU, image https-upgrade, and the empty-slug/bare-URL bail-out
used by the chrome extension when no product was selected.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.ktuner import (
    KTUNER_PRODUCTS,
    PRODUCTS_URL,
    KTunerAdapter,
    _slug_from_url,
    _upgrade_to_https,
)


def _catalog_html(
    *,
    v2_price: str = "$649",
    v12_price: str = "$449",
    ecu_price: str = "$449",
    ffc_price: str = "$99",
    v2_image: str = "http://www.ktuner.com/images/KTunerFlashV2Kit500.jpg",
    ecu_image: str = "http://www.ktuner.com/images/KTunerEUV1.jpg",
    include_warranty: bool = True,
) -> str:
    """
    Shape-accurate rendering of KTuner's ``/products/`` page. Keeps the
    ``.post-content`` wrapper, the ``<hr />`` section delimiters, the
    header-paragraph style (``<p><strong>Name</strong><br/>Model – <strong>
    $Price</strong><br/><img/></p>``), and the trailing "list of supported
    vehicles" line that appears on every product. The KTunerECU variant
    deliberately puts the image in its own ``<p>`` so we exercise both
    image placements.
    """
    warranty = (
        "<hr /><p>Warranty Information:</p><p>Cables and hardware warranty language…</p>" if include_warranty else ""
    )
    return f"""
    <html><body><div class="post-content">
      <p>Here is some information about our KTuner end user systems:</p>
      <p><strong>KTunerFlash V2 Touch \u2013 Flash Based Hardware</strong><br />
        J2534 OBD Interface \u2013<strong> {v2_price}</strong>: Now available!<br />
        <img src="{v2_image}" alt="" /></p>
      <p>Our KTunerFlash V2 tuning package comes with a single unit and license.</p>
      <ul><li>5" Touch Screen Display.</li><li>Real-Time data display.</li></ul>
      <p>Please see our <a href="/applications">list of supported vehicles</a>.</p>
      <hr />
      <p><strong>KTunerFlash V1.2 \u2013 Flash Based Hardware</strong><br />
        J2534 OBD Interface \u2013<strong> {v12_price}</strong>:</p>
      <p><img src="http://www.ktuner.com/images/KTunerFlashKitV1p2-500.jpg" alt="" /></p>
      <p>Our KTunerFlash V1.2 tuning package.</p>
      <ul><li>Store multiple tunes.</li></ul>
      <p>Please see our <a href="/applications">list of supported vehicles</a>.</p>
      <hr />
      <p><strong>KTunerECU \u2013 In-ECU Hardware</strong>:<br />
        Revision 1 With On Board Logging \u2013<strong> {ecu_price}</strong>: Now available!</p>
      <p><img src="{ecu_image}" alt="" /></p>
      <p>Our KTuner In-ECU tuning package.</p>
      <ul><li>Direct Flex Fuel input.</li></ul>
      <p>Please see our <a href="/applications">list of supported vehicles</a>.</p>
      <hr />
      <p><strong>KTuner Flex Fuel Converter</strong><br />
        FFC100 \u2013<strong> {ffc_price}</strong>: Now available!<br />
        <img src="http://www.ktuner.com/images/FlexFuelConverter.jpg" alt="" /></p>
      <p>Converts an ethanol sensor signal into voltage for direct flex fuel support.</p>
      {warranty}
    </div></body></html>
    """


SAMPLE_URLS = {slug: f"{PRODUCTS_URL}?sku={slug}" for slug, _, _ in KTUNER_PRODUCTS}


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_bare_host_routes_to_ktuner(self) -> None:
        assert adapter_name_for_product_url("https://ktuner.com/products/") == "ktuner"

    def test_www_host_routes_to_ktuner(self) -> None:
        assert adapter_name_for_product_url("https://www.ktuner.com/products/?sku=ktunerecu-rev1") == "ktuner"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/ktuner") == "generic"


class TestSlugFromUrl:
    """``?sku=<slug>`` is what ties a fetch to a specific section; invalid or
    missing slugs must bail cleanly instead of silently parsing a wrong row."""

    def test_known_slug_returned(self) -> None:
        assert _slug_from_url(f"{PRODUCTS_URL}?sku=ktunerflash-v2-touch") == "ktunerflash-v2-touch"

    def test_unknown_slug_rejected(self) -> None:
        assert _slug_from_url(f"{PRODUCTS_URL}?sku=not-a-real-product") is None

    def test_missing_query_rejected(self) -> None:
        # Bare /products/ URL posted from the chrome extension — we can't know
        # which of four stacked products the user was looking at, so we bail.
        assert _slug_from_url(PRODUCTS_URL) is None

    def test_case_insensitive_slug(self) -> None:
        assert _slug_from_url(f"{PRODUCTS_URL}?sku=KTunerECU-Rev1") == "ktunerecu-rev1"


class TestUpgradeToHttps:
    """KTuner writes ``<img src="http://www.ktuner.com/...">`` in page source;
    storing these as-is would mixed-content-block on the HTTPS frontend."""

    def test_http_upgraded(self) -> None:
        assert (
            _upgrade_to_https("http://www.ktuner.com/images/KTunerFlashV2Kit500.jpg")
            == "https://www.ktuner.com/images/KTunerFlashV2Kit500.jpg"
        )

    def test_https_unchanged(self) -> None:
        assert (
            _upgrade_to_https("https://www.ktuner.com/images/FlexFuelConverter.jpg")
            == "https://www.ktuner.com/images/FlexFuelConverter.jpg"
        )


class TestDiscovery:
    """One discovery URL per product, each carrying a stable ``?sku=<slug>``
    so the runner treats them as distinct canonical URLs."""

    def test_discovers_one_url_per_product(self) -> None:
        adapter = KTunerAdapter()
        urls = list(adapter.discover_product_urls())
        assert len(urls) == len(KTUNER_PRODUCTS)
        for url, (slug, _, _) in zip(urls, KTUNER_PRODUCTS):
            assert url == f"{PRODUCTS_URL}?sku={slug}"


class TestParseProductPage:
    """End-to-end parsing against the shaped WordPress catalog."""

    def test_v2_touch_parses(self) -> None:
        result = KTunerAdapter().parse_product_page(_catalog_html(), SAMPLE_URLS["ktunerflash-v2-touch"])
        assert result is not None
        # The em-dash in the page header becomes a plain ASCII dash on store.
        assert result.name == "KTunerFlash V2 Touch - Flash Based Hardware"
        assert result.part_manufacturer == "KTuner"
        assert result.part_number == "KTUNERFLASH-V2-TOUCH"
        assert result.price_cents == 64900
        assert result.description is not None
        assert '5" Touch Screen Display' in result.description
        # Boilerplate "list of supported vehicles" footer is stripped from
        # description so it doesn't appear identically on every KTuner row.
        assert "list of supported vehicles" not in result.description.lower()
        # The page's intro paragraph ("Here is some information…") sits in
        # the same pre-first-``<hr/>`` section as the V2 Touch header, so the
        # description extractor must only consider tags after the header —
        # not every tag in the section.
        assert "here is some information" not in result.description.lower()
        assert result.image_urls == ["https://www.ktuner.com/images/KTunerFlashV2Kit500.jpg"]

    def test_v1_2_parses_and_not_confused_with_v2(self) -> None:
        # Keyword match uses ``"v1.2"`` specifically so the two flash units
        # don't collapse onto each other when both headers contain
        # ``"KTunerFlash"``.
        result = KTunerAdapter().parse_product_page(_catalog_html(), SAMPLE_URLS["ktunerflash-v1-2"])
        assert result is not None
        assert "V1.2" in result.name
        assert result.part_number == "KTUNERFLASH-V1.2"
        assert result.price_cents == 44900

    def test_ecu_parses_with_image_from_separate_paragraph(self) -> None:
        # KTunerECU renders its image in a standalone ``<p>`` following the
        # header — exercises the fact that ``_extract_image_url`` scans every
        # tag in the section, not just the header paragraph.
        result = KTunerAdapter().parse_product_page(_catalog_html(), SAMPLE_URLS["ktunerecu-rev1"])
        assert result is not None
        assert result.name.startswith("KTunerECU")
        assert result.part_number == "KTUNERECU-REV1"
        assert result.price_cents == 44900
        assert result.image_urls == ["https://www.ktuner.com/images/KTunerEUV1.jpg"]

    def test_flex_fuel_uses_inline_mpn_not_fallback(self) -> None:
        # Flex Fuel Converter is the only product on the page with a real
        # printed MPN ("FFC100"). Verify we prefer it over the slug fallback.
        result = KTunerAdapter().parse_product_page(_catalog_html(), SAMPLE_URLS["ktuner-flex-fuel-converter"])
        assert result is not None
        assert result.part_number == "FFC100"
        assert result.price_cents == 9900

    def test_bare_products_url_returns_none(self) -> None:
        # Chrome extension lands on ``/products/`` without a ``?sku=`` param —
        # no way to know which section the user meant, so skip rather than
        # ingesting the first product by accident.
        assert KTunerAdapter().parse_product_page(_catalog_html(), PRODUCTS_URL) is None

    def test_unknown_slug_returns_none(self) -> None:
        assert KTunerAdapter().parse_product_page(_catalog_html(), f"{PRODUCTS_URL}?sku=phantom-product") is None

    def test_missing_post_content_returns_none(self) -> None:
        # A homepage or 404 rendered through the same theme lacks the
        # ``.post-content`` wrapper. Bail instead of parsing header nav text.
        html = "<html><body><header><h1>Home</h1></header></body></html>"
        assert KTunerAdapter().parse_product_page(html, SAMPLE_URLS["ktunerflash-v2-touch"]) is None

    def test_section_drift_returns_none(self) -> None:
        # If KTuner removes the FFC from the page entirely, the requested slug
        # no longer matches any section. We return None rather than sticking
        # the slug onto the wrong section.
        html = _catalog_html().replace("KTuner Flex Fuel Converter", "Discontinued Product")
        assert KTunerAdapter().parse_product_page(html, SAMPLE_URLS["ktuner-flex-fuel-converter"]) is None
