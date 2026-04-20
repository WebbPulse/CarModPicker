"""
Tests for performancebyie.com adapter: Shopify JSON-LD parsing with the
brand defaulting to "Integrated Engineering" and a DOM gallery sweep that
expands beyond the single hero image JSON-LD ships.
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
    sku: str = "IEEXCI7",
    brand: str = "Integrated Engineering",
    description: str = "Deep-growl valved catback for MK7 Golf R and 8V S3 with DroneTrap tech.",
    price: str = "2089.99",
    hero_image: str = "https://performancebyie.com/cdn/shop/files/IEEXCI7_04_1024x1024.jpg?v=1729101105",
    gallery_images: tuple[str, ...] = (
        "//performancebyie.com/cdn/shop/files/IEEXCI7_04.jpg?v=1729101105&width=1080",
        "//performancebyie.com/cdn/shop/files/IEEXCI7_02.jpg?v=1729101105&width=1080",
        "//performancebyie.com/cdn/shop/files/IEEXCI7_03.jpg?v=1729101105&width=1080",
    ),
) -> str:
    """
    Minimal page mirroring the JSON-LD + Shopify slideshow DOM that IE emits.
    Brand is a plain string (IE's actual shape), not a Brand object.
    """
    brand_field = f'"brand": "{brand}",' if brand else ""
    gallery_imgs = "\n".join(f'<img src="{u}" alt="iE Catback" srcset="{u} 1080w">' for u in gallery_images)
    return f"""
    <html><head>
      <meta property="og:image:secure_url" content="{hero_image}">
      <script type="application/ld+json">
      {{
        "@context": "http://schema.org",
        "@type": "Product",
        "name": "{name}",
        "sku": "{sku}",
        {brand_field}
        "description": "{description}",
        "image": {{
          "@type": "ImageObject",
          "url": "{hero_image}"
        }},
        "offers": [{{
          "@type": "Offer",
          "sku": "{sku}",
          "price": {price},
          "priceCurrency": "USD"
        }}]
      }}
      </script>
    </head><body>
      <div class="product-slideshow" data-product-photos>
        {gallery_imgs}
      </div>
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
    """End-to-end parsing against real-shape IE Shopify HTML."""

    def test_full_page_parses_house_brand(self) -> None:
        result = IEAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "iE Catback Exhaust System For VW MK7 Golf R & Audi 8V S3"
        assert result.part_manufacturer == "Integrated Engineering"
        assert result.part_number == "IEEXCI7"
        assert result.price_cents == 208999
        assert result.description == "Deep-growl valved catback for MK7 Golf R and 8V S3 with DroneTrap tech."

    def test_dom_gallery_expands_beyond_json_ld_hero(self) -> None:
        # JSON-LD ships only the single hero ImageObject. The DOM slideshow
        # has three distinct files — the canonical form (width stripped)
        # should produce three URLs, with the og:image dedupe'd against file 04.
        result = IEAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        # hero og:image resolves to IEEXCI7_04_1024x1024.jpg, slideshow emits
        # IEEXCI7_04.jpg, _02.jpg, _03.jpg — distinct paths, so 4 unique.
        paths = [u.split("?")[0] for u in result.image_urls]
        assert "https://performancebyie.com/cdn/shop/files/IEEXCI7_04.jpg" in paths
        assert "https://performancebyie.com/cdn/shop/files/IEEXCI7_02.jpg" in paths
        assert "https://performancebyie.com/cdn/shop/files/IEEXCI7_03.jpg" in paths
        # width=1080 should be stripped on slideshow URLs.
        assert all("width=" not in u for u in result.image_urls)

    def test_missing_brand_falls_back_to_ie(self) -> None:
        # Defensive: if IE ever ships a product without a brand field, don't
        # leak a blank manufacturer to ingest. Default to the house brand.
        html = _product_page_html(brand="")
        result = IEAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == IE_BRAND

    def test_missing_json_ld_returns_none(self) -> None:
        # Soft-404 / non-product pages have no Product JSON-LD; skip them so
        # the runner doesn't ingest a blank row.
        html = "<html><head><title>Page Not Found</title></head><body></body></html>"
        assert IEAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_html_entity_in_name_decoded(self) -> None:
        # IE emits "\u0026" in JSON-LD — ``scraped_payload_from_json_ld``
        # decodes it, so "Golf R \u0026 Audi" becomes "Golf R & Audi".
        html = _product_page_html(name="iE Catback Exhaust System For VW MK7 Golf R \\u0026 Audi 8V S3")
        result = IEAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert "&" in result.name
