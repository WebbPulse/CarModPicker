"""
Tests for the rewritten fortune-auto.com adapter. Fortune Auto retired the
``fortuneauto-na.com`` Shopify storefront and replaced it with a WordPress
marketing catalog at ``fortune-auto.com``. The current adapter walks
``/coilovers/<series>/`` pages and reads name/description/image from
OpenGraph/Yoast meta rather than Shopify JSON-LD.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier1_tls.fortuneauto import (
    FORTUNEAUTO_BRAND,
    FortuneAutoAdapter,
    _is_product_url,
    _strip_brand_suffix,
)

SAMPLE_URL = "https://fortune-auto.com/coilovers/500series/"


def _product_page_html(
    *,
    og_title: str = "500 Series Generation 8 - Fortune Auto",
    og_description: str = (
        "Performance Coilovers ideal for the track and occasional street use. "
        "Higher Performance by design. Fortune Auto Coilovers"
    ),
    og_image: str = "https://fortune-auto.com/wp-content/uploads/2023/01/500-Mobile-copy.jpg",
    meta_description: str = "",
    title: str = "Fortune Auto 500 Series Coilovers – Fortune Auto",
    include_og_title: bool = True,
    include_og_image: bool = True,
) -> str:
    """Minimal Yoast/WordPress-shape page (no JSON-LD Product block)."""
    og_title_tag = f'<meta property="og:title" content="{og_title}"/>' if include_og_title else ""
    og_image_tag = f'<meta property="og:image" content="{og_image}"/>' if include_og_image else ""
    meta_desc_tag = f'<meta name="description" content="{meta_description}"/>' if meta_description else ""
    return f"""
    <html><head>
      <title>{title}</title>
      {og_title_tag}
      <meta property="og:description" content="{og_description}"/>
      {og_image_tag}
      {meta_desc_tag}
    </head><body>
      <h1>Fortune Auto 500 Series</h1>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so both the current and legacy domain reach this adapter."""

    def test_current_domain_routes_to_fortuneauto(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "fortuneauto"

    def test_legacy_shopify_domain_still_routes(self) -> None:
        # Archive replay: old ``fortuneauto-na.com`` URLs captured before the
        # migration must still find the Fortune Auto parser so historical HTML
        # in storage keeps parsing.
        legacy = "https://fortuneauto-na.com/products/500-series-coilovers-bmw-e46-m3"
        assert adapter_name_for_product_url(legacy) == "fortuneauto"

    def test_www_subdomain_routes(self) -> None:
        assert adapter_name_for_product_url("https://www.fortune-auto.com/coilovers/510series/") == "fortuneauto"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/coilovers/500series") == "generic"


class TestIsProductUrl:
    """Product URL shape is ``/coilovers/<series>/`` on fortune-auto.com only."""

    def test_series_path_accepted(self) -> None:
        assert _is_product_url("https://fortune-auto.com/coilovers/500series/")

    def test_series_path_without_trailing_slash_accepted(self) -> None:
        assert _is_product_url("https://fortune-auto.com/coilovers/520series")

    def test_www_host_accepted(self) -> None:
        assert _is_product_url("https://www.fortune-auto.com/coilovers/dreadnoughtpro2way/")

    def test_bare_coilovers_root_rejected(self) -> None:
        # The ``/coilovers/`` landing page is the collection root, not a series.
        assert not _is_product_url("https://fortune-auto.com/coilovers/")
        assert not _is_product_url("https://fortune-auto.com/coilovers")

    def test_deeper_path_rejected(self) -> None:
        # Only single-segment sub-paths are product pages; Yoast shouldn't
        # surface deeper ones but we guard against drift.
        assert not _is_product_url("https://fortune-auto.com/coilovers/500series/tech")

    def test_other_path_rejected(self) -> None:
        assert not _is_product_url("https://fortune-auto.com/about/")
        assert not _is_product_url("https://fortune-auto.com/events/")

    def test_unrelated_host_rejected(self) -> None:
        # Legacy Shopify URLs route correctly for replay, but the URL guard
        # itself keeps the adapter from parsing them as new-site products.
        assert not _is_product_url("https://fortuneauto-na.com/products/500-series-coilovers")
        assert not _is_product_url("https://example.com/coilovers/500series/")


class TestStripBrandSuffix:
    """Yoast appends a site-name suffix to ``<title>``; strip it before catalog entry."""

    def test_dash_suffix_stripped(self) -> None:
        assert _strip_brand_suffix("500 Series Generation 8 - Fortune Auto") == "500 Series Generation 8"

    def test_en_dash_suffix_stripped(self) -> None:
        # Yoast uses an en-dash (U+2013) by default.
        assert _strip_brand_suffix("Fortune Auto 500 Series Coilovers – Fortune Auto") == (
            "Fortune Auto 500 Series Coilovers"
        )

    def test_trailing_dash_without_suffix_cleaned(self) -> None:
        # og:title sometimes ships with a dangling " -" when the Yoast
        # suffix template resolves empty.
        assert _strip_brand_suffix("510 Series Generation 8 -") == "510 Series Generation 8"

    def test_no_suffix_preserved(self) -> None:
        assert _strip_brand_suffix("Muller MSC 1-Way") == "Muller MSC 1-Way"


class TestParseProductPage:
    """End-to-end parsing against a WordPress/Yoast-shape coilover series page."""

    def test_full_page_parses(self) -> None:
        result = FortuneAutoAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        # og:title ("500 Series Generation 8 - Fortune Auto") beats <title>
        # and the Yoast brand suffix is trimmed.
        assert result.name == "500 Series Generation 8"
        # Brand is the constant first-party vendor, never guessed.
        assert result.part_manufacturer == FORTUNEAUTO_BRAND
        # Per-fitment: a single series page covers thousands of SKUs.
        assert result.part_number is None
        # Catalog-only: Fortune Auto is quote-driven.
        assert result.price_cents is None
        assert result.product_url == SAMPLE_URL
        # og:image → single-hero gallery
        assert result.image_urls == ["https://fortune-auto.com/wp-content/uploads/2023/01/500-Mobile-copy.jpg"]

    def test_description_from_og(self) -> None:
        result = FortuneAutoAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.description is not None
        assert "Performance Coilovers" in result.description

    def test_description_falls_back_to_meta_description(self) -> None:
        # When og:description is empty but <meta name="description"> has copy,
        # the adapter should still surface a description.
        html = _product_page_html(og_description="", meta_description="Meta description fallback")
        result = FortuneAutoAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.description == "Meta description fallback"

    def test_title_fallback_when_og_title_missing(self) -> None:
        # Not all pages emit og:title; <title> + suffix-strip keeps them parseable.
        html = _product_page_html(include_og_title=False, title="Muller MSC 1-Way - Fortune Auto")
        result = FortuneAutoAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name == "Muller MSC 1-Way"

    def test_no_images_returns_none_for_image_field(self) -> None:
        # og:image is optional on the WordPress catalog; some pages ship
        # without one. Missing → ``image_urls=None`` rather than an empty list.
        html = _product_page_html(include_og_image=False)
        result = FortuneAutoAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls is None

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape guard: URL filter rejects before parsing so a
        # captured /events/ page can't be parsed as a coilover series.
        bad_url = "https://fortune-auto.com/events/"
        assert FortuneAutoAdapter().parse_product_page(_product_page_html(), bad_url) is None

    def test_page_without_name_returns_none(self) -> None:
        # Soft-404 / shell page with no og:title and no <title> — nothing to
        # build a payload from.
        html = "<html><head></head><body><h1>Fortune Auto</h1></body></html>"
        assert FortuneAutoAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """Fortune Auto sits behind Cloudflare; plain requests gets a 403 challenge."""

    def test_declares_tls_tier(self) -> None:
        assert FortuneAutoAdapter.FETCHER_TIER == "tls"
