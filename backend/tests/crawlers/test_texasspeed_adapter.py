"""
Tests for texas-speed.com adapter: URL shape guard, registration, fetcher tier,
JSON-LD parse (mpn-over-sku preference), Hyva gallery extraction, and the
Texas Speed & Performance manufacturer default.

Texas Speed is Magento 2 on the Hyva frontend theme behind Cloudflare (see
``site_problem_notes/texasspeed.md``). These tests run against *synthetic*
HTML modeled on the JSON-LD Product block and Hyva gallery JSON that live
product pages emit.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier1_tls.texasspeed import (
    TexasSpeedAdapter,
    _extract_gallery_full_urls,
    _is_product_url,
)

SAMPLE_URL = "https://www.texas-speed.com/brand/texas-speed-performance/" "p-tsp-chopacabra-tsp-chopacabra-truck-cam/"


def _gallery_json(*urls: str) -> str:
    """Build a Hyva-shape ``"images": [...]`` fragment with one entry per URL."""
    items = ",".join(
        (
            '{"thumb":"' + u + '?thumb=1","img":"' + u + '?img=1","full":"' + u + '","'
            'caption":"","position":"'
            + str(i + 1)
            + '","isMain":'
            + ("true" if i == 0 else "false")
            + ',"type":"image","videoUrl":null}'
        )
        for i, u in enumerate(urls)
    )
    return '"images": [' + items + "]"


def _product_html(
    *,
    name: str = "TSP Chopacabra Truck Cam",
    brand: str = "Texas Speed & Performance",
    sku: str = "TSP-CHOPacabra",
    mpn: str = "CHOPacabra",
    price: str = "419.99",
    description: str = "TSP CHOPacabra Truck Cam Specs: 214/222 .550/.550 108 LSA 106 ICL.",
    json_ld_image: str = "https://www.texas-speed.com/media/catalog/product/1/6/16987_1.jpg",
    gallery_full_urls: tuple[str, ...] = ("https://www.texas-speed.com/media/catalog/product/1/6/16987_1.jpg?full=1",),
) -> str:
    """Minimal HTML that mirrors Texas Speed's JSON-LD Product + Hyva gallery shape."""
    gallery_block = _gallery_json(*gallery_full_urls) if gallery_full_urls else ""
    mpn_field = f'"mpn":"{mpn}",' if mpn else ""
    brand_field = f'"brand": {{"@type": "Brand", "name": "{brand}"}},' if brand else ""
    return f"""
    <html><head>
      <title>{name}</title>
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "{name}",
        "sku": "{sku}",
        {mpn_field}
        "image": "{json_ld_image}",
        "category": "Naturally Aspirated",
        {brand_field}
        "description": "{description}",
        "offers": {{
          "@type": "Offer",
          "url": "{SAMPLE_URL}",
          "price": "{price}",
          "priceCurrency": "USD",
          "availability": "https://schema.org/InStock"
        }}
      }}
      </script>
    </head><body>
      <div x-data='{{ {gallery_block} }}'>
        <h1>{name}</h1>
      </div>
    </body></html>
    """


class TestAdapterRegistration:
    """Every texas-speed.com page routes through this adapter via the host map."""

    def test_host_maps_to_texasspeed(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "texasspeed"

    def test_bare_host_also_maps(self) -> None:
        assert (
            adapter_name_for_product_url("https://texas-speed.com/brand/gm/p-gm-12586768-gm-58x-reluctor-wheel/")
            == "texasspeed"
        )

    def test_unrelated_host_does_not_map(self) -> None:
        assert adapter_name_for_product_url("https://www.example.com/brand/foo/p-bar-baz/") != "texasspeed"


class TestProductUrlRegex:
    """
    Product URL gate. ``/brand/<slug>/p-<slug>/`` is a positive identifier on
    this site — category / CMS pages use different shapes (``/cat/...``,
    ``/shop-by-engine/...``, ``/company/...``).
    """

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_trailing_slash_optional(self) -> None:
        assert _is_product_url("https://www.texas-speed.com/brand/gm/p-gm-12586768-gm-58x-reluctor-wheel")

    def test_query_string_rejected(self) -> None:
        # robots.txt disallows /*? — any URL with a query string is off limits.
        assert not _is_product_url(SAMPLE_URL + "?utm_source=x")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/brand/foo/p-bar/")

    def test_category_path_rejected(self) -> None:
        # Shop-by-engine / category pages must not pass the shape guard.
        assert not _is_product_url("https://www.texas-speed.com/shop-by-engine/ls7/")
        assert not _is_product_url("https://www.texas-speed.com/cat/assembled-engines/")
        assert not _is_product_url("https://www.texas-speed.com/brands/texas-speed-performance/")
        assert not _is_product_url("https://www.texas-speed.com/company/contact-us/")

    def test_missing_p_segment_rejected(self) -> None:
        # /brand/<slug>/ without the /p-<slug>/ tail is a brand landing page.
        assert not _is_product_url("https://www.texas-speed.com/brand/texas-speed-performance/")

    def test_stale_mcprod_sitemap_url_rejected(self) -> None:
        # The stale /sitemap.xml on this origin points at mcprod.*.html URLs
        # that 302 to no-route 404s. The host guard allows the subdomain (it
        # is a *.texas-speed.com host), but the path shape rejects them since
        # they are /<slug>.html with no /brand/.../p-.../ prefix.
        assert not _is_product_url("https://mcprod.texas-speed.com/prc-stage-2-5-ls6-cnc-ported-heads-outright.html")


class TestGalleryExtraction:
    """
    Hyva theme serializes the image gallery as a plain JSON array under an
    Alpine ``x-data``. We locate it by marker and walk bracket depth,
    ignoring contents inside quoted strings.
    """

    def test_multi_image_gallery_extracted_in_position_order(self) -> None:
        urls = (
            "https://www.texas-speed.com/media/catalog/product/1/0/10679.png?full=1",
            "https://www.texas-speed.com/media/catalog/product/1/0/10679_2.png?full=1",
            "https://www.texas-speed.com/media/catalog/product/1/0/10679_3.png?full=1",
        )
        html = "<html><body><div x-data='{" + _gallery_json(*urls) + "}'></div></body></html>"
        assert _extract_gallery_full_urls(html) == list(urls)

    def test_empty_when_gallery_marker_absent(self) -> None:
        # Single-image soft-404 pages omit the Alpine gallery block; caller
        # should fall back to JSON-LD image.
        assert _extract_gallery_full_urls("<html><body>no gallery here</body></html>") == []


class TestParseProductPage:
    """End-to-end parsing: synthetic JSON-LD + gallery HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = TexasSpeedAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "TSP Chopacabra Truck Cam"
        assert result.part_manufacturer == "Texas Speed & Performance"
        # mpn wins over sku so cross-retailer dedupe on manufacturer + PN still
        # matches rows sourced from Summit / Jegs / Amazon for the same cam.
        assert result.part_number == "CHOPacabra"
        assert result.price_cents == 41999
        assert result.description and "CHOPacabra" in result.description
        assert result.product_url == SAMPLE_URL

    def test_prefers_mpn_over_retailer_prefixed_sku(self) -> None:
        # Texas Speed's sku is always brand-prefixed ("PRW-2634600"); the real
        # MPN lives in the mpn field. The adapter must pick mpn so the Part
        # row matches Summit's row that uses MPN as SKU directly.
        html = _product_html(
            name="PRW Water Pump Pulleys 2634600",
            brand="PRW",
            sku="PRW-2634600",
            mpn="2634600",
            price="127.09",
        )
        result = TexasSpeedAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "PRW"
        assert result.part_number == "2634600"

    def test_falls_back_to_sku_when_mpn_missing(self) -> None:
        # Composite kits (e.g. Procharger tuner kits) sometimes ship no mpn.
        # We fall back to the retailer sku so the listing still carries an
        # identifier, even if cross-retailer dedupe on it is weaker.
        html = _product_html(
            name="Procharger 2011-18 RAM 1500 Hemi 5.7 Stage II Tuner Kit",
            brand="Procharger",
            sku="PRO-1DH305-SCI",
            mpn="",
            price="8049.00",
        )
        result = TexasSpeedAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Procharger"
        assert result.part_number == "PRO-1DH305-SCI"
        assert result.price_cents == 804900

    def test_default_manufacturer_when_brand_missing(self) -> None:
        # Rare path: brand.name absent on the JSON-LD Product block. Default
        # to the house brand rather than running the title-first-word
        # heuristic (which would write product words as a manufacturer).
        html = _product_html(brand="").replace('"brand": {"@type": "Brand", "name": ""},', "")
        result = TexasSpeedAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Texas Speed & Performance"

    def test_gallery_wins_over_json_ld_image(self) -> None:
        # When the Hyva gallery JSON is present, prefer its ordered `full`
        # URLs over the single JSON-LD `image` — JSON-LD only carries the
        # main photo, the gallery has every angle.
        gallery = (
            "https://www.texas-speed.com/media/catalog/product/1/0/10679.png?full=1",
            "https://www.texas-speed.com/media/catalog/product/1/0/10679_2.png?full=1",
        )
        html = _product_html(
            json_ld_image="https://www.texas-speed.com/media/catalog/product/old/only-the-main.jpg",
            gallery_full_urls=gallery,
        )
        result = TexasSpeedAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls == list(gallery)

    def test_falls_back_to_json_ld_image_without_gallery(self) -> None:
        html = _product_html(gallery_full_urls=())
        result = TexasSpeedAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls == ["https://www.texas-speed.com/media/catalog/product/1/6/16987_1.jpg"]

    def test_non_product_url_returns_none(self) -> None:
        # Guard: archive rescrape must not feed category pages through this
        # adapter just because the host matches.
        result = TexasSpeedAdapter().parse_product_page(
            _product_html(),
            "https://www.texas-speed.com/shop-by-engine/ls7/",
        )
        assert result is None

    def test_missing_jsonld_returns_none(self) -> None:
        # No JSON-LD at all — typical Magento no-route landing page. Return
        # None so the ingest pipeline doesn't write a blank part.
        html = "<html><head><title>404 Not Found</title></head><body></body></html>"
        assert TexasSpeedAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """Texas Speed declares the TLS fetcher tier — Cloudflare challenges plain requests."""

    def test_declares_tls_tier(self) -> None:
        assert TexasSpeedAdapter.FETCHER_TIER == "tls"
