"""
Tests for hondata.com adapter: OpenCart DOM parsing with no JSON-LD and no
Open Graph tags. Covers host routing, the ``Brand: Hondata, Inc.`` → ``Hondata``
normalization, ``Product Code:`` extraction, price extraction from the info
list, image filtering to ``/image/cache/catalog/`` URLs, and URL noise-param
stripping.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.hondata import (
    HondataAdapter,
    _is_product_url,
    _normalize_hondata_brand,
    _strip_noise_params,
)

SAMPLE_URL = "https://www.hondata.com/index.php?route=product/product&product_id=30"


def _product_page_html(
    *,
    h1: str = "Traction Control",
    brand: str = "Hondata, Inc.",
    product_code: str = "HON-TC-S300",
    availability: str = "In Stock",
    price: str = "$595.00",
    description: str = (
        "Traction Control for your s300, KPro or FlashPro. Uses ABS sensors to "
        "detect wheel slip and retard ignition to restore grip."
    ),
    gallery_paths: tuple[str, ...] = (
        "/image/cache/catalog/tractioncontrol/hero-800x800.jpg",
        "/image/cache/catalog/tractioncontrol/thumb-500x500.jpg",
    ),
    full_paths: tuple[str, ...] = ("/image/cache/catalog/tractioncontrol/hero-original.jpg",),
) -> str:
    """
    Minimal OpenCart default-theme product page. Only the DOM nodes the adapter
    reads are populated — h1, the Brand/Code/Availability info list, the price
    block, image links, and the description tab. A logo ``<img>`` and a
    site-chrome ``<a>`` are included to prove image filtering rejects them.
    """
    thumbs = "".join(f'<li><a href="#"><img src="{p}"></a></li>' for p in gallery_paths)
    full_links = "".join(f'<a href="{p}">full</a>' for p in full_paths)
    return f"""
    <html><head><title>{h1}</title></head><body>
      <header>
        <img src="/image/catalog/hondata-logo.png" alt="Hondata">
        <a href="/index.php?route=common/home">Home</a>
      </header>
      <div id="content">
        <h1>{h1}</h1>
        <ul class="list-unstyled">
          <li>Brand: <a href="#">{brand}</a></li>
          <li>Product Code: {product_code}</li>
          <li>Availability: {availability}</li>
        </ul>
        <ul class="list-unstyled">
          <li><h2>{price}</h2></li>
        </ul>
        <ul class="thumbnails">{thumbs}</ul>
        {full_links}
        <div id="tab-description"><p>{description}</p></div>
      </div>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_www_host_routes_to_hondata(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "hondata"

    def test_bare_host_routes_to_hondata(self) -> None:
        assert (
            adapter_name_for_product_url("https://hondata.com/index.php?route=product/product&product_id=30")
            == "hondata"
        )

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/hondata") == "generic"


class TestIsProductUrl:
    """Guard used by discovery so cross-host links in category pages aren't yielded."""

    def test_product_route_accepted(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_product_route_bare_host_accepted(self) -> None:
        assert _is_product_url("https://hondata.com/index.php?route=product/product&product_id=1")

    def test_category_route_rejected(self) -> None:
        assert not _is_product_url("https://www.hondata.com/index.php?route=product/category&path=65")

    def test_offsite_rejected(self) -> None:
        # A category page could link to an external partner; discovery must drop
        # those even when the route query-param happens to match.
        assert not _is_product_url("https://example.com/index.php?route=product/product&product_id=1")


class TestStripNoiseParams:
    """``language`` / ``path`` are pure navigation noise; ``route`` / ``product_id`` must survive."""

    def test_strips_language(self) -> None:
        cleaned = _strip_noise_params(
            "https://www.hondata.com/index.php?route=product/product&language=en-gb&product_id=30"
        )
        assert "language=" not in cleaned
        assert "product_id=30" in cleaned
        assert "route=product%2Fproduct" in cleaned or "route=product/product" in cleaned

    def test_strips_path(self) -> None:
        # ``path`` encodes the breadcrumb trail; ``product_id`` alone identifies
        # the product, so dropping ``path`` collapses duplicates discovered from
        # different categories into one canonical URL.
        cleaned = _strip_noise_params(
            "https://www.hondata.com/index.php?route=product/product&path=65_24&product_id=30"
        )
        assert "path=" not in cleaned
        assert "product_id=30" in cleaned

    def test_no_query_returns_input(self) -> None:
        assert _strip_noise_params("https://www.hondata.com/") == "https://www.hondata.com/"


class TestNormalizeBrand:
    """Brand row always reads ``Hondata, Inc.`` — collapse to ``Hondata``."""

    def test_full_legal_name_collapses(self) -> None:
        assert _normalize_hondata_brand("Hondata, Inc.") == "Hondata"

    def test_bare_name_collapses(self) -> None:
        assert _normalize_hondata_brand("Hondata") == "Hondata"

    def test_variant_spacing_collapses(self) -> None:
        assert _normalize_hondata_brand("Hondata Inc") == "Hondata"

    def test_unknown_brand_passes_through(self) -> None:
        # Unlikely on this storefront, but if a co-branded SKU ever surfaces
        # we must preserve the original label instead of stamping "Hondata".
        assert _normalize_hondata_brand("KTuner") == "KTuner"

    def test_empty_returns_none(self) -> None:
        assert _normalize_hondata_brand("") is None
        assert _normalize_hondata_brand(None) is None


class TestParseProductPage:
    """End-to-end parsing against a shaped OpenCart default-theme product page."""

    def test_full_page_parses(self) -> None:
        result = HondataAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "Traction Control"
        assert result.part_manufacturer == "Hondata"
        assert result.part_number == "HON-TC-S300"
        assert result.price_cents == 59500
        assert result.description is not None
        assert "Traction Control for your s300" in result.description
        assert result.image_urls is not None
        # Full-res lightbox link comes first; logo and the ``route=common/home``
        # link stay out (the former because it's not under /image/cache/catalog/,
        # the latter because it isn't an image link at all).
        assert result.image_urls[0] == ("https://www.hondata.com/image/cache/catalog/tractioncontrol/hero-original.jpg")
        for img in result.image_urls:
            assert "/image/cache/catalog/" in img
            assert "hondata-logo" not in img

    def test_missing_brand_defaults_to_hondata(self) -> None:
        # Degenerate case: a product page template variant drops the brand row.
        # We still stamp "Hondata" so cross-retailer dedupe keys match KTuner /
        # other adapters on the same manufacturer label.
        html = _product_page_html(brand="").replace('<li>Brand: <a href="#"></a></li>', "")
        result = HondataAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Hondata"

    def test_stored_url_strips_noise_params(self) -> None:
        noisy = "https://www.hondata.com/index.php?" "route=product/product&language=en-gb&path=65_24&product_id=30"
        result = HondataAdapter().parse_product_page(_product_page_html(), noisy)
        assert result is not None
        assert "language=" not in result.product_url
        assert "path=" not in result.product_url
        assert "product_id=30" in result.product_url

    def test_product_code_echoes_h1_is_rejected(self) -> None:
        # Real-corpus pattern: family-overview pages on this storefront
        # (``KPro``, ``CANBoost``, ``Injector Driver``, ``Traction Control``,
        # …) leave the OpenCart Product Code field unset and the template
        # falls back to echoing the H1. Trusting that echo collapses every
        # chassis-specific KPro/S300/etc. variant under one fake SKU. When
        # the Product Code matches the H1 verbatim, leave part_number unset.
        html = _product_page_html(h1="KPro", product_code="KPro")
        result = HondataAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name == "KPro"
        assert result.part_number is None

    def test_product_code_echoes_h1_case_and_whitespace_insensitive(self) -> None:
        # The fallback comparison must be tolerant of trailing whitespace and
        # capitalization drift between the template's two echo paths so a
        # ``Product Code:  s300 `` row doesn't slip past when ``<h1>S300</h1>``.
        html = _product_page_html(h1="S300", product_code="s300 ")
        result = HondataAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number is None

    def test_missing_h1_returns_none(self) -> None:
        # A category listing or account page rendered through the same template
        # has no ``<h1>`` — skip it so the runner doesn't ingest a blank row.
        html = (
            '<html><body><div id="content">'
            '<ul class="list-unstyled"><li>Brand: Hondata, Inc.</li></ul>'
            "</div></body></html>"
        )
        assert HondataAdapter().parse_product_page(html, SAMPLE_URL) is None
