"""
Tests for essexparts.com adapter: host routing, URL shape filter, brand alias
normalization, and end-to-end parse of a synthetic custom-Laravel product page.

Essex is the US AP Racing distributor — no JSON-LD, no Schema.org microdata.
The adapter relies on ``og:type=product`` plus a ``.detail-section`` block
(Part #, Brand, summary) and ``.product-price .price`` for the main price.
These tests run against *synthetic* HTML modeled on a real product page so
they don't depend on live network access.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.essexparts import (
    EssexPartsAdapter,
    _is_product_url,
    _normalize_part_manufacturer,
)

SAMPLE_URL = (
    "https://www.essexparts.com/" "essex-designed-ap-racing-radi-cal-competition-brake-kit-front-cp9668390mm-r35gtr"
)


def _product_html(
    *,
    name: str = "AP Racing by Essex Radi-CAL Competition Brake Kit (Front 9668/390mm)- R35 Nissan GT-R",
    brand: str = "Essex & AP Racing",
    part_number: str = "13.01.10051",
    price: str = "$6,699.00",
    description: str = (
        "Complete front AP Racing by Essex Radi-CAL Competition Brake Kit for the R35 Nissan GT-R. "
        "Features AP Racing CP9668 Radi-CAL Pro5000R six piston calipers."
    ),
    hero_image: str = "/imagecache/productXLarge/22-es_-_web_listing_cp9668_-_23.png",
    gallery_images: tuple[str, ...] = (
        "/imagecache/productXLarge/cp9668_profile_view_web_4_7.jpg",
        "/imagecache/productXLarge/cp9668_back_view_web_4_7.jpg",
    ),
    og_type: str = "product",
    include_option_prices: bool = True,
) -> str:
    """Minimal page mirroring Essex's custom Laravel storefront."""
    # These dollar amounts live in <select> options before the main price in
    # source order — the adapter must not pick them up as the product price.
    option_block = ""
    if include_option_prices:
        option_block = """
        <div class="product-options">
          <select class="prd-opt" name="option_81">
            <option value="81|711">Ferodo DS2500 + $250.00</option>
            <option value="81|712">Ferodo DS1.11 + $250.00</option>
          </select>
          <select class="prd-opt" name="option_116">
            <option value="116|758">CP9668 Pad Tension Kit (x2) + $170.00</option>
          </select>
        </div>
        """
    thumb_links = "\n".join(
        f'<a href="" class="thumb-swap" data-image="{img}" data-num="{i + 2}">'
        f'<img src="/imagecache/productThumb/{img.rsplit("/", 1)[-1]}"/></a>'
        for i, img in enumerate(gallery_images)
    )
    return f"""
    <!doctype html>
    <html lang="en"><head>
      <title>{name} | Essex Parts Services, Inc.</title>
      <meta name="description" content="Essex Parts Racing Parts Brakes Brake Kits Service Provider">
      <meta property="og:title" content="{name} | Essex Parts Services, Inc." />
      <meta property="og:type" content="{og_type}" />
      <meta property="og:url" content="{SAMPLE_URL}" />
      <meta property="og:image" content="https://www.essexparts.com{hero_image}" />
    </head><body>
      <div id="breadcrumbs"></div>
      <div class="product-detail">
        <div class="product-image">
          <div class="zoom ex1">
            <img itemprop="image" src="{hero_image}" width="800" height="720" alt="hero" />
          </div>
          <div class="product-thumbs">
            {thumb_links}
          </div>
        </div>
        <div class="detail-section">
          <h3>{name}</h3>
          <p><strong>Part #:</strong> {part_number}</p>
          <p><strong>Brand:</strong> {brand}</p>
          <div class="product-summary"><p>{description}</p></div>
          <form method="POST" action="/cart/add">
            {option_block}
            <h2 class="product-price">
              <span class="price">{price}</span>
            </h2>
          </form>
        </div>
      </div>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_www_host_routes_to_essexparts(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "essexparts"

    def test_bare_host_routes_to_essexparts(self) -> None:
        assert (
            adapter_name_for_product_url(
                "https://essexparts.com/essex-designed-ap-racing-radi-cal-competition-brake-kit-front-cp9668390mm-r35gtr"
            )
            == "essexparts"
        )

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/essexparts") == "generic"


class TestFetcherTier:
    """No Cloudflare — plain HTTP is sufficient for essexparts.com."""

    def test_http_tier_default(self) -> None:
        assert EssexPartsAdapter.FETCHER_TIER == "http"


class TestProductUrlShape:
    """Root-slug URLs on the Essex host, filtered against known non-product prefixes."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/some-brake-kit/")

    def test_root_path_rejected(self) -> None:
        assert not _is_product_url("https://www.essexparts.com/")

    def test_category_paths_rejected(self) -> None:
        # Category/CMS first-segments should never be ingested as products.
        for path in (
            "/brake-pads",
            "/brake-discs",
            "/brake-calipers",
            "/big-brake-kits",
            "/news-blog/some-post-slug",
            "/company-information",
            "/support",
            "/cart/view",
            "/checkout/method",
            "/customer/login",
            "/manufacturer/ohlins",
            "/formula-sae/ap-racing-fsae",
            "/dealer-locator",
        ):
            assert not _is_product_url(f"https://www.essexparts.com{path}"), path

    def test_pagination_query_rejected(self) -> None:
        # ?page=N is category pagination; don't treat those as products.
        assert not _is_product_url("https://www.essexparts.com/big-brake-kits?page=2")

    def test_short_root_slug_rejected(self) -> None:
        # Real product slugs are long and descriptive; short bare roots are navigation.
        assert not _is_product_url("https://www.essexparts.com/contact")

    def test_sitemap_cms_slugs_rejected(self) -> None:
        # Sitemap surfaces CMS / legal / home / category slugs as single-segment
        # URLs that pass the length guard but are never product pages.
        for path in (
            "/privacy-policy",
            "/terms-and-conditions",
            "/home-page",
            "/featured-products",
            "/essex-designed-apracing-radical-competition-brake-kits",
        ):
            assert not _is_product_url(f"https://www.essexparts.com{path}"), path


class TestNormalizePartManufacturer:
    """Co-brand aliases map to the upstream manufacturer; others pass through."""

    def test_essex_ap_racing_normalized_to_ap_racing(self) -> None:
        assert _normalize_part_manufacturer("Essex & AP Racing") == "AP Racing"
        assert _normalize_part_manufacturer("Essex and AP Racing") == "AP Racing"
        assert _normalize_part_manufacturer("Essex Parts") == "AP Racing"

    def test_third_party_brands_pass_through(self) -> None:
        assert _normalize_part_manufacturer("AP Racing") == "AP Racing"
        assert _normalize_part_manufacturer("Ferodo") == "Ferodo"
        assert _normalize_part_manufacturer("Öhlins") == "Öhlins"
        assert _normalize_part_manufacturer("Hyperco") == "Hyperco"
        assert _normalize_part_manufacturer("Spiegler") == "Spiegler"
        assert _normalize_part_manufacturer("Mintex") == "Mintex"

    def test_case_insensitive_alias(self) -> None:
        assert _normalize_part_manufacturer("essex & ap racing") == "AP Racing"

    def test_empty_passed_through(self) -> None:
        assert _normalize_part_manufacturer(None) is None
        assert _normalize_part_manufacturer("") == ""

    def test_whitespace_trimmed(self) -> None:
        assert _normalize_part_manufacturer("  Ferodo  ") == "Ferodo"


class TestParseProductPage:
    """End-to-end parse of synthetic Essex product HTML."""

    def test_happy_path(self) -> None:
        result = EssexPartsAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        # Name comes from the .detail-section <h3>, not the site-suffixed <title>.
        assert result.name.startswith("AP Racing by Essex Radi-CAL Competition Brake Kit")
        assert "| Essex Parts Services" not in result.name
        # Co-brand alias applied: Essex & AP Racing → AP Racing.
        assert result.part_manufacturer == "AP Racing"
        assert result.part_number == "13.01.10051"
        # Main product price wins over the option-price $250/$170 lines above it.
        assert result.price_cents == 669900
        assert result.product_url == SAMPLE_URL
        assert result.description is not None and "Radi-CAL" in result.description
        # Both hero (itemprop=image) and gallery thumbs are collected.
        assert result.image_urls is not None
        assert len(result.image_urls) == 3
        assert all(u.startswith("https://www.essexparts.com/imagecache/") for u in result.image_urls)

    def test_rejects_category_page(self) -> None:
        # Category pages carry og:type=website — they must never be ingested
        # even if the rest of the DOM looks close to a product page.
        html = _product_html(og_type="website")
        assert EssexPartsAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_rejects_non_product_url(self) -> None:
        # Even a perfectly-formed product HTML page at a non-product URL (e.g.
        # a category path) is dropped by the URL guard before parsing runs.
        assert EssexPartsAdapter().parse_product_page(_product_html(), "https://www.essexparts.com/brake-pads") is None

    def test_price_ignores_option_prices(self) -> None:
        # Sanity regression: option <select> dollar values ($250, $170) appear
        # before the main price in source order. Naive "first $ in body" logic
        # would return 25000. The adapter targets .product-price .price only.
        result = EssexPartsAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.price_cents == 669900

    def test_third_party_brand_preserved(self) -> None:
        # Essex resells Ferodo pads, Öhlins shocks, Hyperco springs, etc. The
        # upstream brand must pass through unchanged so cross-retailer dedupe
        # matches on (manufacturer, part_number) with Turner / FCP / Summit.
        result = EssexPartsAdapter().parse_product_page(
            _product_html(
                name="Ferodo DS2500 Brake Pads — BMW M4 F82 Front",
                brand="Ferodo",
                part_number="FCP4611H",
                price="$299.00",
            ),
            "https://www.essexparts.com/ferodo-ds2500-brake-pads-bmw-m4-f82-front",
        )
        assert result is not None
        assert result.part_manufacturer == "Ferodo"
        assert result.part_number == "FCP4611H"
        assert result.price_cents == 29900

    def test_missing_detail_section_returns_none(self) -> None:
        # No og:type=product and no .product-price block → not a product page.
        html = "<html><head></head><body><h1>Contact Us</h1></body></html>"
        assert EssexPartsAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_missing_name_returns_none(self) -> None:
        # og:type=product + product-price but no <h3>, og:title, <title>, or h1.
        html = """
        <html><head><meta property="og:type" content="product" /></head>
        <body><h2 class="product-price"><span class="price">$10.00</span></h2></body>
        </html>
        """
        assert EssexPartsAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_images_reject_non_product_assets(self) -> None:
        # Swap the hero image for a site logo outside /imagecache/ — it must
        # not appear in the output. Gallery thumbs (inside /imagecache/) still do.
        html = _product_html(
            hero_image="/skins/base/images/structure/logo.png",
        )
        result = EssexPartsAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        assert all("/imagecache/" in u for u in result.image_urls)
        assert all("logo.png" not in u for u in result.image_urls)
