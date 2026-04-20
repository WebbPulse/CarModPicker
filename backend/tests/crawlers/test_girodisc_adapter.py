"""
Tests for girodisc.com adapter: BigCommerce Stencil DOM parsing (no JSON-LD
on this storefront) with the first-party brand hardcoded to "Girodisc".

Covers host routing, the ``/xmlsitemap.php?type=products`` child-sitemap
filter, the root-slug ``_is_product_url`` guard (so category pages like
``/front-rotors/`` don't get parsed as products), and end-to-end parsing
of the ``productView-*`` / ``[itemprop]`` DOM hooks.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.girodisc import (
    GIRODISC_BRAND,
    GirodiscAdapter,
    _is_product_child_sitemap,
    _is_product_url,
)

SAMPLE_URL = "https://girodisc.com/corvette-c8-z06-front-rotors/"


def _product_page_html(
    *,
    name: str = "Corvette C8 Z06 Front Rotors",
    sku: str = "A1-319",
    description_html: str = (
        "<p>These GiroDisc 2-piece rotors are a direct replacement for the"
        " front rotors on the Corvette C8 Z06 <strong>without the Z07"
        " carbon ceramic brakes</strong>.</p>"
    ),
    price_display: str = "$1,550.00",
    price_meta: str = "1550",
    zoom_image_url: str = (
        "https://cdn11.bigcommerce.com/s-a06wg97csf/images/stencil/"
        "1280x1280/products/3769/2622/408mm72v_0020.jpg?c=1"
    ),
    og_image_url: str = (
        "https://cdn11.bigcommerce.com/s-a06wg97csf/products/3769/" "images/2622/408mm72v_0020.386.513.jpg?c=1"
    ),
    og_type: str = "product",
    include_productview: bool = True,
) -> str:
    """
    Minimal page that mirrors the BigCommerce Stencil shape Girodisc emits.
    Only the hooks our adapter reads are populated; the description accordion
    and related-products grid (with its own ``$...`` prices) are included so
    price extraction proves it's scoped and doesn't leak to body-text fallback.
    """
    productview = (
        f"""
        <section class="productView-images" data-image-gallery>
            <figure class="productView-image"
                    data-image-gallery-main
                    data-zoom-image="{zoom_image_url}">
                <img src="{zoom_image_url}" alt="{name}" />
            </figure>
            <ul class="productView-thumbnails">
                <li class="productView-thumbnail">
                    <a data-image-gallery-zoom-image-url="{zoom_image_url}"></a>
                </li>
            </ul>
        </section>
        <section class="productView-details product-data">
            <h1 class="productView-title main-heading" itemprop="name">{name}</h1>
            <div class="productSKU">
                <dt>SKU:</dt>
                <dd data-product-sku itemprop="sku">{sku}</dd>
            </div>
            <div class="productView-price">
                <div itemprop="offers">
                    <span data-product-price-without-tax class="price">{price_display}</span>
                </div>
            </div>
        </section>
        <div id="accordion--description">
            <div itemprop="description">{description_html}</div>
        </div>
        <ul class="productGrid">
            <!-- Related products; their $-prices must NOT be picked up as the main price. -->
            <li class="product">
                <span data-product-price-without-tax class="price">$9,999.00</span>
            </li>
        </ul>
        """
        if include_productview
        else ""
    )
    og_type_tag = f'<meta property="og:type" content="{og_type}" />' if og_type else ""
    return f"""
    <html><head>
      <title>{name} - {sku} - GiroDisc</title>
      {og_type_tag}
      <meta property="og:title" content="{name}" />
      <meta property="og:description" content="We design, manufacture, and sell 2-piece, fully-floating brake rotors for Porsche, BMW, Subaru, and more." />
      <meta property="og:image" content="{og_image_url}" />
      <meta property="product:price:amount" content="{price_meta}" />
      <meta property="product:price:currency" content="USD" />
    </head><body>
      {productview}
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_bare_host_routes_to_girodisc(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "girodisc"

    def test_www_host_routes_to_girodisc(self) -> None:
        assert adapter_name_for_product_url("https://www.girodisc.com/audi-tt-rs-8s-front-rotors/") == "girodisc"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/girodisc") == "generic"


class TestIsProductUrl:
    """Root-slug filter so category pages like ``/front-rotors/`` never get parsed as products."""

    def test_root_slug_accepted(self) -> None:
        assert _is_product_url("https://girodisc.com/corvette-c8-z06-front-rotors/")

    def test_www_host_accepted(self) -> None:
        assert _is_product_url("https://www.girodisc.com/lotus-emira-front-rotors/")

    def test_category_slug_rejected(self) -> None:
        # Category grids use the same root-slug shape — reject by explicit list.
        for bad in (
            "https://girodisc.com/front-rotors/",
            "https://girodisc.com/rear-rotors/",
            "https://girodisc.com/brake-pads/",
            "https://girodisc.com/big-brake-kit-parts/",
            "https://girodisc.com/technical-info/",
            "https://girodisc.com/about-us/",
        ):
            assert not _is_product_url(bad), bad

    def test_php_endpoints_rejected(self) -> None:
        # Cart/checkout/login must never be mistaken for product slugs.
        for bad in (
            "https://girodisc.com/cart.php",
            "https://girodisc.com/checkout.php",
            "https://girodisc.com/search.php?search_query=rotor",
        ):
            assert not _is_product_url(bad), bad

    def test_empty_path_rejected(self) -> None:
        assert not _is_product_url("https://girodisc.com/")

    def test_unrelated_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/corvette-c8-z06-front-rotors/")


class TestIsProductChildSitemap:
    """Discovery only follows ``?type=products`` children of the sitemap index."""

    def test_products_child_accepted(self) -> None:
        assert _is_product_child_sitemap("https://girodisc.com/xmlsitemap.php?type=products&page=1")
        assert _is_product_child_sitemap("https://girodisc.com/xmlsitemap.php?type=products&page=5")

    def test_pages_and_categories_rejected(self) -> None:
        for bad in (
            "https://girodisc.com/xmlsitemap.php?type=pages&page=1",
            "https://girodisc.com/xmlsitemap.php?type=categories&page=1",
            "https://girodisc.com/xmlsitemap.php",
            "https://girodisc.com/sitemap.xml",
        ):
            assert not _is_product_child_sitemap(bad), bad


class TestParseProductPage:
    """End-to-end parsing against real-shape Girodisc BigCommerce HTML."""

    def test_full_page_parses(self) -> None:
        result = GirodiscAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "Corvette C8 Z06 Front Rotors"
        assert result.part_manufacturer == GIRODISC_BRAND
        assert result.part_number == "A1-319"
        # $1,550.00 — taken from the DOM span, not the related-products grid.
        assert result.price_cents == 155000
        assert result.description is not None
        assert result.description.startswith("These GiroDisc 2-piece rotors")
        # Description strips <strong> tags to plain text.
        assert "<strong>" not in result.description
        assert result.image_urls == [
            "https://cdn11.bigcommerce.com/s-a06wg97csf/images/stencil/"
            "1280x1280/products/3769/2622/408mm72v_0020.jpg?c=1"
        ]

    def test_price_falls_back_to_og_meta(self) -> None:
        # Rare theme variant without the DOM span — recover price from the
        # ``product:price:amount`` OG tag (BigCommerce emits whole-dollar values).
        html = _product_page_html(price_display="").replace(
            'data-product-price-without-tax class="price">',
            'data-product-price-absent="true">',
        )
        result = GirodiscAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.price_cents == 155000

    def test_description_prefers_itemprop_over_og(self) -> None:
        # og:description is a site-wide default; the itemprop block is the real
        # per-product copy. Prove itemprop wins even when both are present.
        html = _product_page_html(description_html="<p>Unique per-product copy for this SKU.</p>")
        result = GirodiscAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.description == "Unique per-product copy for this SKU."

    def test_non_bigcommerce_image_host_rejected(self) -> None:
        # Theme chrome (loading.svg) or off-site assets must not make it into
        # the gallery — filter is CDN-host + path-prefix scoped.
        html = _product_page_html(
            zoom_image_url="https://example.com/hotlinked.jpg",
            og_image_url="https://example.com/hotlinked-og.jpg",
        )
        result = GirodiscAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls is None

    def test_category_page_without_og_type_returns_none(self) -> None:
        # Category grid — no ``og:type=product`` and no ``[data-product-sku]``.
        html = """
        <html><head>
          <title>Front Rotors - GiroDisc</title>
          <meta property="og:type" content="website" />
        </head><body>
          <h1>Front Rotors</h1>
          <ul class="productGrid"></ul>
        </body></html>
        """
        assert GirodiscAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_missing_productview_with_og_product_returns_none(self) -> None:
        # og:type=product present but no DOM name extractable — don't fabricate.
        html = _product_page_html(include_productview=False).replace(
            '<meta property="og:title" content="Corvette C8 Z06 Front Rotors" />',
            "",
        )
        assert GirodiscAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_page_without_product_markers_returns_none(self) -> None:
        # No og:type=product and no [data-product-sku] — not a product page.
        html = "<html><head><title>404</title></head><body></body></html>"
        assert GirodiscAdapter().parse_product_page(html, SAMPLE_URL) is None
