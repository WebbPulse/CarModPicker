"""
Tests for prlmotorsports.com adapter: Shopify JSON-LD parsing with the
house brand defaulting to "PRL Motorsports", the target-vehicle leak
(Honda/Acura) rewritten back to the house brand, and a DOM gallery sweep
that expands beyond the single hero image JSON-LD ships.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.prlmotorsports import (
    PRL_BRAND,
    PRLMotorsportsAdapter,
    _canonical_image_url,
    _is_product_child_sitemap,
    _normalize_part_manufacturer,
)

SAMPLE_URL = (
    "https://www.prlmotorsports.com/products/" "prl-motorsports-2023-honda-civic-type-r-fl5-hi-volume-intake-system"
)


def _product_page_html(
    *,
    name: str = "PRL Motorsports 2023+ Honda Civic Type R FL5 Hi-Volume Intake System",
    sku: str = "PRL-FL5-HVI-V1",
    brand: str = "PRL Motorsports",
    description: str = (
        "High-flow intake for the 2023+ FL5 Civic Type R. Retains factory "
        "resonator tuning and fits under the OEM engine cover."
    ),
    price: str = "649.99",
    hero_image: str = ("https://www.prlmotorsports.com/cdn/shop/files/FL5_HVI_hero_1024x1024.jpg?v=1712345678"),
    gallery_images: tuple[str, ...] = (
        "//www.prlmotorsports.com/cdn/shop/files/FL5_HVI_hero.jpg?v=1712345678&width=1080",
        "//www.prlmotorsports.com/cdn/shop/files/FL5_HVI_install.jpg?v=1712345678&width=1080",
        "//www.prlmotorsports.com/cdn/shop/files/FL5_HVI_dyno.jpg?v=1712345678&width=1080",
    ),
) -> str:
    """
    Minimal page mirroring the JSON-LD + Shopify slideshow DOM that PRL emits.
    Brand is a plain string (PRL's actual shape), not a Brand object.
    """
    brand_field = f'"brand": "{brand}",' if brand else ""
    gallery_imgs = "\n".join(f'<img src="{u}" alt="FL5 HVI" srcset="{u} 1080w">' for u in gallery_images)
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

    def test_bare_host_routes_to_prl(self) -> None:
        assert adapter_name_for_product_url("https://prlmotorsports.com/products/foo") == "prlmotorsports"

    def test_www_subdomain_routes_to_prl(self) -> None:
        assert adapter_name_for_product_url("https://www.prlmotorsports.com/products/foo") == "prlmotorsports"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/prlmotorsports") == "generic"


class TestIsProductChildSitemap:
    """Discovery only follows ``sitemap_products_N.xml`` children of the Shopify index."""

    def test_product_children_accepted(self) -> None:
        assert _is_product_child_sitemap("https://www.prlmotorsports.com/sitemap_products_1.xml?from=1&to=9")
        assert _is_product_child_sitemap("https://www.prlmotorsports.com/sitemap_products_42.xml")

    def test_non_product_children_rejected(self) -> None:
        for bad in (
            "https://www.prlmotorsports.com/sitemap_pages_1.xml",
            "https://www.prlmotorsports.com/sitemap_collections_1.xml",
            "https://www.prlmotorsports.com/sitemap_blogs_1.xml",
            "https://www.prlmotorsports.com/products/some-slug",
        ):
            assert not _is_product_child_sitemap(bad), bad


class TestNormalizePartManufacturer:
    """PRL's Shopify vendor field has several equivalent forms and sometimes
    leaks the target vehicle — collapse all variants without losing real
    third-party brands that PRL resells (Hondata FlashPro, KTuner, JB4)."""

    def test_empty_brand_defaults_to_prl(self) -> None:
        assert _normalize_part_manufacturer("") == PRL_BRAND
        assert _normalize_part_manufacturer(None) == PRL_BRAND
        assert _normalize_part_manufacturer("   ") == PRL_BRAND

    def test_prl_variants_collapse_to_canonical_label(self) -> None:
        for variant in ("PRL", "PRL Motorsports", "PRL Motorsports, Inc.", "prl motorsports"):
            assert _normalize_part_manufacturer(variant) == PRL_BRAND, variant

    def test_target_vehicle_brand_maps_to_prl(self) -> None:
        # Shopify vendor field occasionally gets left blank and a theme fallback
        # renders the target vehicle make ("Honda", "Acura") in the brand slot.
        assert _normalize_part_manufacturer("Honda") == PRL_BRAND
        assert _normalize_part_manufacturer("Acura") == PRL_BRAND
        assert _normalize_part_manufacturer("honda") == PRL_BRAND

    def test_third_party_brands_pass_through(self) -> None:
        # PRL stocks Hondata / KTuner / JB4 tunes as companion SKUs to their
        # intake/IC hardware — those must keep their own manufacturer identity
        # so cross-retailer dedupe against the first-party adapters works.
        assert _normalize_part_manufacturer("Hondata") == "Hondata"
        assert _normalize_part_manufacturer("KTuner") == "KTuner"
        assert _normalize_part_manufacturer("JB4") == "JB4"


class TestCanonicalImageUrl:
    """Shopify CDN URLs only; responsive-srcset params collapse to one canonical form."""

    def test_protocol_relative_upgraded_to_https(self) -> None:
        url = _canonical_image_url("//www.prlmotorsports.com/cdn/shop/files/a.jpg?v=1")
        assert url == "https://www.prlmotorsports.com/cdn/shop/files/a.jpg?v=1"

    def test_width_param_stripped(self) -> None:
        url = _canonical_image_url("https://www.prlmotorsports.com/cdn/shop/files/a.jpg?v=1&width=720")
        assert url == "https://www.prlmotorsports.com/cdn/shop/files/a.jpg?v=1"

    def test_non_shopify_cdn_rejected(self) -> None:
        # Third-party tracking pixels / site chrome that isn't on the Shopify CDN.
        assert _canonical_image_url("https://example.com/img.jpg") is None

    def test_site_chrome_rejected(self) -> None:
        assert _canonical_image_url("https://www.prlmotorsports.com/cdn/shop/files/logo-nav.svg") is None


class TestParseProductPage:
    """End-to-end parsing against real-shape PRL Shopify HTML."""

    def test_full_page_parses_house_brand(self) -> None:
        result = PRLMotorsportsAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("PRL Motorsports 2023+ Honda Civic Type R FL5")
        assert result.part_manufacturer == "PRL Motorsports"
        assert result.part_number == "PRL-FL5-HVI-V1"
        assert result.price_cents == 64999
        assert result.description is not None
        assert "FL5 Civic Type R" in result.description

    def test_dom_gallery_expands_beyond_json_ld_hero(self) -> None:
        # JSON-LD ships only the single hero ImageObject. The DOM slideshow
        # has three distinct files — the canonical form (width stripped)
        # should produce three URLs; the og:image variant dedupes against hero.
        result = PRLMotorsportsAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        paths = [u.split("?")[0] for u in result.image_urls]
        assert "https://www.prlmotorsports.com/cdn/shop/files/FL5_HVI_hero.jpg" in paths
        assert "https://www.prlmotorsports.com/cdn/shop/files/FL5_HVI_install.jpg" in paths
        assert "https://www.prlmotorsports.com/cdn/shop/files/FL5_HVI_dyno.jpg" in paths
        assert all("width=" not in u for u in result.image_urls)

    def test_missing_brand_falls_back_to_prl(self) -> None:
        # Defensive: if PRL ever ships a product without a brand field, don't
        # leak a blank manufacturer to ingest. Default to the house brand.
        html = _product_page_html(brand="")
        result = PRLMotorsportsAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == PRL_BRAND

    def test_honda_brand_rewritten_to_prl(self) -> None:
        # Target-vehicle leak: Shopify theme renders "Honda" as the brand when
        # vendor is blank. The adapter treats this as a car-make and rewrites
        # to PRL Motorsports so the manufacturer row isn't "Honda".
        html = _product_page_html(brand="Honda")
        result = PRLMotorsportsAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == PRL_BRAND

    def test_third_party_brand_passes_through(self) -> None:
        # Hondata FlashPro sold on PRL's storefront keeps its real manufacturer.
        html = _product_page_html(
            name="Hondata FlashPro for 2023+ Honda Civic Type R FL5",
            brand="Hondata",
            sku="HDFP-FL5",
        )
        result = PRLMotorsportsAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Hondata"
        assert result.part_number == "HDFP-FL5"

    def test_missing_json_ld_returns_none(self) -> None:
        # Soft-404 / non-product pages have no Product JSON-LD; skip them so
        # the runner doesn't ingest a blank row.
        html = "<html><head><title>Page Not Found</title></head><body></body></html>"
        assert PRLMotorsportsAdapter().parse_product_page(html, SAMPLE_URL) is None
