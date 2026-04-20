"""Tests for z1motorsports.com adapter: URL shape, microdata parse, image dedupe, never-emit-internal-id rule."""

from app.crawlers.adapters.tier1_tls.z1motorsports import (
    Z1MotorsportsAdapter,
    _canonicalize_product_url,
    _image_dedup_key,
    _is_product_url,
)

SAMPLE_URL = (
    "https://www.z1motorsports.com/big-brake-upgrades/z1-motorsports/"
    "z1-350z-g35-forged-street-big-brake-upgrade-front-and-rear-p-43428.html"
)


def _product_html(
    *,
    name: str = "Z1 350Z / G35 Forged Street Big Brake Upgrade (Front & Rear)",
    brand: str = "Z1 Motorsports",
    sku: str = " 43428",
    price: str = "1649.99",
    description: str = "Z1's Street Big Brake Kit is a complete brake upgrade package.",
    image_meta: str = "ss26_43428.jpg",
    orig_img: str = "https://cdn.z1motorsports.com/images/ss26_43428.jpg",
    thumb_1200: str = "https://cdn.z1motorsports.com/images/thumbs/1200x900_ss26_43428.webp",
    thumb_200: str = "https://cdn.z1motorsports.com/images/thumbs/200x150_ss26_43428.webp",
    second_photo: str = "https://cdn.z1motorsports.com/images/thumbs/1200x900_Z1_Forged_Street_Rear.webp",
) -> str:
    """Minimal page mirroring Z1's microdata-driven product layout (no JSON-LD Product block)."""
    return f"""
    <html><head>
      <title itemprop='name'>{name}</title>
    </head><body>
      <form id="formAddToCart">
        <meta itemprop="sku" content="{sku}" />
        <meta itemprop="itemCondition" content="http://schema.org/NewCondition" />
        <h1><span itemprop="name">{name}</span></h1>
        <div id='pi-brand'>Brand:
          <a href="/z1-motorsports-m-1.html" itemprop="brand">{brand}</a>
        </div>
        <div id="productDescriptionContainer">
          <meta itemprop="image" content="{image_meta}" />
          <div class="product-img-gal-display">
            <figure data-orig-img="{orig_img}" data-display-img="{thumb_1200}" data-zoom-img="{thumb_1200}">
              <img src="{thumb_1200}" />
            </figure>
          </div>
          <div class="product-img-gal-sel">
            <figure data-small-img="{thumb_200}" data-display-img="{thumb_1200}" data-zoom-img="{thumb_1200}"></figure>
            <figure data-small-img="{thumb_200}" data-display-img="{second_photo}" data-zoom-img="{second_photo}"></figure>
          </div>
        </div>
        <div itemprop="description">{description}</div>
        <div id="display_price_bottom">
          <span class="sp-newPrice" itemprop="price" content="{price}">${price}</span>
          <span class="sp-oldPrice">$1,799.99</span>
        </div>
      </form>
    </body></html>
    """


class TestProductUrlShape:
    """The product suffix ``/<slug>-p-<digits>.html`` anchors URL identification."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_bare_host_with_http_scheme(self) -> None:
        # Sitemap mixes http://z1motorsports.com/... (no www) with https://www.z1motorsports.com/...;
        # both must be recognized as valid product URLs before canonicalization.
        url = (
            "http://z1motorsports.com/chassis-reinforcement/z1-motorsports/"
            "z1-370z-carbon-fiber-strut-tower-brace-p-46168.html"
        )
        assert _is_product_url(url)

    def test_category_url_rejected(self) -> None:
        # Category URLs follow ``-c-<digits>[_<digits>]*.html`` and must NOT
        # flow into the parser — only the product-suffix shape is accepted.
        assert not _is_product_url("https://www.z1motorsports.com/performance-parts/brakes-c-6_9.html")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/unrelated-page-p-12345.html")

    def test_canonicalize_upgrades_scheme_and_host(self) -> None:
        # Both the http scheme and the bare host get rewritten to the
        # canonical https://www.z1motorsports.com/... form used downstream.
        raw = (
            "http://z1motorsports.com/chassis-reinforcement/z1-motorsports/"
            "z1-370z-carbon-fiber-strut-tower-brace-p-46168.html"
        )
        canonical = _canonicalize_product_url(raw)
        assert canonical is not None
        assert canonical.startswith("https://www.z1motorsports.com/")
        assert canonical.endswith("-p-46168.html")

    def test_canonicalize_strips_query_string(self) -> None:
        # Product pages on Z1 never take a query string; drop trackers if any
        # are attached upstream so the downstream dedup key is stable.
        canonical = _canonicalize_product_url(SAMPLE_URL + "?utm_source=email")
        assert canonical == SAMPLE_URL

    def test_canonicalize_rejects_non_product(self) -> None:
        assert _canonicalize_product_url("https://www.z1motorsports.com/about.html") is None


class TestImageDedupe:
    """Same photo at multiple resolutions must collapse to a single gallery entry."""

    def test_strips_size_prefix_and_extension(self) -> None:
        assert _image_dedup_key("https://cdn.z1motorsports.com/images/ss26_43428.jpg") == "ss26_43428"
        assert _image_dedup_key("https://cdn.z1motorsports.com/images/thumbs/1200x900_ss26_43428.webp") == "ss26_43428"
        assert _image_dedup_key("https://cdn.z1motorsports.com/images/thumbs/200x150_ss26_43428.webp") == "ss26_43428"

    def test_different_photos_have_different_keys(self) -> None:
        a = _image_dedup_key("https://cdn.z1motorsports.com/images/thumbs/1200x900_ss26_43428.webp")
        b = _image_dedup_key("https://cdn.z1motorsports.com/images/thumbs/1200x900_Z1_Forged_Rear.webp")
        assert a != b


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape microdata HTML → ScrapedPayload."""

    def test_full_page_parses(self) -> None:
        result = Z1MotorsportsAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Z1 350Z")
        assert result.part_manufacturer == "Z1 Motorsports"
        assert result.price_cents == 164999
        assert result.product_url == SAMPLE_URL
        assert result.description and "Street Big Brake Kit" in result.description
        # Hero photo + one distinct second photo — size variants of the hero
        # collapse via _image_dedup_key to a single entry.
        assert result.image_urls is not None
        assert len(result.image_urls) == 2

    def test_never_uses_internal_sku_as_part_number(self) -> None:
        # The itemprop="sku" value (" 43428") is Z1's internal product id, not
        # an MPN. It must never leak into part_number or cross-retailer dedup
        # breaks. Same rule as Vivid Racing.
        result = Z1MotorsportsAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        if result.part_number is not None:
            assert "43428" not in result.part_number

    def test_picks_sale_price_not_old_price(self) -> None:
        # sp-newPrice carries itemprop="price"; sp-oldPrice doesn't. Confirm we
        # always pull the current (sale) price, never the crossed-out figure.
        result = Z1MotorsportsAdapter().parse_product_page(_product_html(price="899.00"), SAMPLE_URL)
        assert result is not None
        assert result.price_cents == 89900

    def test_filename_only_image_anchored_to_cdn(self) -> None:
        # <meta itemprop="image" content="ss26_43428.jpg"> must resolve to the
        # full cdn.z1motorsports.com/images/ URL.
        html = """
        <html><body>
          <h1><span itemprop="name">Z1 Sample Widget</span></h1>
          <a itemprop="brand">Z1 Motorsports</a>
          <meta itemprop="image" content="ss26_99999.jpg" />
          <span itemprop="price" content="19.99">$19.99</span>
        </body></html>
        """
        result = Z1MotorsportsAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        assert result.image_urls[0].startswith("https://cdn.z1motorsports.com/images/")
        assert result.image_urls[0].endswith("ss26_99999.jpg")

    def test_non_product_url_returns_none(self) -> None:
        # Guard: the entry check rejects URLs that aren't product pages so the
        # archive rescrape pipeline can't feed category pages through this adapter.
        result = Z1MotorsportsAdapter().parse_product_page(
            _product_html(),
            "https://www.z1motorsports.com/performance-parts/brakes-c-6_9.html",
        )
        assert result is None

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert Z1MotorsportsAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """Z1 must declare the TLS fetcher tier — Cloudflare blocks plain HTTP."""

    def test_declares_tls_tier(self) -> None:
        assert Z1MotorsportsAdapter.FETCHER_TIER == "tls"
