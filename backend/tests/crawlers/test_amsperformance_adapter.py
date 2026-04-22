"""
Tests for amsperformance.com adapter: WooCommerce + Rank Math JSON-LD parsing
with AMS-specific name-suffix and variable-product SKU cleanups, plus the
brand fallback that defaults to ``"AMS Performance"`` when JSON-LD omits it.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.amsperformance import (
    AMSPerformanceAdapter,
    _clean_part_number,
    _is_product_child_sitemap,
    _strip_site_suffix,
)

SAMPLE_URL = "https://www.amsperformance.com/product/ams-performance-infiniti-q50-q60-80mm-air-intakes/"


def _product_page_html(
    *,
    name: str = "AMS Performance INFINITI Q50/Q60 80mm Air Intakes - AMS Performance",
    sku: str = "ALP.28.08.0003-1",
    brand: str = "AMS Performance",
    description: str = "The Highest Flowing Intakes for the VR30.",
    price: str = "420.69",
    image_url: str = "https://www.amsperformance.com/wp-content/uploads/2025/08/intakes-1.jpg",
) -> str:
    """
    Minimal page that mirrors the Rank Math ``@graph`` JSON-LD shape AMS emits.
    Only the Product node fields our adapter reads are populated.
    """
    brand_field = f'"brand":{{"@type":"Brand","name":"{brand}"}},' if brand else ""
    return f"""
    <html><head>
      <title>{name}</title>
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org",
        "@graph": [
          {{"@type": "WebSite", "name": "AMS Performance"}},
          {{
            "@type": "Product",
            "name": "{name}",
            "sku": "{sku}",
            {brand_field}
            "description": "{description}",
            "image": [
              {{"@type": "ImageObject", "url": "{image_url}"}}
            ],
            "offers": {{
              "@type": "Offer",
              "price": "{price}",
              "priceCurrency": "USD"
            }}
          }}
        ]
      }}
      </script>
    </head><body></body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_www_host_routes_to_amsperformance(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "amsperformance"

    def test_bare_host_routes_to_amsperformance(self) -> None:
        assert adapter_name_for_product_url("https://amsperformance.com/product/some-slug/") == "amsperformance"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/amsperformance") == "generic"


class TestStripSiteSuffix:
    """Rank Math appends ``" - AMS Performance"`` to every product name."""

    def test_strips_exact_suffix(self) -> None:
        assert (
            _strip_site_suffix("AMS Performance GTR 80mm Intakes - AMS Performance")
            == "AMS Performance GTR 80mm Intakes"
        )

    def test_case_insensitive(self) -> None:
        assert _strip_site_suffix("Titan GTR Diaper - ams performance") == "Titan GTR Diaper"

    def test_extra_whitespace_trimmed(self) -> None:
        assert _strip_site_suffix("Seibon Doors  -   AMS Performance  ") == "Seibon Doors"

    def test_no_suffix_returns_name_unchanged(self) -> None:
        assert _strip_site_suffix("Seibon Carbon Doors") == "Seibon Carbon Doors"

    def test_only_suffix_preserves_original(self) -> None:
        # Pathological input: if the whole string is just the suffix, returning
        # an empty name would fail the downstream length check. Fall back to
        # the original so the page still parses.
        assert _strip_site_suffix("- AMS Performance") == "- AMS Performance"


class TestCleanPartNumber:
    """Variable-product parent SKUs emit dangling dashes we must trim."""

    def test_trims_trailing_dash(self) -> None:
        assert _clean_part_number("ALP.07.11.0001-") == "ALP.07.11.0001"

    def test_trims_multiple_trailing_dashes(self) -> None:
        assert _clean_part_number("ALP.07.11.0001---") == "ALP.07.11.0001"

    def test_passes_through_clean_sku(self) -> None:
        assert _clean_part_number("NI78") == "NI78"
        assert _clean_part_number("TMS GTR-DRV-105") == "TMS GTR-DRV-105"

    def test_preserves_internal_dashes(self) -> None:
        # Real MPNs contain dashes ("DD0910NSGTR-OE-DRY") — only trailing ones go.
        assert _clean_part_number("DD0910NSGTR-OE-DRY") == "DD0910NSGTR-OE-DRY"

    def test_variant_numeric_suffix_left_alone(self) -> None:
        # "ALP.28.08.0003-1" is the first variant of a variable product. We keep
        # the "-1" because trimming it would collapse distinct variants into one
        # SKU; only a bare trailing dash (the default / no-variant case) is noise.
        assert _clean_part_number("ALP.28.08.0003-1") == "ALP.28.08.0003-1"

    def test_empty_returns_none(self) -> None:
        assert _clean_part_number(None) is None
        assert _clean_part_number("") is None
        assert _clean_part_number("-") is None


class TestIsProductChildSitemap:
    """Discovery only follows ``product-sitemap{N}.xml`` children of the Rank Math index."""

    def test_product_children_accepted(self) -> None:
        assert _is_product_child_sitemap("https://www.amsperformance.com/product-sitemap1.xml")
        assert _is_product_child_sitemap("https://www.amsperformance.com/product-sitemap42.xml")

    def test_non_product_children_rejected(self) -> None:
        for bad in (
            "https://www.amsperformance.com/post-sitemap1.xml",
            "https://www.amsperformance.com/page-sitemap.xml",
            "https://www.amsperformance.com/category-sitemap.xml",
            "https://www.amsperformance.com/video-sitemap2.xml",
            "https://www.amsperformance.com/dealer-sitemap1.xml",
            "https://www.amsperformance.com/build-sitemap.xml",
            "https://www.amsperformance.com/instructions-sitemap.xml",
            "https://www.amsperformance.com/product/some-slug/",
        ):
            assert not _is_product_child_sitemap(bad), bad


class TestParseProductPage:
    """End-to-end parsing against real-shape AMS WooCommerce + Rank Math HTML."""

    def test_full_page_parses_house_brand(self) -> None:
        result = AMSPerformanceAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        # " - AMS Performance" suffix trimmed.
        assert result.name == "AMS Performance INFINITI Q50/Q60 80mm Air Intakes"
        assert result.part_manufacturer == "AMS Performance"
        assert result.part_number == "ALP.28.08.0003-1"
        assert result.price_cents == 42069
        assert result.description == "The Highest Flowing Intakes for the VR30."
        assert result.image_urls == ["https://www.amsperformance.com/wp-content/uploads/2025/08/intakes-1.jpg"]

    def test_third_party_brand_passed_through(self) -> None:
        html = _product_page_html(
            name="Driveshaft Shop Nissan R35 GTR 1000HP Axle Kit [NI78] - AMS Performance",
            sku="NI78",
            brand="Driveshaft Shop",
            description="Porsche-style 108mm CVs with upgraded 30-spline 300M races.",
            price="3160.30",
        )
        result = AMSPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Driveshaft Shop"
        assert result.part_number == "NI78"
        assert result.price_cents == 316030

    def test_missing_brand_falls_back_to_title_then_default(self) -> None:
        # Titan Motorsport product on amsperformance.com emits brand=null in
        # JSON-LD; title-heuristic picks up "Titan" as the first non-generic token.
        html = _product_page_html(
            name="Titan Motorsport Kevlar GTR Transmission Diaper - AMS Performance",
            sku="TMS GTR-DRV-105",
            brand="",
            description="Kevlar transmission blanket for GTR builds.",
            price="1149.00",
        )
        result = AMSPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Titan"
        assert result.part_number == "TMS GTR-DRV-105"

    def test_missing_brand_and_untitled_falls_back_to_ams(self) -> None:
        # Degenerate title (all generic words) — default to "AMS Performance"
        # rather than stamping ``None`` that would later fail ingestion.
        html = _product_page_html(
            name="Turbo Kit - AMS Performance",
            sku="X1",
            brand="",
            description="Generic product description.",
            price="100.00",
        )
        result = AMSPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "AMS Performance"

    def test_variable_product_dangling_dash_trimmed(self) -> None:
        html = _product_page_html(sku="ALP.07.11.0001-")
        result = AMSPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "ALP.07.11.0001"

    def test_missing_json_ld_returns_none(self) -> None:
        # Soft 404s and non-product landing pages have no JSON-LD Product node;
        # skip them so the runner doesn't ingest a blank row.
        html = "<html><head><title>Page Not Found - AMS Performance</title></head><body></body></html>"
        assert AMSPerformanceAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_jsonld_url_mismatch_still_parses(self) -> None:
        # WooCommerce sometimes renames a product slug and 301s the old URL to
        # the new one; the JSON-LD then declares the post-redirect URL while
        # the runner still passes the original. The adapter must not reject
        # the block just because its declared URL doesn't match the input.
        html = _product_page_html(
            name="AMS Performance INFINITI Q50/Q60 80mm Air Intakes - AMS Performance",
            sku="ALP.28.08.0003-1",
        )
        input_url = "https://www.amsperformance.com/product/old-ams-infiniti-intakes/"
        result = AMSPerformanceAdapter().parse_product_page(html, input_url)
        assert result is not None
        assert result.part_number == "ALP.28.08.0003-1"
