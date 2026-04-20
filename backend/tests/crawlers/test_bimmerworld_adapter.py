"""
Tests for bimmerworld.com adapter: URL guard, registration, fetcher tier, and
the NetSuite SuiteCommerce parsing path (DOM IDs + inline-script vars, no
JSON-LD because Bimmerworld populates the JSON-LD block in JavaScript).
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.bimmerworld import (
    BimmerworldAdapter,
    _is_product_url,
)

SAMPLE_URL = "https://www.bimmerworld.com/Brakes/StopTech-ST60-380-Big-Brake-Kit-E9X-335i.html"


def _product_html(
    *,
    name: str = "StopTech ST60 380 Big Brake Kit - E9X 335i",
    short_description: str = "Front, 6-piston, balance-optimized, big brake kit for E9X 335i",
    full_description: str = (
        "StopTech 380 ST60 Big Brake Kit for E9X 335i features - "
        "Drilled or Slotted 2pc Aerorotors. 6-piston ST60 forged calipers. "
        "Forged caliper brackets. Sport pads. DOT-compliant stainless brake lines."
    ),
    price: str = "$3,959.46",
    brand: str = "StopTech",
    itemid: str = "83.154.6800",
    primary_media_id: str = "240059",
    zoom_media_id: str = "240060",
    extra_zoom_media_id: str = "240070",
) -> str:
    """
    Mirror Bimmerworld's NetSuite SuiteCommerce product page: hidden
    ``#productName`` / ``#productDescription`` / ``#priceDisplay`` spans,
    a ``.product-image-slider`` gallery with ``data-zoom`` attrs on each
    ``.slide``, an empty ``#dynamicJSONLD`` script (built by JS at runtime),
    and an inline ``<script>`` that defines ``var brand`` / ``var itemid``.
    """
    og_image = f"https://www.bimmerworld.com/core/media/media.nl?id={primary_media_id}" "&c=3750282&h=AAAprimary"
    primary_zoom = f"/core/media/media.nl?id={zoom_media_id}&c=3750282&h=BBBzoom"
    extra_zoom = f"/core/media/media.nl?id={extra_zoom_media_id}&c=3750282&h=CCCzoom"
    duplicate_thumb_of_primary = f"/core/media/media.nl?id={primary_media_id}&c=3750282&h=ZZZsmall"
    return f"""
    <html><head>
      <meta name="description" content="This is BMW parts item {itemid} described as {name}.">
      <meta property="og:type" content="product">
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{short_description}">
      <meta property="og:image" content="{og_image}">
    </head><body>
      <h1>{name}</h1>
      <span id="priceDisplay" style="display: none;">{price}</span>
      <span id="productName" style="display: none;">{name}</span>
      <span id="productDescription" style="display: none;">{short_description}</span>

      <div class="product-image">
        <div class="product-image-slider flexslider flexslider-product">
          <div class="slides">
            <div id="slide0" class="slide"
                 data-thumb="{duplicate_thumb_of_primary}"
                 data-zoom="{primary_zoom}"></div>
            <div id="slide1" class="slide"
                 data-thumb="/stoptech-ST60-tn.jpg"
                 data-zoom="/stoptech-ST60-2-piece-drilled-rotor-red-caliper.jpg"></div>
            <div id="slide2" class="slide"
                 data-thumb="/stoptech-ST60-installed-tn.jpg"
                 data-zoom="{extra_zoom}"></div>
          </div>
        </div>
      </div>

      <div class="product-desc-block">
        <div id="tabs-products">
          <div id="tabs-1">
            <div class="tab-content1 resp-tab-content resp-tab-content-active">
              {full_description}
            </div>
          </div>
        </div>
      </div>

      <script type="text/javascript">
        // The dynamic JSON-LD builder reads these vars; we extract them by regex.
        var image = "{og_image}";
        var itemid="{itemid}";
        var mpn="" || itemid;
        var brand="{brand}";
        var instock="0";
      </script>
      <script id="dynamicJSONLD" type="application/ld+json"></script>
    </body></html>
    """


class TestAdapterRegistration:
    """The host-to-adapter map routes every bimmerworld.com page through this adapter."""

    def test_www_host_maps_to_bimmerworld(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "bimmerworld"

    def test_bare_host_also_maps(self) -> None:
        assert adapter_name_for_product_url("https://bimmerworld.com/Brakes/Front-Brake-Disc.html") == "bimmerworld"

    def test_unrelated_host_does_not_map(self) -> None:
        assert adapter_name_for_product_url("https://example.com/Brakes/Foo.html") != "bimmerworld"


class TestProductUrlGuard:
    """
    Shape guard: any path on the Bimmerworld host that ends with ``.html``
    *except* a small CMS denylist. Category and "About" pages end with ``/``
    on this site, so the trailing extension is the structural separator.
    """

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_deeply_nested_product_url(self) -> None:
        assert _is_product_url(
            "https://www.bimmerworld.com/BMW-Interior/BMW-Interior-Floor-Mats/"
            "Rear-All-Weather-Floor-Mats-Black-Red-F48-X1.html"
        )

    def test_category_path_rejected(self) -> None:
        # Categories end in / on Bimmerworld — they aren't product pages.
        assert not _is_product_url("https://www.bimmerworld.com/Brakes/")
        assert not _is_product_url("https://www.bimmerworld.com/About-Us/BMW-Tech-Info/")

    def test_cms_denylist_rejected(self) -> None:
        # Gift cards / wishlist end in .html on this site but aren't products.
        assert not _is_product_url("https://www.bimmerworld.com/Gift-Certificate.html")
        assert not _is_product_url("https://www.bimmerworld.com/Wishlist.html")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/Brakes/StopTech.html")


class TestParseProductPage:
    """End-to-end adapter parsing: synthetic NetSuite-shape HTML → ScrapedPayload."""

    def test_full_page_parses(self) -> None:
        result = BimmerworldAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "StopTech ST60 380 Big Brake Kit - E9X 335i"
        assert result.part_manufacturer == "StopTech"
        assert result.part_number == "83.154.6800"
        assert result.price_cents == 395946
        assert result.product_url == SAMPLE_URL
        # Description tab beats the short blurb.
        assert result.description and "Aerorotors" in result.description
        assert result.image_urls is not None and len(result.image_urls) >= 2

    def test_description_tab_wins_over_short_blurb(self) -> None:
        # The hidden #productDescription span is a one-liner; the #tabs-1
        # tab carries the full feature copy. Adapter must prefer the tab.
        result = BimmerworldAdapter().parse_product_page(
            _product_html(short_description="Short.", full_description="Much longer feature copy."),
            SAMPLE_URL,
        )
        assert result is not None
        assert result.description == "Much longer feature copy."

    def test_falls_back_to_meta_description_when_short_blurb_only(self) -> None:
        # No tab content, no productDescription span — fall back to og:description.
        html = """
        <html><head>
          <meta property="og:title" content="OEM Air Filter">
          <meta property="og:description" content="Direct fit replacement air filter.">
          <meta property="og:image" content="https://www.bimmerworld.com/core/media/media.nl?id=1&c=3750282&h=h">
        </head><body>
          <span id="productName">OEM Air Filter</span>
          <span id="priceDisplay">$24.95</span>
        </body></html>
        """
        result = BimmerworldAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.description == "Direct fit replacement air filter."
        assert result.price_cents == 2495

    def test_image_gallery_deduped_by_media_id(self) -> None:
        # primary_media_id appears as og:image AND as a data-thumb on slide0
        # under a different ``h=`` hash — both should collapse to one entry.
        result = BimmerworldAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        media_ids = []
        for u in result.image_urls:
            if "media.nl" in u:
                media_ids.append(u.split("id=", 1)[1].split("&", 1)[0])
        assert media_ids == ["240059", "240060", "240070"]

    def test_part_number_falls_back_to_meta_description(self) -> None:
        # Strip the inline-script vars entirely; the static meta description's
        # "BMW parts item <ID>" lead is the documented fallback.
        html = """
        <html><head>
          <meta name="description" content="This is BMW parts item 11.53.7.583.146 described as Some Part.">
          <meta property="og:title" content="Some Part">
        </head><body>
          <span id="productName">Some Part</span>
        </body></html>
        """
        result = BimmerworldAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "11.53.7.583.146"
        # No inline-script var means no brand was on the page.
        assert result.part_manufacturer is None

    def test_non_product_url_returns_none(self) -> None:
        # Guard for the archive rescrape pipeline: don't feed category /
        # CMS pages through this parser even though their host matches.
        result = BimmerworldAdapter().parse_product_page(
            _product_html(),
            "https://www.bimmerworld.com/Brakes/",
        )
        assert result is None

    def test_missing_name_returns_none(self) -> None:
        html = "<html><body><p>Out of stock.</p></body></html>"
        assert BimmerworldAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """Bimmerworld is plain HTTP — no Cloudflare block, no TLS fingerprint check."""

    def test_declares_http_tier(self) -> None:
        assert BimmerworldAdapter.FETCHER_TIER == "http"
