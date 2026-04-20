"""
Tests for iagperformance.com adapter: BigCommerce Stencil JSON-LD parsing with
IAG-specific cleanups (mpn preferred over dropship-prefixed sku, brand
canonicalization for IAG's own spellings, Shogun page-builder description
scrubbing, gtin12 extraction, DOM gallery expansion past the JSON-LD hero).
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.iagperformance import (
    IAGPerformanceAdapter,
    _clean_shogun_markers,
    _image_dedup_key,
    _is_products_child_sitemap,
    _normalize_part_manufacturer,
)

SAMPLE_URL = (
    "https://www.iagperformance.com/iag-performance-crest-cnc-stage-x-2-5l-"
    "subaru-billet-aluminum-short-block-for-wrx-sti-lgt-fxt/"
)


def _product_page_html(
    *,
    name: str = (
        "IAG Performance / Crest CNC Stage X 2.5L Subaru Billet Aluminum " "Short Block For WRX, STI, LGT, FXT"
    ),
    sku: str = "IAG-ENG-SX25",
    mpn: str = "IAG-ENG-SX25",
    brand: str = "IAG Performance",
    description: str = "IAG Performance Crest CNC 2.5L Subaru Billet Aluminum Short Block 1150+ BHP.",
    price: str = "17999.99",
    gtin12: str = "",
    zoom_image: str = (
        "https://cdn11.bigcommerce.com/s-40kcmfrwg5/images/stencil/1280x1280/"
        "products/6385/144544/IAG-ENG-SX25-01__03126.1729104343.jpg?c=1"
    ),
    lowres_image: str = (
        "https://cdn11.bigcommerce.com/s-40kcmfrwg5/images/stencil/500x459/"
        "products/6385/144544/IAG-ENG-SX25-01__03126.1729104343.jpg?c=1"
    ),
) -> str:
    """Minimal page that mirrors the real BigCommerce Stencil JSON-LD shape IAG emits."""
    brand_field = f'"brand": {{"@type": "Brand", "name": "{brand}"}},' if brand else ""
    gtin_field = f'"gtin12": "{gtin12}",' if gtin12 else ""
    return f"""
    <html><head>
      <title>{name}</title>
      <meta property="og:type" content="product" />
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "{name}",
        "sku": "{sku}",
        "mpn": "{mpn}",
        {gtin_field}
        "url": "{SAMPLE_URL}",
        {brand_field}
        "description": "{description}",
        "image": "{zoom_image}",
        "offers": {{
          "@type": "Offer",
          "priceCurrency": "USD",
          "price": "{price}",
          "availability": "https://schema.org/InStock"
        }}
      }}
      </script>
    </head><body>
      <h1 class="productView-title" itemprop="name">{name}</h1>
      <section class="productView-images" data-image-gallery>
        <figure class="productView-image" data-zoom-image="{zoom_image}">
          <img class="productView-image--default" data-src="{lowres_image}" alt="{name}">
        </figure>
      </section>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_www_host_routes_to_iagperformance(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "iagperformance"

    def test_bare_host_routes_to_iagperformance(self) -> None:
        assert adapter_name_for_product_url("https://iagperformance.com/some-slug/") == "iagperformance"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/iagperformance") == "generic"


class TestNormalizePartManufacturer:
    """IAG's self-spellings collapse; third-party vendors pass through."""

    def test_iag_variants_collapse_to_canonical(self) -> None:
        for raw in ("IAG", "IAG Performance", "iag", "iag-performance", "IAGPerformance"):
            assert _normalize_part_manufacturer(raw) == "IAG Performance", raw

    def test_third_party_brand_passes_through(self) -> None:
        # Subaru-focused reseller catalog — ACT, Cobb, Perrin, GrimmSpeed, etc.
        # land on their real manufacturer row.
        assert _normalize_part_manufacturer("ACT") == "ACT"
        assert _normalize_part_manufacturer("Cobb Tuning") == "Cobb Tuning"
        assert _normalize_part_manufacturer("GrimmSpeed") == "GrimmSpeed"

    def test_empty_returns_none(self) -> None:
        # None enables the caller's title-heuristic fallback.
        assert _normalize_part_manufacturer(None) is None
        assert _normalize_part_manufacturer("") is None
        assert _normalize_part_manufacturer("   ") is None


class TestCleanShogunMarkers:
    """Shogun page-builder element anchors must be scrubbed before ingest."""

    def test_strips_single_marker(self) -> None:
        raw = 'Intro text.\n    {\n      "__shgImageV2Elements": { "uuid": "s-0bf8bc47" }\n    }\n       Body text.'
        cleaned = _clean_shogun_markers(raw)
        assert cleaned is not None
        assert "__shgImageV2Elements" not in cleaned
        assert "uuid" not in cleaned
        assert "Intro text." in cleaned
        assert "Body text." in cleaned

    def test_strips_multiple_markers(self) -> None:
        raw = 'A {"__shgImageV2Elements": {"uuid": "s-1"}} B ' '{"__shgImageV2Elements": {"uuid": "s-2"}} C'
        cleaned = _clean_shogun_markers(raw)
        assert cleaned == "A B C"

    def test_plain_description_passes_through(self) -> None:
        raw = "Just a normal product description with no page-builder markers."
        assert _clean_shogun_markers(raw) == raw

    def test_empty_input_returns_input(self) -> None:
        assert _clean_shogun_markers(None) is None
        assert _clean_shogun_markers("") == ""


class TestIsProductsChildSitemap:
    """Discovery only follows ``type=products&page=N`` children of the sitemap index."""

    def test_products_children_accepted(self) -> None:
        assert _is_products_child_sitemap("https://www.iagperformance.com/xmlsitemap.php?type=products&page=1")
        assert _is_products_child_sitemap("https://www.iagperformance.com/xmlsitemap.php?type=products&page=2")

    def test_non_product_children_rejected(self) -> None:
        for bad in (
            "https://www.iagperformance.com/xmlsitemap.php?type=pages&page=1",
            "https://www.iagperformance.com/xmlsitemap.php?type=categories&page=1",
            "https://www.iagperformance.com/xmlsitemap.php?type=brands&page=1",
            "https://www.iagperformance.com/xmlsitemap.php?type=news&page=1",
            "https://www.iagperformance.com/some-product-slug/",
        ):
            assert not _is_products_child_sitemap(bad), bad


class TestImageDedupKey:
    """The same photo appears at several stencil sizes — keys must collapse."""

    URLS = [
        "https://cdn11.bigcommerce.com/s-40kcmfrwg5/images/stencil/1280x1280/products/6385/144544/abc__03126.1729104343.jpg?c=1",
        "https://cdn11.bigcommerce.com/s-40kcmfrwg5/images/stencil/500x459/products/6385/144544/abc__03126.1729104343.jpg?c=1",
        "https://cdn11.bigcommerce.com/s-40kcmfrwg5/products/6385/images/144544/abc__03126.1729104343.500.750.jpg?c=1",
    ]

    def test_all_size_variants_collapse_to_one_key(self) -> None:
        keys = {_image_dedup_key(u) for u in self.URLS}
        assert len(keys) == 1

    def test_different_photos_keep_distinct_keys(self) -> None:
        a = _image_dedup_key(self.URLS[0])
        b = _image_dedup_key(
            "https://cdn11.bigcommerce.com/s-40kcmfrwg5/images/stencil/1280x1280/"
            "products/6385/144545/xyz__03127.1729104344.jpg?c=1"
        )
        assert a != b


class TestParseProductPage:
    """End-to-end parsing against real-shape BigCommerce Stencil JSON-LD."""

    def test_full_page_parses_house_brand(self) -> None:
        result = IAGPerformanceAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "IAG Performance"
        assert result.part_number == "IAG-ENG-SX25"
        assert result.price_cents == 1799999
        assert result.product_url == SAMPLE_URL
        # 1280x1280 and 500x459 variants of the same photo collapse to one entry.
        assert result.image_urls is not None
        assert len(result.image_urls) == 1
        assert "1280x1280" in result.image_urls[0]

    def test_iag_brand_variant_canonicalized(self) -> None:
        # Older IAG products emit brand="IAG" rather than "IAG Performance".
        # Both should end up as the single canonical row.
        html = _product_page_html(brand="IAG")
        result = IAGPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "IAG Performance"

    def test_third_party_brand_passed_through(self) -> None:
        # IAG re-sells ACT clutches via BC dropship — the brand should land on ACT.
        html = _product_page_html(
            name="ACT 6 Pad Rigid Race Disc for 2004+ Subaru WRX STI - 6240018",
            sku="ds_BHXS_6240018",
            mpn="6240018",
            brand="ACT",
            description="ACT 6 Pad Rigid Race Clutch Disc with ceramic friction materials.",
            price="175",
        )
        result = IAGPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "ACT"
        # mpn wins over the dropship-prefixed sku so cross-retailer dedup sees
        # the clean manufacturer part number, not the BC internal code.
        assert result.part_number == "6240018"
        assert result.price_cents == 17500

    def test_dropship_prefix_stripped_from_sku_when_mpn_empty(self) -> None:
        # If a product ever lands with ds_<BRAND>_ SKU but no mpn, the prefix
        # should still be scrubbed so the part number is a clean MPN.
        html = _product_page_html(sku="ds_BHXS_6240018", mpn="")
        result = IAGPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "6240018"

    def test_shogun_markers_stripped_from_description(self) -> None:
        html = _product_page_html(
            description=(
                "IAG PERFORMANCE / CREST CNC 2.5L BILLET BLOCK 1150+ BHP "
                '{\\"__shgImageV2Elements\\": {\\"uuid\\": \\"s-0bf8bc47\\"}} '
                "Precision machined from 6061-T6 Aerospace Aluminum."
            ),
        )
        result = IAGPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.description is not None
        assert "__shgImageV2Elements" not in result.description
        assert "uuid" not in result.description
        assert "1150+ BHP" in result.description
        assert "6061-T6" in result.description

    def test_gtin12_passed_through_when_present(self) -> None:
        html = _product_page_html(gtin12="887753904157")
        result = IAGPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.gtin == "887753904157"

    def test_gtin_absent_when_not_emitted(self) -> None:
        result = IAGPerformanceAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.gtin is None

    def test_missing_json_ld_returns_none(self) -> None:
        # Soft 404s and non-product pages have no JSON-LD Product — skip them
        # so the runner doesn't ingest a blank row.
        html = "<html><head><title>Page Not Found - IAG Performance</title></head><body></body></html>"
        assert IAGPerformanceAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_non_product_path_returns_none(self) -> None:
        # Off-host URL shouldn't get routed to the adapter, but be defensive.
        html = _product_page_html()
        assert IAGPerformanceAdapter().parse_product_page(html, "https://www.iagperformance.com/cart.php") is None
