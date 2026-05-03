"""
Tests for briantooleyracing.com adapter: URL shape guard, host routing,
flat-sitemap discovery (priority=1.0 filter), Magento gallery extraction,
title MPN-suffix stripping, and end-to-end JSON-LD Product parsing.

BTR is Magento; robots.txt lists the standard ``/catalog/product/view/`` and
``/catalogsearch/`` paths, and each product page emits a JSON-LD ``Product``
block plus a ``mage/gallery/gallery`` ``"data":[...]`` array for the image
gallery. These tests run against synthetic HTML modeled on real page
fixtures.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http import briantooleyracing as btr_mod
from app.crawlers.adapters.tier0_http.briantooleyracing import (
    BrianTooleyRacingAdapter,
    _discover_via_sitemap,
    _extract_gallery_full_urls,
    _is_product_url,
    _strip_trailing_mpn,
)

SAMPLE_URL = "https://briantooleyracing.com/btr-560-beehive-valve-spring-set-sp011-16.html"


def _gallery_json(*urls: str) -> str:
    """
    Build a Magento-shape ``"mage/gallery/gallery": {"data": [...]}`` fragment
    with one entry per URL. Mirrors the ``thumb``/``img``/``full``/``position``/
    ``isMain``/``type`` keys that BTR product pages actually emit.
    """
    items = ",".join(
        (
            '{"thumb":"' + u + '?thumb=1",'
            '"img":"' + u + '?img=1",'
            '"full":"' + u + '",'
            '"caption":"",'
            '"position":"' + str(i + 1) + '",'
            '"isMain":' + ("true" if i == 0 else "false") + ","
            '"type":"image","videoUrl":null}'
        )
        for i, u in enumerate(urls)
    )
    return '"mage/gallery/gallery": {"data": [' + items + "]}"


def _product_html(
    *,
    name: str = "BTR LS6 BEEHIVE SPRING - .560 LIFT - 16 PC KIT - SP011-16",
    brand: str = "Brian Tooley Racing",
    sku: str = "SP011-16",
    mpn: str = "SP011-16",
    price: str = "119.99",
    json_ld_description: str = "",
    dom_description: str = (
        "BTR's .560 lift LS6-style valve springs give you all of the performance "
        "of an LS7 spring at a fraction of the cost."
    ),
    json_ld_image: str = "https://briantooleyracing.com/media/catalog/product/m/2/m2_sp011-16_22.jpg",
    gallery_full_urls: tuple[str, ...] = (
        "https://briantooleyracing.com/media/catalog/product/m/2/m2_sp011-16_22.jpg?full=1",
        "https://briantooleyracing.com/media/catalog/product/v/a/valve-spring-installed-height-tech_01_1_51.jpg?full=1",
    ),
) -> str:
    """Minimal HTML that mirrors BTR's Magento JSON-LD Product + gallery shape."""
    gallery_block = _gallery_json(*gallery_full_urls) if gallery_full_urls else ""
    mpn_field = f'"mpn":"{mpn}",' if mpn else ""
    sku_field = f'"sku":"{sku}",' if sku else ""
    brand_field = f'"brand": {{"@type": "Brand", "name": "{brand}"}},' if brand else ""
    description_dom = (
        f'<div class="product attribute description"><div class="value">{dom_description}</div></div>'
        if dom_description
        else ""
    )
    return f"""
    <html><head>
      <title>{name}</title>
      <meta property="og:type" content="product" />
      <meta property="og:url" content="{SAMPLE_URL}" />
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "{name}",
        {sku_field}
        {mpn_field}
        "image": "{json_ld_image}",
        "description": "{json_ld_description}",
        {brand_field}
        "url": "{SAMPLE_URL}",
        "offers": [{{
          "@type": "Offer",
          "priceCurrency": "USD",
          "price": {price},
          "availability": "https://schema.org/InStock",
          "url": "{SAMPLE_URL}"
        }}]
      }}
      </script>
      <script type="text/x-magento-init">
        {{"[data-gallery-role=gallery-placeholder]": {{ {gallery_block} }} }}
      </script>
    </head><body>
      <span class="page-title-wrapper">{name}</span>
      {description_dom}
    </body></html>
    """


class TestAdapterRegistration:
    """Host routing sends briantooleyracing.com pages through this adapter."""

    def test_bare_host_routes_to_briantooleyracing(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "briantooleyracing"

    def test_www_subdomain_routes_to_briantooleyracing(self) -> None:
        # The canonical host redirects www → apex, but the chrome extension may
        # capture a www URL before the redirect — route on either form.
        assert (
            adapter_name_for_product_url("https://www.briantooleyracing.com/03-08-5-7-hemi-cam-bolt.html")
            == "briantooleyracing"
        )

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/briantooleyracing") == "generic"


class TestAdapterFetcherTier:
    """BTR responds to plain ``requests`` — no Cloudflare interstitial."""

    def test_http_tier_default(self) -> None:
        assert BrianTooleyRacingAdapter.FETCHER_TIER == "http"


class TestProductUrlShape:
    """
    Product URLs are root-slug ``/<slug>.html``. Categories live at depth-1
    too (``/tools.html``) but discovery filters them out via the
    ``<priority>`` tag in the sitemap — for URLs arriving from the extension
    or a rescrape, we only reject nested paths and non-html URLs here.
    """

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_root_path_rejected(self) -> None:
        assert not _is_product_url("https://briantooleyracing.com/")

    def test_non_html_rejected(self) -> None:
        # Magento legacy ``/catalog/product/view/id/N`` URLs are disallowed by
        # robots.txt and have no ``.html`` suffix — reject them here so the
        # archive rescrape never feeds them into this adapter.
        assert not _is_product_url("https://briantooleyracing.com/catalog/product/view/id/71864")

    def test_nested_category_path_rejected(self) -> None:
        # The sitemap has ~400 categories at depth 2-3; none of these are
        # product pages even though they share the ``.html`` extension.
        assert not _is_product_url("https://briantooleyracing.com/camshafts-lifters-pushrods/camshafts.html")
        assert not _is_product_url(
            "https://briantooleyracing.com/camshafts-lifters-pushrods/camshafts/ls3-naturally-aspirated-cams.html"
        )

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/btr-spring.html")


class TestStripTrailingMpn:
    """Titles ship with ``" - <MPN>"`` tails on most BTR listings; strip when the token matches the JSON-LD MPN."""

    def test_strips_matching_mpn_with_dash(self) -> None:
        assert (
            _strip_trailing_mpn("BTR LS6 BEEHIVE SPRING - .560 LIFT - 16 PC KIT - SP011-16", "SP011-16")
            == "BTR LS6 BEEHIVE SPRING - .560 LIFT - 16 PC KIT"
        )

    def test_strips_when_mpn_preceded_by_brand_token(self) -> None:
        # ``03-08 5.7 HEMI CAM BOLT - MOPAR 06504429`` — the trailing ``06504429``
        # matches the JSON-LD MPN; the ``MOPAR`` word before it is part of the
        # display name and should stay.
        assert (
            _strip_trailing_mpn("03-08 5.7 HEMI CAM BOLT - MOPAR 06504429", "06504429")
            == "03-08 5.7 HEMI CAM BOLT - MOPAR"
        )

    def test_case_insensitive_match(self) -> None:
        assert _strip_trailing_mpn("Widget - abc-123", "ABC-123") == "Widget"

    def test_non_matching_tail_left_intact(self) -> None:
        # Trailing token isn't the real MPN — keep the title unchanged rather
        # than guess at which of several dashes separates the SKU suffix.
        assert _strip_trailing_mpn("Gen V LT - Camshaft", "1GU204-SCI") == "Gen V LT - Camshaft"

    def test_no_mpn_returns_title_unchanged(self) -> None:
        assert _strip_trailing_mpn("Widget - ABC-123", None) == "Widget - ABC-123"
        assert _strip_trailing_mpn("Widget - ABC-123", "") == "Widget - ABC-123"


class TestGalleryExtraction:
    """Magento ``mage/gallery/gallery`` ``"data":[...]`` is the authoritative image list on BTR."""

    def test_multi_image_gallery_extracted_in_position_order(self) -> None:
        urls = (
            "https://briantooleyracing.com/media/catalog/product/m/2/main.jpg",
            "https://briantooleyracing.com/media/catalog/product/m/2/second.jpg",
            "https://briantooleyracing.com/media/catalog/product/m/2/third.jpg",
        )
        html = "<html><body><script>" + _gallery_json(*urls) + "</script></body></html>"
        assert _extract_gallery_full_urls(html) == list(urls)

    def test_dedup_by_path_ignores_querystring_variants(self) -> None:
        # Same photo at two resize param sets collapses to one entry.
        u1 = "https://briantooleyracing.com/media/catalog/product/m/2/main.jpg?quality=80&width=683"
        u2 = "https://briantooleyracing.com/media/catalog/product/m/2/main.jpg?quality=50&width=200"
        html = "<html><body><script>" + _gallery_json(u1, u2) + "</script></body></html>"
        result = _extract_gallery_full_urls(html)
        assert len(result) == 1
        assert result[0] == u1

    def test_empty_when_gallery_marker_absent(self) -> None:
        assert _extract_gallery_full_urls("<html><body>no gallery here</body></html>") == []

    def test_malformed_json_returns_empty(self) -> None:
        # Marker present but the ``data`` array never closes — bracket walk
        # hits the cap and we return [] rather than raising.
        html = '<script>"mage/gallery/gallery": {"data": [ {"full":"a"'
        assert _extract_gallery_full_urls(html) == []


class TestParseProductPage:
    """End-to-end parsing: synthetic JSON-LD + gallery + description DOM → ScrapedPayload."""

    def test_full_page_parses_with_gallery_and_dom_description(self) -> None:
        result = BrianTooleyRacingAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        # MPN-suffix stripped from title.
        assert result.name == "BTR LS6 BEEHIVE SPRING - .560 LIFT - 16 PC KIT"
        assert result.part_manufacturer == "Brian Tooley Racing"
        assert result.part_number == "SP011-16"
        assert result.price_cents == 11999
        # JSON-LD description is empty; DOM block fills it in.
        assert result.description is not None
        assert "LS6-style valve springs" in result.description
        # Gallery wins over JSON-LD single ``image``.
        assert result.image_urls is not None
        assert len(result.image_urls) == 2
        assert result.image_urls[0].endswith("m2_sp011-16_22.jpg?full=1")
        assert result.product_url == SAMPLE_URL

    def test_third_party_brand_preserved(self) -> None:
        # BTR resells Procharger / Mopar / ARP / etc.; JSON-LD ``brand.name``
        # on those SKUs is the third-party brand and must flow through
        # untouched so cross-retailer dedupe lines up with Summit / Jegs.
        html = _product_html(
            name="PROCHARGER SUPERCHARGER KIT - C7 CORVETTE Z06 - TUNER KIT - LT4 - 1GU204-SCI",
            brand="Procharger",
            sku="1GU204-SCI",
            mpn="1GU204-SCI",
            price="9599",
        )
        result = BrianTooleyRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Procharger"
        assert result.part_number == "1GU204-SCI"
        assert result.name == "PROCHARGER SUPERCHARGER KIT - C7 CORVETTE Z06 - TUNER KIT - LT4"
        assert result.price_cents == 959900

    def test_falls_back_to_json_ld_image_without_gallery(self) -> None:
        # Gallery JSON absent — fall back to the single JSON-LD ``image``.
        html = _product_html(gallery_full_urls=())
        result = BrianTooleyRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls == ["https://briantooleyracing.com/media/catalog/product/m/2/m2_sp011-16_22.jpg"]

    def test_prefers_mpn_over_sku_when_they_differ(self) -> None:
        # Rare on BTR (sku and mpn are usually identical) but defensively
        # coded so cross-retailer dedupe still matches Summit / Jegs when a
        # product ever ships a retailer-prefixed sku.
        html = _product_html(sku="BTR-88670", mpn="88670")
        result = BrianTooleyRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "88670"

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape must not feed category pages through this adapter
        # just because the host matches — shape guard kicks in first.
        result = BrianTooleyRacingAdapter().parse_product_page(
            _product_html(),
            "https://briantooleyracing.com/camshafts-lifters-pushrods/camshafts.html",
        )
        assert result is None

    def test_missing_json_ld_returns_none(self) -> None:
        # No JSON-LD Product — typical Magento no-route landing page. Return
        # None so the ingest pipeline doesn't write a blank part.
        html = "<html><head><title>404 Not Found</title></head><body></body></html>"
        assert BrianTooleyRacingAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestDiscoverViaSitemap:
    """
    Sitemap discovery filters a flat urlset by ``<priority>1.0</priority>``
    to isolate products from categories (0.5) and CMS pages (0.2), then
    rejects the site root and any legacy ``/catalog/product/view/id/N``
    entries via the ``_is_product_url`` shape guard.
    """

    SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://briantooleyracing.com/</loc><priority>1.0</priority></url>
      <url>
        <loc>https://briantooleyracing.com/btr-560-beehive-valve-spring-set-sp011-16.html</loc>
        <priority>1.0</priority>
      </url>
      <url>
        <loc>https://briantooleyracing.com/03-08-5-7-hemi-cam-bolt.html</loc>
        <priority>1.0</priority>
      </url>
      <url>
        <loc>https://briantooleyracing.com/catalog/product/view/id/71864</loc>
        <priority>1.0</priority>
      </url>
      <url>
        <loc>https://briantooleyracing.com/camshafts-lifters-pushrods.html</loc>
        <priority>0.5</priority>
      </url>
      <url>
        <loc>https://briantooleyracing.com/camshafts-lifters-pushrods/camshafts.html</loc>
        <priority>0.5</priority>
      </url>
      <url>
        <loc>https://briantooleyracing.com/privacy-policy.html</loc>
        <priority>0.2</priority>
      </url>
    </urlset>
    """

    def test_keeps_priority_1_products_only(self, monkeypatch) -> None:
        # Swap the module's fetch_page with a stub so we don't hit the network.
        monkeypatch.setattr(btr_mod, "fetch_page", lambda url, timeout=30: self.SITEMAP_XML)
        urls = _discover_via_sitemap()
        assert urls == [
            "https://briantooleyracing.com/btr-560-beehive-valve-spring-set-sp011-16.html",
            "https://briantooleyracing.com/03-08-5-7-hemi-cam-bolt.html",
        ]

    def test_returns_empty_on_fetch_failure(self, monkeypatch) -> None:
        def _raise(url, timeout=30):
            raise RuntimeError("sitemap unavailable")

        monkeypatch.setattr(btr_mod, "fetch_page", _raise)
        assert _discover_via_sitemap() == []

    def test_returns_empty_on_malformed_xml(self, monkeypatch) -> None:
        monkeypatch.setattr(btr_mod, "fetch_page", lambda url, timeout=30: "not xml at all")
        assert _discover_via_sitemap() == []


class TestDiscoverProductUrls:
    """Env override wins over sitemap discovery; falls back to the default URL."""

    def test_env_override_filters_to_product_urls(self, monkeypatch) -> None:
        monkeypatch.setenv(
            "CRAWLER_BRIANTOOLEYRACING_START_URLS",
            (
                "https://briantooleyracing.com/btr-560-beehive-valve-spring-set-sp011-16.html,"
                "https://briantooleyracing.com/camshafts-lifters-pushrods/camshafts.html,"
                "https://example.com/not-btr.html"
            ),
        )
        adapter = BrianTooleyRacingAdapter()
        urls = list(adapter.discover_product_urls())
        assert urls == ["https://briantooleyracing.com/btr-560-beehive-valve-spring-set-sp011-16.html"]

    def test_falls_back_to_default_when_sitemap_empty(self, monkeypatch) -> None:
        monkeypatch.delenv("CRAWLER_BRIANTOOLEYRACING_START_URLS", raising=False)
        monkeypatch.setattr(btr_mod, "_discover_via_sitemap", lambda: [])
        adapter = BrianTooleyRacingAdapter()
        urls = list(adapter.discover_product_urls())
        assert urls == list(btr_mod.DEFAULT_START_URLS)
