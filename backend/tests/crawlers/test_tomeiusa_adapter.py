"""
Tests for products.tomeiusa.com adapter: PrestaShop tomei-child theme parsing
with no JSON-LD and no useful Open Graph price/description. Covers host
routing, the URL-pattern guards used by discovery, the spec-table
description builder, and end-to-end parsing of a shaped product page.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier1_tls.tomeiusa import (
    TomeiUsaAdapter,
    _build_description,
    _is_category_url,
    _is_product_url,
    _strip_query,
)

SAMPLE_URL = "https://products.tomeiusa.com/oil-pump/814-oversized-oil-pump-rb26dett-rb25det-rb20det"


def _product_page_html(
    *,
    h1: str = "OVERSIZED OIL PUMP RB26DETT/RB25DE(T)/RB20DE(T)",
    parts_no: str = "TB203A-NS05A",
    msrp: str = "$1,380.00",
    engine: str = "NISSAN RB26DETT, NISSAN RB25DE",
    model: str = "NISSAN 32 GT-R, NISSAN 33 GT-R",
    main_category: str = "OIL LUBRICATION",
    sub_category: str = "OIL PUMP",
    gallery: tuple[tuple[str, str], ...] = (
        (
            "https://products.tomeiusa.com/20039-medium_default/oil-pump.jpg",
            "https://products.tomeiusa.com/20039/oil-pump.jpg",
        ),
        (
            "https://products.tomeiusa.com/20040-medium_default/oil-pump.jpg",
            "https://products.tomeiusa.com/20040/oil-pump.jpg",
        ),
    ),
) -> str:
    """
    Minimal tomei-child theme product page. Only the DOM nodes the adapter
    reads are populated — the title h1, the spec table inside
    ``#single__body__main__meta__table``, and the image carousel ``<ul>`` with
    ``data-image-large-src`` thumbnails. A header logo is included to prove
    image extraction stays scoped to the gallery.
    """
    thumbs = "".join(
        (
            f'<li class="thumb-container">'
            f'<img class="thumb js-thumb" '
            f'data-image-medium-src="{med}" '
            f'data-image-large-src="{large}" '
            f'src="{med}"></li>'
        )
        for med, large in gallery
    )
    return f"""
    <html><head>
      <meta property="og:image" content="https://products.tomeiusa.com/og-fallback.jpg">
    </head><body>
      <header><img src="/img/tomei-logo.png" alt="Tomei"></header>
      <div class="product-cover">
        <img class="js-qv-product-cover" src="https://products.tomeiusa.com/cover.jpg">
      </div>
      <ul class="product-images js-qv-product-images">{thumbs}</ul>
      <h1 class="h1" itemprop="name">{h1}</h1>
      <div id="single__body__main__meta__table">
        <table class="table table-striped">
          <tbody>
            <tr><th>parts #</th><td>{parts_no}</td></tr>
            <tr><th>msrp</th><td>{msrp}</td></tr>
            <tr><th>engine</th><td>{engine}</td></tr>
            <tr><th>model</th><td>{model}</td></tr>
            <tr><th>main category</th><td>{main_category}</td></tr>
            <tr><th>sub category</th><td>{sub_category}</td></tr>
            <tr><th>shipping size</th><td>12 x 7 x 5 inch</td></tr>
            <tr><th>qty in stock</th><td>14</td></tr>
            <tr><th>note</th><td>In Stock Now!</td></tr>
          </tbody>
        </table>
      </div>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_products_subdomain_routes_to_tomeiusa(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "tomeiusa"

    def test_marketing_subdomain_routes_to_tomeiusa(self) -> None:
        # Catalog lives on products.tomeiusa.com but the marketing site
        # (www.tomeiusa.com) shares the same brand domain — both should
        # route to this adapter so a stray marketing URL still parses.
        assert adapter_name_for_product_url("https://www.tomeiusa.com/catalog/") == "tomeiusa"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/tomei") == "generic"


class TestUrlGuards:
    """Discovery follows category links from the homepage and product links from category pages."""

    def test_product_url_accepted(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_category_url_accepted(self) -> None:
        assert _is_category_url("https://products.tomeiusa.com/9-oil-lubrication")

    def test_category_url_rejects_product_path(self) -> None:
        # A product URL has the shape ``/<slug>/<id>-<slug>``; the category
        # regex must not accidentally match the second segment.
        assert not _is_category_url(SAMPLE_URL)

    def test_product_url_rejects_category_path(self) -> None:
        assert not _is_product_url("https://products.tomeiusa.com/9-oil-lubrication")

    def test_offsite_rejected(self) -> None:
        # Category pages link to the marketing subdomain (manuals, dealer
        # listings, etc.). Discovery must drop those even when the path
        # superficially matches the product pattern.
        assert not _is_product_url("https://www.tomeiusa.com/oil-pump/814-oversized-oil-pump-rb26dett-rb25det-rb20det")


class TestStripQuery:
    """``?q=`` filter params on category links collapse into the canonical URL."""

    def test_strips_query(self) -> None:
        assert (
            _strip_query("https://products.tomeiusa.com/10-intake?q=TYPE-WHOLE+UNIT")
            == "https://products.tomeiusa.com/10-intake"
        )

    def test_no_query_returns_input(self) -> None:
        assert _strip_query(SAMPLE_URL) == SAMPLE_URL


class TestBuildDescription:
    """Tomei ships almost no narrative copy — fitment rows are the description."""

    def test_full_spec_emits_titlecased_labels(self) -> None:
        result = _build_description(
            {
                "engine": "NISSAN RB26DETT",
                "model": "NISSAN 32 GT-R",
                "main category": "OIL LUBRICATION",
                "sub category": "OIL PUMP",
                # Excluded rows must not appear:
                "msrp": "$1,380.00",
                "qty in stock": "14",
            }
        )
        assert result is not None
        assert "Engine: NISSAN RB26DETT" in result
        assert "Model: NISSAN 32 GT-R" in result
        assert "Main Category: OIL LUBRICATION" in result
        assert "Sub Category: OIL PUMP" in result
        assert "1,380.00" not in result
        assert "qty" not in result.lower()

    def test_empty_spec_returns_none(self) -> None:
        assert _build_description({}) is None
        assert _build_description({"msrp": "$1.00"}) is None


class TestParseProductPage:
    """End-to-end parsing against a shaped tomei-child product page."""

    def test_full_page_parses(self) -> None:
        result = TomeiUsaAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "OVERSIZED OIL PUMP RB26DETT/RB25DE(T)/RB20DE(T)"
        assert result.part_manufacturer == "Tomei"
        assert result.part_number == "TB203A-NS05A"
        assert result.price_cents == 138000
        assert result.product_url == SAMPLE_URL
        assert result.description is not None
        assert "Engine: NISSAN RB26DETT" in result.description
        assert "Model: NISSAN 32 GT-R" in result.description
        assert result.image_urls is not None
        # Full-resolution gallery URL (data-image-large-src) wins over the
        # medium thumbnail and the header logo.
        assert result.image_urls[0] == "https://products.tomeiusa.com/20039/oil-pump.jpg"
        for img in result.image_urls:
            assert "tomei-logo" not in img

    def test_missing_spec_table_still_returns_payload(self) -> None:
        # Some product pages render the title without the spec table (very rare
        # — typically merch with no fitment data). Name + brand still get
        # ingested so the runner records the URL.
        html = '<html><body><h1 class="h1" itemprop="name">TOMEI BANNER</h1></body></html>'
        result = TomeiUsaAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name == "TOMEI BANNER"
        assert result.part_manufacturer == "Tomei"
        assert result.part_number is None
        assert result.price_cents is None
        assert result.description is None

    def test_query_string_stripped_from_stored_url(self) -> None:
        noisy = SAMPLE_URL + "?q=TYPE-WHOLE+UNIT"
        result = TomeiUsaAdapter().parse_product_page(_product_page_html(), noisy)
        assert result is not None
        assert result.product_url == SAMPLE_URL

    def test_og_image_fallback_when_carousel_missing(self) -> None:
        # Single-image products on PrestaShop often skip the carousel and
        # only emit the cover + og:image. The adapter must still surface an
        # image URL.
        html = """
        <html><head>
          <meta property="og:image" content="https://products.tomeiusa.com/og.jpg">
        </head><body>
          <h1 class="h1" itemprop="name">SOLO ITEM</h1>
        </body></html>
        """
        result = TomeiUsaAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls == ["https://products.tomeiusa.com/og.jpg"]

    def test_missing_h1_returns_none(self) -> None:
        # 404 served as 200 (PrestaShop returns the page-not-found template
        # for out-of-range pagination); skip so the runner doesn't ingest a
        # blank row.
        assert TomeiUsaAdapter().parse_product_page("<html><body></body></html>", SAMPLE_URL) is None
