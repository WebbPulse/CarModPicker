"""
Tests for goapr.com adapter: URL shape guard, registration, fetcher tier, and
parsing the ``product_data`` JSON blob that APR emits on every product page.
"""

import json

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier1_tls.apr import (
    _PRODUCT_SITEMAP_PATH_RE,
    APR_BRAND,
    APRAdapter,
    _is_product_url,
)

SAMPLE_URL = "https://www.goapr.com/products/exhaust_systems/catback_exhaust_systems/parts/CBK0052"


def _product_html(
    *,
    name: str = "APR Catback Exhaust System",
    partnumber: str = "CBK0052",
    mfg_partnumber: str = "",
    brand: str = "APR",
    description: str = (
        "Introducing the APR MK8 Golf R Catback Exhaust System—a masterpiece " "crafted by enthusiast engineers."
    ),
    upc: str = "810009935247",
    price: float = 1649.95,
    include_script: bool = True,
    images: list[dict] | None = None,
) -> str:
    """
    Synthesize an APR product page around the ``product_data`` JSON block. The
    real page is ~1.5 MB of storefront chrome; only the JSON blob matters for
    parsing, so the fixture mirrors exactly that.
    """
    if images is None:
        images = [
            {"type": "default", "filename": "0f25efea01c995dac29d1e6d8e0b8a9d52c3e151.jpg", "alt": None},
            {"type": "additional", "filename": "01746800b6393ee61196e196760df125ceaa51af.jpg", "alt": None},
            {"type": "additional", "filename": "16259c9e470e20eb47a8ffd99a7009e0f6e50e78.jpg", "alt": None},
            # Non-gallery type — swatch / install / promo art we should drop.
            {"type": "attribute", "filename": "swatch-red.jpg", "alt": None},
        ]
    payload: dict = {
        "name": name,
        "partnumber": partnumber,
        "mfg_partnumber": mfg_partnumber,
        "brand": brand,
        "description": description,
        "shortdescription": "Fits 2022-2025 Volkswagen Golf R MK8",
        "upc": upc,
        "price": price,
        "pricing": [
            {"type": "web", "startdate": "2026-01-01 00:00:00", "enddate": None, "price": price},
            {"type": "sr", "startdate": "2026-01-01 00:00:00", "enddate": None, "price": price + 207.0},
        ],
        "images": images,
    }
    blob = json.dumps(payload)
    script = f'<script nonce=abc123 type="application/json" id="product_data">{blob}</script>' if include_script else ""
    return f"""
    <html><head>
      <title>APR {partnumber} {name}</title>
      <meta property="og:description" content="{description}">
    </head><body>
      <div class="mainarea">
        {script}
        <h1>{name}</h1>
      </div>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing: every goapr.com page hits the APR adapter."""

    def test_www_host_maps_to_apr(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "apr"

    def test_bare_host_also_maps(self) -> None:
        assert adapter_name_for_product_url("https://goapr.com/products/software/parts/ECU-12T-EA211") == "apr"

    def test_unrelated_host_falls_back(self) -> None:
        assert adapter_name_for_product_url("https://example.com/products/foo/parts/X") == "generic"


class TestProductUrlShape:
    """
    The ``/parts/<id>`` suffix is what distinguishes a SKU page from the
    category / subcategory landing pages that share the ``/products/`` prefix
    and also appear in the sitemaps.
    """

    def test_catback_product_accepted(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_deeply_nested_software_product_accepted(self) -> None:
        assert _is_product_url(
            "https://www.goapr.com/products/software/ecu_upgrade/gasoline/4/12t_ea111_ea211/parts/ECU-12T-EA211"
        )

    def test_category_page_rejected(self) -> None:
        assert not _is_product_url("https://www.goapr.com/products/exhaust_systems/")
        assert not _is_product_url("https://www.goapr.com/products/software/ecu_upgrade/gasoline/")

    def test_query_string_rejected(self) -> None:
        assert not _is_product_url(SAMPLE_URL + "?utm_source=x")

    def test_off_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/products/foo/parts/BAR")

    def test_non_products_path_rejected(self) -> None:
        assert not _is_product_url("https://www.goapr.com/account/parts/CBK0052")


class TestSitemapFilter:
    """Discovery walks ``/sitemap/`` → ``/sitemap_products/*`` children only."""

    def test_product_sitemap_matched(self) -> None:
        assert _PRODUCT_SITEMAP_PATH_RE.search("https://www.goapr.com/sitemap_products/exhaust_systems/")
        assert _PRODUCT_SITEMAP_PATH_RE.search("https://www.goapr.com/sitemap_products/software/")

    def test_non_product_sitemaps_skipped(self) -> None:
        for u in (
            "https://www.goapr.com/sitemap_platforms/audi/",
            "https://www.goapr.com/sitemap_brands/",
            "https://www.goapr.com/sitemap_blog/",
            "https://www.goapr.com/sitemap_support/",
            "https://www.goapr.com/sitemap_other/",
        ):
            assert not _PRODUCT_SITEMAP_PATH_RE.search(u), u


class TestParseProductPage:
    """End-to-end parsing against real-shape APR ``product_data`` fixtures."""

    def test_full_page_parses_from_product_data(self) -> None:
        result = APRAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "APR Catback Exhaust System"
        assert result.part_manufacturer == "APR"
        # mfg_partnumber is empty on most APR SKUs; fall back to ``partnumber``.
        assert result.part_number == "CBK0052"
        assert result.price_cents == 164995
        assert result.gtin == "810009935247"
        assert result.product_url == SAMPLE_URL
        assert result.description is not None and "APR MK8 Golf R" in result.description

    def test_mfg_partnumber_preferred_when_present(self) -> None:
        # Co-branded / OEM-sourced SKUs reference an external manufacturer code
        # in ``mfg_partnumber``; that should win over APR's own ``partnumber``.
        result = APRAdapter().parse_product_page(
            _product_html(partnumber="CBK9999", mfg_partnumber="OEM-12345"),
            SAMPLE_URL,
        )
        assert result is not None
        assert result.part_number == "OEM-12345"

    def test_gallery_drops_non_product_image_types(self) -> None:
        # Only default / additional / lifestyle belong in the gallery. Swatches
        # and install diagrams must not leak into image_urls.
        result = APRAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        assert all(u.startswith("https://images.goapr.com/") for u in result.image_urls)
        assert not any("swatch-red" in u for u in result.image_urls)
        # Default image first, then two additionals, in JSON order.
        assert result.image_urls[0].endswith("0f25efea01c995dac29d1e6d8e0b8a9d52c3e151.jpg")
        assert len(result.image_urls) == 3

    def test_missing_brand_defaults_to_apr(self) -> None:
        # Defensive: APR emits ``"brand": "APR"`` on every page, but if the
        # field ever drops we should still assign the house brand rather than
        # leaking a blank manufacturer to ingest.
        result = APRAdapter().parse_product_page(_product_html(brand=""), SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == APR_BRAND

    def test_empty_upc_yields_none_gtin(self) -> None:
        # Software SKUs often ship without a UPC — empty strings must not be
        # passed through as GTIN or the dedup lookup will match on "".
        result = APRAdapter().parse_product_page(_product_html(upc=""), SAMPLE_URL)
        assert result is not None
        assert result.gtin is None

    def test_missing_product_data_returns_none(self) -> None:
        # No ``product_data`` blob — soft 404 / non-product page. Parser must
        # refuse ingestion so the runner doesn't write a blank row.
        html = _product_html(include_script=False)
        assert APRAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_non_product_url_returns_none(self) -> None:
        # Guard against the archive rescrape pipeline feeding a category page
        # through this adapter.
        result = APRAdapter().parse_product_page(
            _product_html(),
            "https://www.goapr.com/products/exhaust_systems/",
        )
        assert result is None

    def test_price_falls_back_to_web_pricing_when_price_field_missing(self) -> None:
        # If APR ever drops the top-level ``price`` field, the adapter should
        # fall back to the ``web`` entry in the ``pricing`` list (the current
        # retail price) rather than writing None.
        import re

        raw = _product_html()
        # Strip the top-level "price": 1649.95 entry. The "pricing" list still
        # carries the same web price, so price_cents should still resolve.
        stripped = re.sub(r'"price":\s*1649\.95,\s*"pricing"', '"pricing"', raw)
        result = APRAdapter().parse_product_page(stripped, SAMPLE_URL)
        assert result is not None
        assert result.price_cents == 164995


class TestAdapterFetcherTier:
    """APR declares the TLS fetcher tier — plain requests get a CF challenge."""

    def test_declares_tls_tier(self) -> None:
        assert APRAdapter.FETCHER_TIER == "tls"
