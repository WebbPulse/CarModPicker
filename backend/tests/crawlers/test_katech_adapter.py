"""
Tests for katechengines.com adapter: URL shape guard, host routing,
flat-sitemap discovery (``/i-`` prefix filter), Web Shop Manager microdata
parsing, gallery extraction, and the ``katech.com`` → ``generic`` routing
quirk noted in the adapter docstring.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http import katech as katech_mod
from app.crawlers.adapters.tier0_http.katech import (
    KatechAdapter,
    _discover_via_sitemap,
    _is_product_url,
)

SAMPLE_URL = "https://katechengines.com/i-30497794-katech-c6-remote-clutch-bleeder-kit.html"


def _product_html(
    *,
    name: str = "Katech C6 Remote Clutch Bleeder Kit",
    sku: str = "KAT-A4824",
    price: str = "175.99",
    availability: str = "https://schema.org/InStock",
    brand_name: str = "Katech Engineering",
    description_html: str = (
        "The kit fits 2005-2013 Corvettes and allows you to bleed the clutch from under the hood,"
        " rather than the very difficult position of under the car.<br /><br />"
        "<strong>Fits all 2005-2013 C6 Corvette models</strong>"
    ),
    gallery_full_urls: tuple[str, ...] = (
        "https://katechengines.com/images/F198642236.png",
        "https://katechengines.com/images/F198643835.png",
    ),
    og_image: str = "https://katechengines.com/images/I30497794.jpg",
) -> str:
    """
    Minimal HTML that mirrors katechengines.com Web Shop Manager shape:

    - Product microdata scope wrapping an ``h1[itemprop=name]`` and
      ``span.wsm-prod-sku[itemprop=sku]``.
    - Hidden Offer scope with ``priceCurrency`` + ``price`` + ``availability``.
    - Description div with inline HTML (``<br>``, ``<strong>``).
    - Brand anchor with ``itemprop=brand`` + ``itemtype=http://schema.org/Brand``
      (note the ``http`` — real pages mix http/https schema URLs).
    - Gallery ``<ul class="wsm_product_thumbs">`` with one ``<li>`` per image;
      we only collect anchors pointing at ``/images/F<digits>.<ext>``.
    """
    # Mirror the two real WSM layouts:
    # - single-image products render one ``<a id="primage…" class="colorbox
    #   active" rel="colorbox[product]" href="…/F<N>.<ext>">``.
    # - multi-image products wrap that same anchor in a primage li and add a
    #   ``<ul id="productImageBar">`` with one ``<li class="wsm_product_thumb">``
    #   per photo; both the primage anchor and the li anchors point at the
    #   same ``F<N>`` URL for the first photo, so document-order + dedup
    #   yields a clean ordered list.
    primage_anchor = (
        f'<a id="primage1" class="colorbox active" rel="colorbox[product]" '
        f'href="{gallery_full_urls[0]}" title="primary"></a>'
        if gallery_full_urls
        else ""
    )
    thumb_items = "".join(
        (
            f'<li class="wsm_product_thumb">'
            f'<a onclick="WSM.Product.showImageMain(...); return false;" '
            f'href="{u}" title="Image {idx + 1}">'
            f'<img src="https://katechengines.com/images/T{idx + 1}.png" '
            f'class="wsm_product_thumb_zoom" alt="thumb" /></a>'
            f"</li>"
        )
        for idx, u in enumerate(gallery_full_urls)
    )
    thumb_bar = (
        f'<ul id="productImageBar" class="wsm-prod-image-bar clearfix">{thumb_items}</ul>'
        if len(gallery_full_urls) > 1
        else ""
    )
    gallery_block = primage_anchor + thumb_bar
    brand_block = (
        f'<li class="wsm_product_info_brand"><label>Brand:</label> '
        f'<a itemprop="brand" itemscope itemtype="http://schema.org/Brand" '
        f'href="https://katechengines.com/b-158999-katech-engineering.html">{brand_name}</a></li>'
        if brand_name
        else ""
    )
    return f"""
    <html><head>
      <title>{name}</title>
      <meta property="og:type" content="website" />
      <meta property="og:title" content="{name}" />
      <meta property="og:image" content="{og_image}" />
      <meta property="og:url" content="{SAMPLE_URL}" />
    </head><body>
      <div id="wsm-product-wrapper" class="wsm-product-wrapper-id-30497794"
           itemscope itemtype="https://schema.org/Product">
        <div id="wsm-prod-info">
          <h1 itemprop="name" class="wsm-prod-title">{name}</h1>
          <div class="wsm_product_info_itemid wsm-prod-stock-id wsm-prod-dealer-id">
            <label>SKU: </label><span class="wsm-prod-sku" itemprop="sku">{sku}</span>
          </div>
          <div class="hidden" style="display:none" itemprop="offers"
               itemscope itemtype="https://schema.org/Offer">
            <span itemprop="priceCurrency">USD</span>
            <span itemprop="price">{price}</span>
            <link itemprop="availability" href="{availability}" />
          </div>
          <ul>{brand_block}</ul>
        </div>
        <div id="wsm-tab-decrip" class="wsm-tab-content wsm-tab-content-description">
          <h2 class="wsm-tab-content-header"><span>Description</span></h2>
          <div itemprop="description" class="wsm-prod-tab-content">{description_html}</div>
        </div>
        <div class="wsm-prod-image-section">{gallery_block}</div>
      </div>
    </body></html>
    """


class TestAdapterRegistration:
    """Host routing: ``katechengines.com`` → katech; ``katech.com`` → generic."""

    def test_bare_host_routes_to_katech(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "katech"

    def test_www_subdomain_routes_to_katech(self) -> None:
        assert (
            adapter_name_for_product_url(
                "https://www.katechengines.com/i-30497554-katech-c7-corvette-zr1-stage-1-package.html"
            )
            == "katech"
        )

    def test_katech_com_does_not_route_to_katech(self) -> None:
        # ``katech.com`` is Kinetic Art & Technology, an unrelated motor/
        # actuator shop. Pages captured from that domain must fall through
        # to ``generic`` rather than being parsed as engine SKUs.
        assert adapter_name_for_product_url("https://www.katech.com/product/123") == "generic"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/katech") == "generic"


class TestAdapterFetcherTier:
    """Web Shop Manager responds to plain ``requests`` without a challenge."""

    def test_http_tier_default(self) -> None:
        assert KatechAdapter.FETCHER_TIER == "http"


class TestProductUrlShape:
    """
    Product URLs are root-slug ``/i-<id>-<slug>.html``. Categories
    (``/c-<id>-<slug>.html``), CMS pages (``/p-``), brand landings (``/b-``),
    resource pages (``/rt-``), and footer pages (``/ft-``) share the ``.html``
    suffix but are rejected by the ``/i-`` prefix check.
    """

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_root_path_rejected(self) -> None:
        assert not _is_product_url("https://katechengines.com/")

    def test_category_url_rejected(self) -> None:
        # /c- is the category prefix; WSM sitemap has ~100 of these at priority 0.8.
        assert not _is_product_url("https://katechengines.com/c-1389267-vehicle-performance-packages.html")

    def test_cms_content_page_rejected(self) -> None:
        # /p- is CMS content (about us, manufacturing, etc.); different prefix.
        assert not _is_product_url("https://katechengines.com/p-35851-about-us.html")

    def test_resource_page_rejected(self) -> None:
        # /rt- pages share the ``priority=0.7`` bucket with products; reject by shape.
        assert not _is_product_url("https://katechengines.com/rt-2-engine-management.html")

    def test_brand_landing_rejected(self) -> None:
        assert not _is_product_url("https://katechengines.com/b-158999-katech-engineering.html")

    def test_nested_path_rejected(self) -> None:
        assert not _is_product_url("https://katechengines.com/catalog/i-30497554-foo.html")

    def test_non_html_rejected(self) -> None:
        assert not _is_product_url("https://katechengines.com/i-30497554-foo")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/i-1-foo.html")


class TestParseProductPage:
    """End-to-end parsing: synthetic WSM microdata + gallery → ScrapedPayload."""

    def test_full_page_parses_with_gallery_and_description(self) -> None:
        result = KatechAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "Katech C6 Remote Clutch Bleeder Kit"
        assert result.part_manufacturer == "Katech Engineering"
        # SKU is retailer-prefixed ``KAT-*`` but Katech is the manufacturer
        # here, so the prefixed SKU is effectively the MPN — stored as-is.
        assert result.part_number == "KAT-A4824"
        assert result.price_cents == 17599
        # Description HTML flattened to plain text, line breaks collapsed.
        assert result.description is not None
        assert "Corvettes" in result.description
        assert "Fits all 2005-2013 C6 Corvette models" in result.description
        # Both ``F<N>`` gallery images picked up in DOM order.
        assert result.image_urls == [
            "https://katechengines.com/images/F198642236.png",
            "https://katechengines.com/images/F198643835.png",
        ]
        assert result.product_url == SAMPLE_URL

    def test_preorder_product_parses(self) -> None:
        # Some Katech stage packages ship with ``availability="PreOrder / PreSale"``;
        # the Offer scope still surfaces price normally.
        result = KatechAdapter().parse_product_page(
            _product_html(
                name="Katech C7 Corvette ZR1 Stage 1 Package",
                sku="KAT-C7ZR1-1",
                price="6499.99",
                availability="https://schema.org/PreOrder / PreSale",
                gallery_full_urls=("https://katechengines.com/images/F198642815.jpg",),
            ),
            "https://katechengines.com/i-30497554-katech-c7-corvette-zr1-stage-1-package.html",
        )
        assert result is not None
        assert result.name == "Katech C7 Corvette ZR1 Stage 1 Package"
        assert result.part_number == "KAT-C7ZR1-1"
        assert result.price_cents == 649999
        assert result.image_urls == ["https://katechengines.com/images/F198642815.jpg"]

    def test_falls_back_to_og_image_without_gallery(self) -> None:
        # Legacy SKUs sometimes render only the auto-generated ``I<product-id>``
        # thumbnail with no ``wsm_product_thumbs`` list. OG image picks up
        # that single URL so the part still lands with a preview image.
        html = _product_html(gallery_full_urls=())
        result = KatechAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls == ["https://katechengines.com/images/I30497794.jpg"]

    def test_dedup_by_path_ignores_querystring_variants(self) -> None:
        # Same photo appearing twice in the gallery li stream collapses to one entry.
        html = _product_html(
            gallery_full_urls=(
                "https://katechengines.com/images/F1.jpg?v=1",
                "https://katechengines.com/images/F1.jpg?v=2",
                "https://katechengines.com/images/F2.jpg",
            )
        )
        result = KatechAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls == [
            "https://katechengines.com/images/F1.jpg?v=1",
            "https://katechengines.com/images/F2.jpg",
        ]

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape must not feed category pages through this adapter
        # just because the host matches — shape guard kicks in first.
        result = KatechAdapter().parse_product_page(
            _product_html(),
            "https://katechengines.com/c-1389267-vehicle-performance-packages.html",
        )
        assert result is None

    def test_missing_product_microdata_returns_none(self) -> None:
        # No ``itemtype=Product`` scope — typical WSM soft-404 on a
        # discontinued SKU. Return None so the ingest pipeline doesn't
        # write a blank part row.
        html = "<html><head><title>404 Not Found</title></head><body></body></html>"
        assert KatechAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_missing_name_returns_none(self) -> None:
        # Product scope present but the ``h1[itemprop=name]`` is empty —
        # treat as malformed and skip rather than storing a blank name.
        html = (
            '<html><body><div itemscope itemtype="https://schema.org/Product">'
            '<h1 itemprop="name"></h1>'
            '<span itemprop="sku">KAT-A4824</span>'
            "</div></body></html>"
        )
        assert KatechAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestDiscoverViaSitemap:
    """
    Sitemap discovery filters a flat urlset by URL-path shape (``/i-`` prefix,
    ``.html`` suffix). Priority alone is insufficient — ``/rt-`` resource
    pages share the products' ``priority=0.7`` bucket.
    """

    SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://katechengines.com</loc><priority>1.0</priority></url>
      <url>
        <loc>https://katechengines.com/i-30497794-katech-c6-remote-clutch-bleeder-kit.html</loc>
        <priority>0.7</priority>
      </url>
      <url>
        <loc>https://katechengines.com/i-30498198-g6-camaro-ss-lt1-stage-3.html</loc>
        <priority>0.7</priority>
      </url>
      <url>
        <loc>https://katechengines.com/rt-2-engine-management.html</loc>
        <priority>0.7</priority>
      </url>
      <url>
        <loc>https://katechengines.com/c-1389267-vehicle-performance-packages.html</loc>
        <priority>0.8</priority>
      </url>
      <url>
        <loc>https://katechengines.com/p-35851-about-us.html</loc>
        <priority>0.9</priority>
      </url>
      <url>
        <loc>https://katechengines.com/ft-2432-privacy-policy.html</loc>
        <priority>0.6</priority>
      </url>
    </urlset>
    """

    def test_keeps_i_prefixed_products_only(self, monkeypatch) -> None:
        # Swap the module's fetch_page with a stub so we don't hit the network.
        monkeypatch.setattr(katech_mod, "fetch_page", lambda url, timeout=30: self.SITEMAP_XML)
        urls = _discover_via_sitemap()
        assert urls == [
            "https://katechengines.com/i-30497794-katech-c6-remote-clutch-bleeder-kit.html",
            "https://katechengines.com/i-30498198-g6-camaro-ss-lt1-stage-3.html",
        ]

    def test_dedupes_repeat_entries(self, monkeypatch) -> None:
        dup_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://katechengines.com/i-1-widget.html</loc></url>
          <url><loc>https://katechengines.com/i-1-widget.html?utm_source=x</loc></url>
        </urlset>
        """
        monkeypatch.setattr(katech_mod, "fetch_page", lambda url, timeout=30: dup_xml)
        urls = _discover_via_sitemap()
        assert urls == ["https://katechengines.com/i-1-widget.html"]

    def test_returns_empty_on_fetch_failure(self, monkeypatch) -> None:
        def _raise(url, timeout=30):
            raise RuntimeError("sitemap unavailable")

        monkeypatch.setattr(katech_mod, "fetch_page", _raise)
        assert _discover_via_sitemap() == []

    def test_returns_empty_on_malformed_xml(self, monkeypatch) -> None:
        monkeypatch.setattr(katech_mod, "fetch_page", lambda url, timeout=30: "not xml at all")
        assert _discover_via_sitemap() == []


class TestDiscoverProductUrls:
    """Env override wins over sitemap discovery; falls back to the default URL."""

    def test_env_override_filters_to_product_urls(self, monkeypatch) -> None:
        monkeypatch.setenv(
            "CRAWLER_KATECH_START_URLS",
            (
                "https://katechengines.com/i-30497794-katech-c6-remote-clutch-bleeder-kit.html,"
                "https://katechengines.com/c-1389267-vehicle-performance-packages.html,"
                "https://example.com/not-katech.html"
            ),
        )
        adapter = KatechAdapter()
        urls = list(adapter.discover_product_urls())
        assert urls == [
            "https://katechengines.com/i-30497794-katech-c6-remote-clutch-bleeder-kit.html",
        ]

    def test_falls_back_to_default_when_sitemap_empty(self, monkeypatch) -> None:
        monkeypatch.delenv("CRAWLER_KATECH_START_URLS", raising=False)
        monkeypatch.setattr(katech_mod, "_discover_via_sitemap", lambda: [])
        adapter = KatechAdapter()
        urls = list(adapter.discover_product_urls())
        assert urls == list(katech_mod.DEFAULT_START_URLS)
