"""
Tests for shop.gmgracing.com adapter: host routing, URL shape guard,
manufacturer collapse, ``var meta`` parsing, and og-only fallback.

GMG's Shopify store runs an older theme that does **not** emit JSON-LD
Product blocks, so parsing leans on the inline ``var meta = {...};``
analytics blob for vendor / variant SKU / variant price-in-cents, with
og: meta tags as a fallback. These tests cover both paths against
synthetic HTML modeled on a real shop.gmgracing.com page.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.gmgracing import (
    GMGRacingAdapter,
    _is_product_url,
    _normalize_part_manufacturer,
)

SAMPLE_URL = "https://shop.gmgracing.com/products/gmg-wc-991-gt3-exhaust-center-section"


def _product_html(
    *,
    name: str = "991 GT3/GT3RS GMG WC Center Section Exhaust",
    vendor: str = "GMG",
    sku: str = "GMGEX991GT3CENTERWC-5",
    min_price_cents: int = 229500,
    description: str = "Direct bolt-on T304 stainless center section for 991 GT3/GT3RS.",
    image: str = "https://shop.gmgracing.com/cdn/shop/products/991_GT3RS_GMG_WCCenterSection_11_grande.jpg?v=1561659824",
    og_price: str = "2,295.00",
    include_meta_var: bool = True,
) -> str:
    """
    Minimal page mirroring a real GMG product: og: tags plus the inline
    ``var meta = {...};`` blob. When ``include_meta_var`` is ``False`` the
    blob is omitted so the og-only fallback path is exercised.
    """
    meta_var_block = ""
    if include_meta_var:
        meta_var_block = f"""
      <script>
      var meta = {{"product":{{"id":9435836867,"vendor":"{vendor}","type":"Headers","handle":"gmg-wc-991-gt3-exhaust-center-section","variants":[{{"id":1,"price":{min_price_cents},"sku":"{sku}"}},{{"id":2,"price":{min_price_cents + 15000},"sku":"{sku[:-1]}4"}}]}},"page":{{"pageType":"product"}}}};
      </script>
        """
    return f"""
    <html><head>
      <meta property="og:type" content="product">
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{description}">
      <meta property="og:image" content="{image}">
      <meta property="og:price:amount" content="{og_price}">
      <meta property="og:price:currency" content="USD">
      {meta_var_block}
    </head><body>
      <h1>{name}</h1>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-to-adapter routing covers shop.gmgracing.com and the raw myshopify mirror."""

    def test_shop_subdomain_routes_to_gmgracing(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "gmgracing"

    def test_bare_apex_routes_to_gmgracing(self) -> None:
        assert adapter_name_for_product_url("https://gmgracing.com/products/foo") == "gmgracing"

    def test_myshopify_mirror_routes_to_gmgracing(self) -> None:
        # Shopify stores are reachable at ``<shop>.myshopify.com`` in addition
        # to the primary domain; some links in the wild use that host.
        assert adapter_name_for_product_url("https://gmgracing.myshopify.com/products/foo") == "gmgracing"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/products/gmg") == "generic"


class TestProductUrlGuard:
    """Any GMG host URL with ``/products/`` in the path is a product page."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_apex_host_is_product_shape(self) -> None:
        assert _is_product_url("https://gmgracing.com/products/some-handle")

    def test_myshopify_host_is_product_shape(self) -> None:
        assert _is_product_url("https://gmgracing.myshopify.com/products/some-handle")

    def test_non_product_path_rejected(self) -> None:
        # Collections / CMS / cart pages don't live under /products/.
        assert not _is_product_url("https://shop.gmgracing.com/collections/porsche")
        assert not _is_product_url("https://shop.gmgracing.com/pages/about")
        assert not _is_product_url("https://shop.gmgracing.com/cart")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/products/foo")


class TestNormalizePartManufacturer:
    """
    GMG's vendor field is inconsistent (``GMG``, ``GMG Racing``, occasionally
    empty). ``_normalize_part_manufacturer`` collapses all self-spellings to
    the canonical brand without clobbering third-party vendor names on
    re-sold hardware.
    """

    def test_empty_brand_defaults_to_gmg_racing(self) -> None:
        assert _normalize_part_manufacturer("") == "GMG Racing"
        assert _normalize_part_manufacturer(None) == "GMG Racing"

    def test_gmg_variants_all_collapse(self) -> None:
        for variant in ("GMG", "GMG Racing", "gmg", "gmg racing", "GMGRacing", "gmg-racing"):
            assert _normalize_part_manufacturer(variant) == "GMG Racing", variant

    def test_third_party_brand_passes_through(self) -> None:
        # GMG re-sells Brembo / BBS / Recaro hardware under the real brand —
        # those vendor strings must land on the real manufacturer row rather
        # than being swallowed under GMG's name.
        assert _normalize_part_manufacturer("Brembo") == "Brembo"
        assert _normalize_part_manufacturer("BBS") == "BBS"
        assert _normalize_part_manufacturer("Recaro") == "Recaro"

    def test_whitespace_around_variant_still_collapses(self) -> None:
        assert _normalize_part_manufacturer("  GMG Racing  ") == "GMG Racing"


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape GMG HTML → ScrapedPayload."""

    def test_full_page_parses_from_meta_var(self) -> None:
        result = GMGRacingAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("991 GT3/GT3RS GMG")
        assert result.part_manufacturer == "GMG Racing"
        assert result.part_number == "GMGEX991GT3CENTERWC-5"
        # Lowest variant price wins — matches the "From $X" number in og:price.
        assert result.price_cents == 229500
        assert result.product_url == SAMPLE_URL
        # Image URL has the Shopify ``_grande`` named-size suffix stripped so
        # the gallery entry collapses onto the sitemap's canonical form.
        assert result.image_urls and result.image_urls[0].endswith(
            "/cdn/shop/products/991_GT3RS_GMG_WCCenterSection_11.jpg?v=1561659824"
        )

    def test_brand_variant_collapsed_to_canonical(self) -> None:
        # Vendor spelled "GMG Racing" on this product — still maps to the
        # single canonical brand row.
        html = _product_html(vendor="GMG Racing")
        result = GMGRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "GMG Racing"

    def test_third_party_vendor_passed_through(self) -> None:
        # Re-sold Brembo hardware — the third-party brand survives verbatim.
        html = _product_html(
            vendor="Brembo",
            name="991 Brembo Type-III REAR 2-piece Brake Rotors",
            sku="BREMBO-991-REAR-TYPE3",
        )
        result = GMGRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Brembo"
        assert result.part_number == "BREMBO-991-REAR-TYPE3"

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape pipeline must not feed CMS / collection URLs here.
        result = GMGRacingAdapter().parse_product_page(
            _product_html(),
            "https://shop.gmgracing.com/collections/porsche",
        )
        assert result is None

    def test_missing_meta_var_falls_back_to_og(self) -> None:
        # Older theme tweak — ``var meta`` blob absent. Adapter still pulls
        # name / description / images from og: tags, price from ``og:price:
        # amount`` (commas handled), and defaults the manufacturer to GMG
        # Racing since there's no vendor field to read.
        html = _product_html(include_meta_var=False, og_price="1,295.00")
        result = GMGRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("991 GT3/GT3RS GMG")
        assert result.part_manufacturer == "GMG Racing"
        assert result.part_number is None
        assert result.price_cents == 129500
        assert result.image_urls

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert GMGRacingAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_draft_product_without_prices_keeps_name(self) -> None:
        # Draft / "Call for quote" products have variants but no positive
        # integer prices. Name / SKU / brand still land; price is None.
        html = """
        <html><head>
          <meta property="og:type" content="product">
          <meta property="og:title" content="991 Cup GMG Race Seat - Call for Spec">
          <meta property="og:description" content="Custom-spec race seat.">
          <meta property="og:image" content="https://shop.gmgracing.com/cdn/shop/products/seat_grande.jpg">
          <script>
          var meta = {"product":{"id":1,"vendor":"GMG","handle":"race-seat","variants":[{"id":1,"price":0,"sku":"GMG-SEAT-CUP"}]}};
          </script>
        </head><body><h1>991 Cup GMG Race Seat</h1></body></html>
        """
        result = GMGRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("991 Cup GMG Race Seat")
        assert result.part_manufacturer == "GMG Racing"
        assert result.part_number == "GMG-SEAT-CUP"
        assert result.price_cents is None


class TestAdapterFetcherTier:
    """GMG's Shopify store works on plain HTTP (tier0)."""

    def test_declares_http_tier(self) -> None:
        # shop.gmgracing.com serves robots.txt, sitemap, and product pages
        # with plain ``requests`` + crawler UA — no TLS fingerprint block.
        assert GMGRacingAdapter.FETCHER_TIER == "http"
