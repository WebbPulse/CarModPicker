"""
Tests for kwsuspensions.com adapter: URL shape guard, registration, fetcher
tier, pagination walk, and DOM parsing for the legacy Magento storefront.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier1_tls.kwsuspensions import (
    KW_BRAND,
    KWSuspensionsAdapter,
    _extract_product_links,
    _has_next_page,
    _is_product_url,
)

SAMPLE_URL = "https://www.kwsuspensions.com/products/kw-suspensions-kw-v1-coilover-kit-10210005.html"


def _product_html(
    *,
    name: str = "KW COILOVER KIT V1",
    part_no: str = "10210005",
    price_text: str = "$1,479.00",
    include_price: bool = True,
    description_inner: str = (
        "<b>KW V1</b>: Sporty - Balanced. With KW factory pre-set damping."
        "<br><b>Fits:</b><br><b>1998-2010 Volkswagen New Beetle</b>"
    ),
    upc: str = "842607000140",
    include_upc: bool = True,
    image_sku: str = "10210005",
    image_indices: tuple[str, ...] = ("001", "002", "003", "004"),
) -> str:
    """Synthesize a KW product page that mirrors the real Magento theme.

    The real page has no JSON-LD / microdata / OG — only the DOM containers
    the theme renders. The fixture reproduces exactly those containers:
    ``.product-name h3``, ``.kw-prod-view-part-no``, ``.map-price .price``,
    ``.kw-decription-text``, ``.kw-metrics-table``, and the dual-rendered
    gallery image (256x thumbnail + 1920x lightbox, same filename).
    """
    price_block = (
        f'<span style="display:block;clear:left;" class="map-price" id="map-product-price-27044">'
        f'Your Price: <span class="price">{price_text}</span></span>'
        if include_price
        else ""
    )
    # Each image in the real theme appears twice — once in the 256x thumbnail
    # strip and once in the 1920x lightbox modal. We should dedupe by filename
    # and keep the 1920x variant.
    image_rows = "".join(
        f'<div class="image"><img class="img-list-miniature" '
        f'src="https://www.kwsuspensions.com/media/catalog/product/cache/4/image/256x/'
        f'040ec09b1e35df139433887a97daa66f/k/w/kw_{image_sku}_{idx}_1600_9.jpg" /></div>'
        f'<img src="https://www.kwsuspensions.com/media/catalog/product/cache/4/image/1920x/'
        f'040ec09b1e35df139433887a97daa66f/k/w/kw_{image_sku}_{idx}_1600_9.jpg" />'
        for idx in image_indices
    )
    upc_row = f'<tr class="last"><td>UPC Code: </td><td>{upc}</td></tr>' if include_upc else ""
    return f"""
    <html><head>
      <title>KW Suspensions</title>
      <meta name="description" content="Marketing meta blurb, should lose to the full description." />
    </head><body>
      <div class="product-view">
        <div class="row">
          <div class="large-12 columns product-name"><h3>{name}</h3></div>
        </div>
        <div class="product-shop">
          <div class="kw-prod-view-part-no">Part #: {part_no}</div>
          <div class="kw-prod-view-uom">UOM: Kit</div>
          <div class="price-box">{price_block}</div>
          <div class="slider-for-detailpage">{image_rows}</div>
        </div>
        <div class="tabs-content">
          <div class="content active" id="kw_tab_description">
            <div class="prod_description">
              <div class="kw-decription-text">{description_inner}</div>
            </div>
          </div>
          <div class="content" id="kw_tab_metrics">
            <table class="kw-metrics-table">
              <tr class="first"><td>Weight: </td><td>44.10 lbs</td></tr>
              <tr><td>Length: </td><td>30.00"</td></tr>
              {upc_row}
            </table>
          </div>
        </div>
      </div>
    </body></html>
    """


def _listing_html(*, product_slugs: list[str], include_next: bool = True) -> str:
    """Minimal ``/products.html?p=N`` fixture: product cards + pagination arrow."""
    cards = "".join(
        f'<li class="item"><a href="https://www.kwsuspensions.com/products/{slug}.html">'
        f'<img src="//example.com/thumb.jpg"></a></li>'
        for slug in product_slugs
    )
    next_arrow = (
        '<li><a class="arrow next i-next" href="https://www.kwsuspensions.com/products.html?p=2"'
        ' title="Next">&raquo;</a></li>'
        if include_next
        else ""
    )
    return f"""
    <html><body>
      <ul class="products-grid">{cards}</ul>
      <div class="pages"><ul class="pagination">
        <li class="current"><button>1</button></li>
        {next_arrow}
      </ul></div>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing: every kwsuspensions.com page hits the KW adapter."""

    def test_www_host_maps_to_kw(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "kwsuspensions"

    def test_bare_host_also_maps(self) -> None:
        assert (
            adapter_name_for_product_url(
                "https://kwsuspensions.com/products/kw-suspensions-kw-v3-coilover-kit-35220091.html"
            )
            == "kwsuspensions"
        )

    def test_unrelated_host_falls_back(self) -> None:
        assert adapter_name_for_product_url("https://example.com/products/foo.html") == "generic"


class TestProductUrlShape:
    """``/products/<slug>.html`` is the SKU page; ``/products.html`` is the catalog
    and anything deeper (``/products/coilovers/clubsport``) is category chrome."""

    def test_canonical_product_accepted(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_bundle_suffix_accepted(self) -> None:
        assert _is_product_url(
            "https://www.kwsuspensions.com/products/kw-suspensions-kw-v1-coilover-kit-bundle-1021000t.html"
        )

    def test_catalog_listing_rejected(self) -> None:
        assert not _is_product_url("https://www.kwsuspensions.com/products.html")

    def test_paginated_listing_rejected(self) -> None:
        # ?p=N query identifies the catalog listing, not a SKU page, even though
        # the base path of /products.html would otherwise fail the slug regex.
        assert not _is_product_url("https://www.kwsuspensions.com/products.html?p=5")

    def test_category_nested_path_rejected(self) -> None:
        # Product URLs are flat (/products/<slug>.html); nested paths like
        # /products/coilovers/v1 are marketing category pages.
        assert not _is_product_url("https://www.kwsuspensions.com/products/coilovers/clubsport")
        assert not _is_product_url("https://www.kwsuspensions.com/products/competition")

    def test_off_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/products/foo.html")

    def test_missing_html_suffix_rejected(self) -> None:
        # Marketing pages without the .html suffix are category URLs, not SKUs.
        assert not _is_product_url("https://www.kwsuspensions.com/products/kw-suspensions-kw-v1-coilover-kit")


class TestListingPagination:
    """Catalog walk stops when the ``i-next`` arrow disappears."""

    def test_next_arrow_detected_on_early_page(self) -> None:
        html = _listing_html(product_slugs=["foo-123", "bar-456"], include_next=True)
        assert _has_next_page(html)

    def test_last_page_has_no_next_arrow(self) -> None:
        html = _listing_html(product_slugs=["last-sku"], include_next=False)
        assert not _has_next_page(html)

    def test_product_links_extracted_in_order(self) -> None:
        html = _listing_html(
            product_slugs=[
                "kw-suspensions-kw-v1-coilover-kit-10210005",
                "kw-suspensions-kw-v3-coilover-kit-35220091",
            ],
            include_next=True,
        )
        urls = _extract_product_links(html)
        assert urls == [
            "https://www.kwsuspensions.com/products/kw-suspensions-kw-v1-coilover-kit-10210005.html",
            "https://www.kwsuspensions.com/products/kw-suspensions-kw-v3-coilover-kit-35220091.html",
        ]

    def test_category_and_pagination_links_filtered(self) -> None:
        # The listing HTML also contains nav links to category pages and the
        # "next" arrow's own /products.html href. None of those should show up
        # in the product URL list.
        html = _listing_html(product_slugs=["kw-suspensions-kw-v2-coilover-kit-15210001"], include_next=True)
        urls = _extract_product_links(html)
        assert urls == ["https://www.kwsuspensions.com/products/kw-suspensions-kw-v2-coilover-kit-15210001.html"]

    def test_duplicate_links_deduped(self) -> None:
        # Some SKUs appear in both the thumbnail and the title link on the same
        # card, so the same href is rendered twice per product. The discovery
        # helper must dedupe.
        html = _listing_html(
            product_slugs=["kw-suspensions-kw-v1-coilover-kit-10210005", "kw-suspensions-kw-v1-coilover-kit-10210005"],
            include_next=False,
        )
        assert len(_extract_product_links(html)) == 1


class TestParseProductPage:
    """End-to-end DOM parsing against a real-shape KW product fixture."""

    def test_full_page_parses(self) -> None:
        result = KWSuspensionsAdapter.__new__(KWSuspensionsAdapter).parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "KW COILOVER KIT V1"
        assert result.part_manufacturer == KW_BRAND
        assert result.part_number == "10210005"
        assert result.price_cents == 147900
        assert result.gtin == "842607000140"
        assert result.product_url == SAMPLE_URL
        assert result.description is not None
        assert "KW V1" in result.description
        assert "Fits" in result.description

    def test_gallery_dedupes_by_filename_keeping_large_variant(self) -> None:
        # Each gallery slot renders both 256x and 1920x URLs for the same file.
        # We must dedupe on filename and keep the larger variant so downstream
        # consumers get the high-res asset.
        result = KWSuspensionsAdapter.__new__(KWSuspensionsAdapter).parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        assert len(result.image_urls) == 4
        assert all("/1920x/" in u for u in result.image_urls)
        assert all("/256x/" not in u for u in result.image_urls)
        # Filenames preserved in listing order (001 → 004).
        assert result.image_urls[0].endswith("kw_10210005_001_1600_9.jpg")
        assert result.image_urls[-1].endswith("kw_10210005_004_1600_9.jpg")

    def test_missing_price_yields_none(self) -> None:
        # MAP-suppressed SKUs ("Please call for availability") render no price
        # block at all — we must not fabricate one.
        html = _product_html(include_price=False)
        result = KWSuspensionsAdapter.__new__(KWSuspensionsAdapter).parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.price_cents is None

    def test_missing_upc_yields_none_gtin(self) -> None:
        # Apparel / accessories ship without a UPC row. An empty GTIN must not
        # be passed through or the dedup lookup will collide on "".
        html = _product_html(include_upc=False)
        result = KWSuspensionsAdapter.__new__(KWSuspensionsAdapter).parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.gtin is None

    def test_brand_always_kw(self) -> None:
        # Every SKU on kwsuspensions.com is KW-made; the adapter hardcodes the
        # brand regardless of what the title looks like.
        result = KWSuspensionsAdapter.__new__(KWSuspensionsAdapter).parse_product_page(
            _product_html(name="KW HEIGHT ADJUSTABLE SPRING KIT", part_no="253100BJ"),
            SAMPLE_URL,
        )
        assert result is not None
        assert result.part_manufacturer == KW_BRAND

    def test_bundle_part_number_preserves_case(self) -> None:
        # Bundle SKUs use mixed-case suffixes (``1021000T``). The URL slug is
        # lowercase, but the DOM keeps the real case — we prefer the DOM value.
        html = _product_html(part_no="1021000T")
        result = KWSuspensionsAdapter.__new__(KWSuspensionsAdapter).parse_product_page(
            html,
            "https://www.kwsuspensions.com/products/kw-suspensions-kw-v1-coilover-kit-bundle-1021000t.html",
        )
        assert result is not None
        assert result.part_number == "1021000T"

    def test_non_product_url_returns_none(self) -> None:
        # Guard against the archive rescrape pipeline feeding a listing or
        # category page through this adapter.
        result = KWSuspensionsAdapter.__new__(KWSuspensionsAdapter).parse_product_page(
            _product_html(),
            "https://www.kwsuspensions.com/products.html",
        )
        assert result is None

    def test_missing_name_returns_none(self) -> None:
        # Soft-404 or out-of-catalog URLs render the storefront chrome without
        # a product-name block; parser must refuse rather than write a blank.
        html = """<html><body><div class="product-view">no name here</div></body></html>"""
        result = KWSuspensionsAdapter.__new__(KWSuspensionsAdapter).parse_product_page(html, SAMPLE_URL)
        assert result is None


class TestAdapterFetcherTier:
    """KW declares the TLS fetcher tier so the langselector cookie persists
    across the warm-up + per-URL fetches."""

    def test_declares_tls_tier(self) -> None:
        assert KWSuspensionsAdapter.FETCHER_TIER == "tls"
