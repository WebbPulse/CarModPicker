"""
Tests for hrewheels.com adapter: URL guard, registration, fetcher tier,
and the catalog-only parsing path (brand always HRE, no prices, hero +
original-resolution gallery from the custom PHP template).
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.hrewheels import (
    HREWheelsAdapter,
    _canonicalize_sitemap_url,
    _is_product_url,
)

PRODUCT_URL = "https://www.hrewheels.com/wheels/series-p1/p101"
CLASSIC_URL = "https://www.hrewheels.com/wheels/classic-series/305m"


def _product_html(
    *,
    name: str = "Series P1 - P101",
    h1_model: str = "P101",
    series: str = "Series P1",
    category: str = "Forged",
    display_price: str = "Starting at $3,350 USD each",
    description_paragraphs: tuple[str, ...] = (
        "The Series P1 is HRE's best-selling series of forged wheels.",
        "The Series P1 serves as the perfect complement to modern sports GTs.",
    ),
    hero_src: str = "//s3.amazonaws.com/cdn.hrewheels.com/img/wheel-422x409/137764070426c54b10fac91b060845fab004a557d2.png",
    alt_data_large: tuple[str, ...] = (
        "//s3.amazonaws.com/cdn.hrewheels.com/img/wheel-original/137764070426c54b10fac91b060845fab004a557d2.png",
        "//s3.amazonaws.com/cdn.hrewheels.com/img/wheel-original/1377652372e8da1af915225aa52faedc542deb4cd8.JPG",
    ),
    og_image: str = "//s3.amazonaws.com/cdn.hrewheels.com/img/wheel-160x155/137764070426c54b10fac91b060845fab004a557d2.png",
    include_affirm: bool = True,
    logo_noise_src: str = "/img/logo-Brembo.jpg",
) -> str:
    affirm_block = '<p>As low as $558/mo with Affirm. <a href="#">Apply now</a></p>' if include_affirm else ""
    description_html = "".join(f"<p>{para}</p>" for para in description_paragraphs)
    alt_html = "".join(
        f'<a href="{src}" data-large="{src}" data-id="{i}"><img src="{src}"/></a>'
        for i, src in enumerate(alt_data_large)
    )
    return f"""
    <html><head>
      <title>{name} | HRE Performance Wheels</title>
      <meta property="og:title" content="{name}"/>
      <meta property="og:description" content=""/>
      <meta property="og:image" content="{og_image}"/>
    </head><body>
      <div class="MainImage"><img src="{hero_src}"/></div>
      <div class="MainInformation">
        <h1 class="WheelName">{h1_model}</h1>
        <div class="SeriesName">{series}</div>
        <div class="Category">{category}</div>
        <div class="ConstructionType"><p>Monoblok</p></div>
        <div class="SeriesDisplayPrice">{display_price}</div>
        {affirm_block}
        {description_html}
        <p>Finish Shown: Brushed Dark Clear</p>
        <p class="ViewFinishes"><a href="#">View available finishes</a></p>
        <a href="/get-quote?wid=59" class="Button Alt SpecialOrder">Get Quote</a>
      </div>
      <div class="clearfix WheelAltImages">
        {alt_html}
      </div>
      <div class="WheelSpecifications">
        <img src="{logo_noise_src}"/>
      </div>
    </body></html>
    """


class TestAdapterRegistration:
    """Host mapping routes hrewheels.com (bare + www) to this adapter."""

    def test_www_host_maps_to_hrewheels(self) -> None:
        assert adapter_name_for_product_url(PRODUCT_URL) == "hrewheels"

    def test_bare_host_maps_to_hrewheels(self) -> None:
        assert adapter_name_for_product_url("https://hrewheels.com/wheels/series-p1/p101") == "hrewheels"

    def test_unrelated_host_does_not_map(self) -> None:
        assert adapter_name_for_product_url("https://example.com/wheels/series-p1/p101") != "hrewheels"


class TestProductUrlGuard:
    """
    Product URL shape is ``/wheels/<series>/<model>`` — exactly two
    segments after ``/wheels/``. Category roots and the grid index fall
    one segment short and must be rejected.
    """

    def test_product_url_valid(self) -> None:
        assert _is_product_url(PRODUCT_URL)
        assert _is_product_url(PRODUCT_URL + "/")

    def test_classic_series_url_valid(self) -> None:
        assert _is_product_url(CLASSIC_URL)

    def test_flowform_url_valid(self) -> None:
        assert _is_product_url("https://www.hrewheels.com/wheels/hre-flowform/ff15")

    def test_wheels_root_rejected(self) -> None:
        assert not _is_product_url("https://www.hrewheels.com/wheels")
        assert not _is_product_url("https://www.hrewheels.com/wheels/")

    def test_wheels_grid_rejected(self) -> None:
        # `/wheels/grid` is the grid index, not a product.
        assert not _is_product_url("https://www.hrewheels.com/wheels/grid")

    def test_series_only_rejected(self) -> None:
        # Series-landing pages would have one segment after /wheels/.
        assert not _is_product_url("https://www.hrewheels.com/wheels/series-p1")

    def test_non_wheels_path_rejected(self) -> None:
        # CMS pages in the sitemap (gallery, news, corporate, …) must not
        # be parsed as products during archive rescrape.
        assert not _is_product_url("https://www.hrewheels.com/gallery")
        assert not _is_product_url("https://www.hrewheels.com/corporate/company")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/wheels/series-p1/p101")


class TestCanonicalizeSitemapUrl:
    """
    Sitemap loc values use ``http://`` + ``www`` even though the origin
    301s to https. Normalize up-front so the fetcher doesn't eat a redirect
    per URL.
    """

    def test_upgrades_http_to_https(self) -> None:
        canonical = _canonicalize_sitemap_url("http://www.hrewheels.com/wheels/series-p1/p101")
        assert canonical == "https://www.hrewheels.com/wheels/series-p1/p101"

    def test_preserves_path(self) -> None:
        canonical = _canonicalize_sitemap_url("http://www.hrewheels.com/wheels/classic-series/305m")
        assert canonical.endswith("/wheels/classic-series/305m")


class TestParseProductPage:
    """Parse a product page into the expected ScrapedPayload fields."""

    def test_full_payload(self) -> None:
        result = HREWheelsAdapter().parse_product_page(_product_html(), PRODUCT_URL)
        assert result is not None
        # og:title ("Series P1 - P101") beats the bare h1 because it
        # disambiguates the model across series in the global catalog.
        assert result.name == "Series P1 - P101"
        assert result.part_manufacturer == "HRE"
        assert result.part_number is None
        # Catalog-only retailer: even when the page shows "Starting at $3,350",
        # price must be None.
        assert result.price_cents is None
        assert result.product_url == PRODUCT_URL

    def test_price_is_none_even_with_starting_at(self) -> None:
        # Defensive: HRE pages advertise a "Starting at $X USD each" series
        # price, but per the catalog-only policy the adapter must not extract it.
        html = _product_html(display_price="Starting at $9,950 USD each")
        result = HREWheelsAdapter().parse_product_page(html, PRODUCT_URL)
        assert result is not None
        assert result.price_cents is None

    def test_brand_is_always_hre(self) -> None:
        # HRE only sells HRE — brand is a site-level constant, never a
        # per-product guess.
        result = HREWheelsAdapter().parse_product_page(_product_html(), CLASSIC_URL)
        assert result is not None
        assert result.part_manufacturer == "HRE"

    def test_description_joins_prose_paragraphs(self) -> None:
        result = HREWheelsAdapter().parse_product_page(_product_html(), PRODUCT_URL)
        assert result is not None
        assert result.description is not None
        assert "best-selling series of forged wheels" in result.description
        assert "perfect complement" in result.description

    def test_description_skips_affirm_promo(self) -> None:
        # The Affirm "As low as $X/mo ... Apply now" ``<p>`` is financing
        # chrome, not product copy — must not leak into the description.
        result = HREWheelsAdapter().parse_product_page(_product_html(include_affirm=True), PRODUCT_URL)
        assert result is not None
        assert result.description is not None
        assert "Apply now" not in result.description
        assert "$558/mo" not in result.description

    def test_description_skips_view_finishes_link(self) -> None:
        # The ``<p class="ViewFinishes">`` is a UI control, not copy.
        result = HREWheelsAdapter().parse_product_page(_product_html(), PRODUCT_URL)
        assert result is not None
        assert result.description is not None
        assert "View available finishes" not in result.description

    def test_images_prefer_original_resolution_gallery(self) -> None:
        result = HREWheelsAdapter().parse_product_page(_product_html(), PRODUCT_URL)
        assert result is not None
        assert result.image_urls is not None and len(result.image_urls) >= 2
        # Every gallery URL should be the full-resolution variant, not a
        # 160x155 og:image thumbnail or a 422x409 mid-size.
        for url in result.image_urls:
            assert url.startswith("https://s3.amazonaws.com/cdn.hrewheels.com/img/")
        assert any("wheel-original" in u for u in result.image_urls)

    def test_images_reject_non_cdn_chrome(self) -> None:
        # The WheelSpecifications block renders sponsor/theme logos from
        # ``/img/logo-Brembo.jpg`` — not a product image, must not leak in.
        result = HREWheelsAdapter().parse_product_page(_product_html(), PRODUCT_URL)
        assert result is not None
        assert result.image_urls is not None
        joined = " ".join(result.image_urls)
        assert "logo-Brembo" not in joined
        assert "/img/" not in joined or "cdn.hrewheels.com/img/" in joined

    def test_falls_back_to_hero_when_no_gallery(self) -> None:
        # Some models have no ``.WheelAltImages`` block — the hero image
        # from ``.MainImage`` must still produce at least one URL.
        result = HREWheelsAdapter().parse_product_page(_product_html(alt_data_large=()), PRODUCT_URL)
        assert result is not None
        assert result.image_urls is not None and len(result.image_urls) >= 1


class TestParseEdgeCases:
    """Guards for non-product URLs and malformed pages."""

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape guard: CMS paths must not be parsed as products
        # even when full product HTML is supplied by mistake.
        result = HREWheelsAdapter().parse_product_page(_product_html(), "https://www.hrewheels.com/gallery")
        assert result is None

    def test_wheels_root_returns_none(self) -> None:
        result = HREWheelsAdapter().parse_product_page(_product_html(), "https://www.hrewheels.com/wheels")
        assert result is None

    def test_missing_name_returns_none(self) -> None:
        html = "<html><body><p>Page not found</p></body></html>"
        assert HREWheelsAdapter().parse_product_page(html, PRODUCT_URL) is None


class TestAdapterFetcherTier:
    """HRE is plain nginx + PHP/Plesk — no Cloudflare, no TLS challenge."""

    def test_declares_http_tier(self) -> None:
        assert HREWheelsAdapter.FETCHER_TIER == "http"
