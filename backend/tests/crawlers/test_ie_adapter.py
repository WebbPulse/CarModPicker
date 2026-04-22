"""
Tests for performancebyie.com adapter: current IE theme emits og:title /
og:description / og:image for name+description+hero, an inline
``data-pdp-variant-json`` array for sku + price (cents), and the Impulse
sidebar gallery for the rest of the images. Brand always defaults to the IE
house brand.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.ie import (
    IE_BRAND,
    IEAdapter,
    _canonical_image_url,
    _is_product_child_sitemap,
)

SAMPLE_URL = "https://performancebyie.com/products/ie-catback-exhaust-system-for-vw-mk7-golf-r-audi-8v-s3"


def _product_page_html(
    *,
    name: str = "iE Catback Exhaust System For VW MK7 Golf R & Audi 8V S3",
    sku: str | None = "IEEXCI7",
    description: str = "Deep-growl valved catback for MK7 Golf R and 8V S3 with DroneTrap tech.",
    price_cents: int | None = 208999,
    hero_image: str = "https://performancebyie.com/cdn/shop/files/IEEXCI7_04_1024x1024.jpg?v=1729101105",
    gallery_images: tuple[str, ...] = (
        "//performancebyie.com/cdn/shop/files/IEEXCI7_04.jpg?v=1729101105&width=1800",
        "//performancebyie.com/cdn/shop/files/IEEXCI7_02.jpg?v=1729101105&width=1800",
        "//performancebyie.com/cdn/shop/files/IEEXCI7_03.jpg?v=1729101105&width=1800",
    ),
) -> str:
    """
    Minimal page mirroring the current Impulse theme: OG meta + inline
    variant JSON + ``.sidebar-item[data-type="image"]`` gallery.
    """
    sku_json = f'"{sku}"' if sku is not None else "null"
    price_json = str(price_cents) if price_cents is not None else "null"
    gallery_items = "\n".join(
        f'<div class="sidebar-item" data-type="image" data-src="{u}">'
        f'<img src="{u.replace("width=1800", "width=220")}" class="thumbnail" /></div>'
        for u in gallery_images
    )
    return f"""
    <html><head>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{description}">
      <meta property="og:image:secure_url" content="{hero_image}">
      <meta name="description" content="{description}">
      <script type="application/json" data-pdp-variant-json>
      [{{"id": 1, "sku": {sku_json}, "price": {price_json}, "name": "{name}"}}]
      </script>
    </head><body>
      <section class="product-main" id="videos-photos">
        <div class="product-content">
          <div class="sidebar" id="sidebar">
            {gallery_items}
          </div>
        </div>
      </section>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_bare_host_routes_to_ie(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "ie"

    def test_www_subdomain_routes_to_ie(self) -> None:
        assert adapter_name_for_product_url("https://www.performancebyie.com/products/foo") == "ie"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/performancebyie") == "generic"


class TestIsProductChildSitemap:
    """Discovery only follows ``sitemap_products_N.xml`` children of the Shopify index."""

    def test_product_children_accepted(self) -> None:
        assert _is_product_child_sitemap("https://performancebyie.com/sitemap_products_1.xml?from=1&to=9")
        assert _is_product_child_sitemap("https://performancebyie.com/sitemap_products_42.xml")

    def test_non_product_children_rejected(self) -> None:
        for bad in (
            "https://performancebyie.com/sitemap_pages_1.xml",
            "https://performancebyie.com/sitemap_collections_1.xml",
            "https://performancebyie.com/sitemap_blogs_1.xml",
            "https://performancebyie.com/products/some-slug",
        ):
            assert not _is_product_child_sitemap(bad), bad


class TestCanonicalImageUrl:
    """Shopify CDN URLs only; responsive-srcset params collapse to one canonical form."""

    def test_protocol_relative_upgraded_to_https(self) -> None:
        url = _canonical_image_url("//performancebyie.com/cdn/shop/files/a.jpg?v=1")
        assert url == "https://performancebyie.com/cdn/shop/files/a.jpg?v=1"

    def test_width_param_stripped(self) -> None:
        url = _canonical_image_url("https://performancebyie.com/cdn/shop/files/a.jpg?v=1&width=720")
        assert url == "https://performancebyie.com/cdn/shop/files/a.jpg?v=1"

    def test_non_shopify_cdn_rejected(self) -> None:
        # Third-party tracking pixels / site chrome that isn't on the Shopify CDN.
        assert _canonical_image_url("https://example.com/img.jpg") is None

    def test_site_chrome_rejected(self) -> None:
        assert _canonical_image_url("https://performancebyie.com/cdn/shop/files/logo-nav.svg") is None


class TestParseProductPage:
    """End-to-end parsing against real-shape current-theme IE HTML."""

    def test_full_page_parses_house_brand(self) -> None:
        result = IEAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "iE Catback Exhaust System For VW MK7 Golf R & Audi 8V S3"
        assert result.part_manufacturer == IE_BRAND
        assert result.part_number == "IEEXCI7"
        assert result.price_cents == 208999
        assert result.description == "Deep-growl valved catback for MK7 Golf R and 8V S3 with DroneTrap tech."

    def test_dom_gallery_expands_beyond_hero(self) -> None:
        # og:image resolves to IEEXCI7_04_1024x1024.jpg; the sidebar emits
        # IEEXCI7_04.jpg, _02.jpg, _03.jpg as distinct files, so 4 unique
        # URLs end up in image_urls (hero + 3 gallery).
        result = IEAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        paths = [u.split("?")[0] for u in result.image_urls]
        assert "https://performancebyie.com/cdn/shop/files/IEEXCI7_04.jpg" in paths
        assert "https://performancebyie.com/cdn/shop/files/IEEXCI7_02.jpg" in paths
        assert "https://performancebyie.com/cdn/shop/files/IEEXCI7_03.jpg" in paths
        # width=1800 / width=220 should be stripped on sidebar URLs.
        assert all("width=" not in u for u in result.image_urls)

    def test_brand_always_defaults_to_ie(self) -> None:
        # Every product on performancebyie.com is IE's own line; titles lead
        # with the chassis ("iE Catback ... VW MK7 Golf R"), which a generic
        # heuristic would misread. We always stamp the house brand.
        result = IEAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == IE_BRAND

    def test_missing_product_markers_returns_none(self) -> None:
        # Soft-404 / non-product pages have no og:title and no h1; skip them
        # so the runner doesn't ingest a blank row.
        html = "<html><head><title>Page Not Found</title></head><body></body></html>"
        assert IEAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_variant_json_missing_still_yields_payload(self) -> None:
        # A product page without the inline variant JSON still has og:title,
        # so we return the payload with a null SKU / price rather than None.
        html = _product_page_html(sku=None, price_cents=None)
        result = IEAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("iE Catback")
        assert result.part_number is None
        assert result.price_cents is None

    def test_html_entity_in_name_decoded(self) -> None:
        # og:title content carries HTML-escaped ampersands ("Golf R &amp; Audi");
        # BeautifulSoup decodes the entity when we read ``.get("content")``.
        html = _product_page_html(name="iE Catback Exhaust System For VW MK7 Golf R &amp; Audi 8V S3")
        result = IEAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert "&" in result.name
