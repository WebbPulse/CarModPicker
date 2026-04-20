"""
Tests for driveshaftshop.com adapter: WooCommerce + Yoast JSON-LD parsing
with DSS-specific nested-priceSpecification extraction, description-embedded
``PART# <code>`` preference over the numeric WooCommerce sku, and the
``"Driveshaft Shop"`` default brand.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.driveshaftshop import (
    DriveshaftShopAdapter,
    _is_product_child_sitemap,
    _part_number_from_description,
    _price_cents_from_price_specification,
    _strip_site_suffix,
)

SAMPLE_URL = "https://driveshaftshop.com/product/2020-2023-g80-bmw-m3-axles/"


def _product_page_html(
    *,
    name: str = "2020-2023 G80/G81/G82/G83 BMW M3 AXLES",
    sku: str = "510520",
    description: str = "The Driveshaft Shop BMW M3 axle description. PART# 510520",
    price: str = "2199.99",
    image_url: str = "https://driveshaftshop.com/wp-content/uploads/2023/12/BMW-G80-01.png",
    include_product: bool = True,
) -> str:
    """
    Minimal page that mirrors the WooCommerce + Yoast ``@graph`` JSON-LD shape
    DSS emits. Only the Product-node fields our adapter reads are populated;
    price sits in ``offers[0].priceSpecification[0].price`` (not on the Offer
    directly) to match the real site.
    """
    product_block = (
        f""",
          {{
            "@context": "https://schema.org/",
            "@type": "Product",
            "name": "{name}",
            "sku": "{sku}",
            "description": "{description}",
            "image": "{image_url}",
            "offers": [
              {{
                "@type": "Offer",
                "priceSpecification": [
                  {{
                    "@type": "UnitPriceSpecification",
                    "price": "{price}",
                    "priceCurrency": "USD"
                  }}
                ],
                "availability": "https://schema.org/InStock"
              }}
            ]
          }}"""
        if include_product
        else ""
    )
    return f"""
    <html><head>
      <title>{name} - Driveshaft Shop</title>
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org",
        "@graph": [
          {{"@type": "WebPage", "name": "{name} - Driveshaft Shop"}}
          {product_block}
        ]
      }}
      </script>
    </head><body></body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_bare_host_routes_to_driveshaftshop(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "driveshaftshop"

    def test_www_host_routes_to_driveshaftshop(self) -> None:
        assert adapter_name_for_product_url("https://www.driveshaftshop.com/product/some-slug/") == "driveshaftshop"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/driveshaftshop") == "generic"


class TestStripSiteSuffix:
    """Yoast appends the site name to WebPage titles; Product.name is usually clean,
    but strip defensively so a leaky page still produces a clean stored name."""

    def test_strips_hyphen_suffix(self) -> None:
        assert _strip_site_suffix("BMW E30 1-Piece Chromoly Driveshaft - Driveshaft Shop") == (
            "BMW E30 1-Piece Chromoly Driveshaft"
        )

    def test_strips_en_dash_suffix(self) -> None:
        assert _strip_site_suffix("BMW M3 Axles – Driveshaft Shop") == "BMW M3 Axles"

    def test_strips_the_driveshaft_shop(self) -> None:
        assert _strip_site_suffix("GTR Axles - The Driveshaft Shop") == "GTR Axles"

    def test_case_insensitive(self) -> None:
        assert _strip_site_suffix("Evo X Axles - driveshaft shop") == "Evo X Axles"

    def test_no_suffix_returns_name_unchanged(self) -> None:
        assert _strip_site_suffix("2020-2023 G80 BMW M3 AXLES") == "2020-2023 G80 BMW M3 AXLES"

    def test_only_suffix_preserves_original(self) -> None:
        assert _strip_site_suffix("- Driveshaft Shop") == "- Driveshaft Shop"


class TestPartNumberFromDescription:
    """``PART# <code>`` is the authoritative manufacturer part code."""

    def test_extracts_alphanumeric_code(self) -> None:
        desc = "This is our 1-piece conversion for the BMW E30 platform. PART# BMWSH3-CV"
        assert _part_number_from_description(desc) == "BMWSH3-CV"

    def test_extracts_numeric_code(self) -> None:
        assert _part_number_from_description("Description ends. PART# 510520") == "510520"

    def test_handles_slash_in_code(self) -> None:
        assert _part_number_from_description("PART# A/B123") == "A/B123"

    def test_case_insensitive(self) -> None:
        assert _part_number_from_description("part# abc-1") == "abc-1"

    def test_no_space_after_hash(self) -> None:
        assert _part_number_from_description("PART#XYZ-1") == "XYZ-1"

    def test_none_when_missing(self) -> None:
        assert _part_number_from_description("No code here at all.") is None

    def test_none_when_empty(self) -> None:
        assert _part_number_from_description(None) is None
        assert _part_number_from_description("") is None


class TestPriceFromPriceSpecification:
    """DSS buries price inside ``offers[0].priceSpecification[0].price``."""

    def test_extracts_from_nested_list(self) -> None:
        item = {
            "offers": [
                {
                    "priceSpecification": [{"price": "2199.99", "priceCurrency": "USD"}],
                }
            ]
        }
        assert _price_cents_from_price_specification(item) == 219999

    def test_extracts_from_scalar_offer(self) -> None:
        item = {"offers": {"priceSpecification": {"price": "99.00"}}}
        assert _price_cents_from_price_specification(item) == 9900

    def test_handles_comma_thousands(self) -> None:
        item = {"offers": [{"priceSpecification": [{"price": "3,160.30"}]}]}
        assert _price_cents_from_price_specification(item) == 316030

    def test_returns_none_when_missing_offers(self) -> None:
        assert _price_cents_from_price_specification({}) is None

    def test_returns_none_when_missing_specification(self) -> None:
        assert _price_cents_from_price_specification({"offers": [{"price": "10"}]}) is None

    def test_returns_none_on_zero_price(self) -> None:
        item = {"offers": [{"priceSpecification": [{"price": "0"}]}]}
        assert _price_cents_from_price_specification(item) is None

    def test_returns_none_on_invalid_price(self) -> None:
        item = {"offers": [{"priceSpecification": [{"price": "ask for price"}]}]}
        assert _price_cents_from_price_specification(item) is None


class TestIsProductChildSitemap:
    """Discovery only follows ``product-sitemap[N].xml`` children of the Yoast index."""

    def test_bare_product_sitemap_accepted(self) -> None:
        # DSS's catalog fits a single file.
        assert _is_product_child_sitemap("https://driveshaftshop.com/product-sitemap.xml")

    def test_numbered_product_sitemaps_accepted(self) -> None:
        # Yoast paginates once the catalog outgrows one sitemap.
        assert _is_product_child_sitemap("https://driveshaftshop.com/product-sitemap1.xml")
        assert _is_product_child_sitemap("https://driveshaftshop.com/product-sitemap42.xml")

    def test_non_product_children_rejected(self) -> None:
        for bad in (
            "https://driveshaftshop.com/post-sitemap.xml",
            "https://driveshaftshop.com/page-sitemap.xml",
            "https://driveshaftshop.com/category-sitemap.xml",
            "https://driveshaftshop.com/product_cat-sitemap.xml",
            "https://driveshaftshop.com/product_tag-sitemap.xml",
            "https://driveshaftshop.com/pa_driveshaft-sitemap.xml",
            "https://driveshaftshop.com/product/some-slug/",
        ):
            assert not _is_product_child_sitemap(bad), bad


class TestParseProductPage:
    """End-to-end parsing against real-shape DSS WooCommerce + Yoast HTML."""

    def test_full_page_parses(self) -> None:
        result = DriveshaftShopAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "2020-2023 G80/G81/G82/G83 BMW M3 AXLES"
        assert result.part_manufacturer == "Driveshaft Shop"
        # PART# 510520 (description) == sku on this product, but the description
        # pattern still wins — we rely on it over the numeric WooCommerce id.
        assert result.part_number == "510520"
        assert result.price_cents == 219999
        assert result.image_urls == ["https://driveshaftshop.com/wp-content/uploads/2023/12/BMW-G80-01.png"]

    def test_description_part_overrides_numeric_sku(self) -> None:
        # E30 driveshaft: WooCommerce id is 610002, but the real manufacturer
        # code is BMWSH3-CV (published in the description). Prefer the code so
        # cross-retailer dedupe works.
        html = _product_page_html(
            name="1986-1992 BMW E30 1-Piece Chromoly Driveshaft",
            sku="610002",
            description=(
                "This is our 1-piece conversion for the BMW E30 platform. "
                "Comes complete with precision machined plates. PART# BMWSH3-CV"
            ),
            price="1094.58",
        )
        result = DriveshaftShopAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "BMWSH3-CV"
        assert result.price_cents == 109458

    def test_missing_part_hash_falls_back_to_sku(self) -> None:
        # Degenerate description with no PART# line — fall back to the JSON-LD
        # sku rather than stamping ``None``.
        html = _product_page_html(sku="999999", description="No code in body.")
        result = DriveshaftShopAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "999999"

    def test_name_suffix_stripped_if_present(self) -> None:
        # Defensive: simulate a Product.name that leaks the site suffix.
        html = _product_page_html(name="GT500 Driveshaft - Driveshaft Shop")
        result = DriveshaftShopAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name == "GT500 Driveshaft"

    def test_missing_json_ld_returns_none(self) -> None:
        # Non-product landing page — no Product JSON-LD to parse.
        html = "<html><head><title>Page Not Found - Driveshaft Shop</title></head><body></body></html>"
        assert DriveshaftShopAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_no_product_in_graph_returns_none(self) -> None:
        # Graph has only a WebPage node, no Product.
        html = _product_page_html(include_product=False)
        assert DriveshaftShopAdapter().parse_product_page(html, SAMPLE_URL) is None
