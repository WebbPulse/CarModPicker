"""
Tests for cobbtuning.com adapter: URL shape guard, registration, fetcher tier,
JSON-LD parse, DOM fallback, and the COBB-Tuning manufacturer default.

Cobb is a Magento 2 store behind Cloudflare-style bot protection (see
``site_problem_notes/cobbtuning.md``); we have not captured a real product page
yet. These tests run against *synthetic* HTML modeled on a generic schema.org
``Product`` block, which is what Magento 2's default SEO output emits.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier1_tls.cobbtuning import (
    CobbTuningAdapter,
    _is_product_url,
)

SAMPLE_URL = "https://www.cobbtuning.com/accessport-v3-sub-002-subaru-wrx-sti-2015-2021.html"


def _product_html(
    *,
    name: str = "COBB AccessPORT V3 Subaru WRX/STI 2015-2021",
    brand: str = "COBB Tuning",
    sku: str = "AP3-SUB-002",
    price: str = "775.00",
    description: str = "AccessPORT V3 handheld tuner for 2015-2021 Subaru WRX and STI.",
    image: str = "https://www.cobbtuning.com/media/catalog/product/a/p/ap3-sub-002.jpg",
) -> str:
    """Minimal page mirroring Magento 2's default schema.org Product JSON-LD block."""
    return f"""
    <html><head>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{description}">
      <meta property="og:image" content="{image}">
      <meta property="product:price:amount" content="{price}">
      <meta property="og:price:currency" content="USD">
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "{name}",
        "description": "{description}",
        "brand": {{"@type": "Brand", "name": "{brand}"}},
        "sku": "{sku}",
        "mpn": "{sku}",
        "image": ["{image}"],
        "offers": {{
          "@type": "Offer",
          "price": "{price}",
          "priceCurrency": "USD",
          "availability": "https://schema.org/InStock"
        }}
      }}
      </script>
    </head><body><h1>{name}</h1></body></html>
    """


class TestAdapterRegistration:
    """The host-to-adapter map routes every cobbtuning.com page through this adapter."""

    def test_host_maps_to_cobbtuning(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "cobbtuning"

    def test_bare_host_also_maps(self) -> None:
        assert adapter_name_for_product_url("https://cobbtuning.com/accessport-v3.html") == "cobbtuning"

    def test_unrelated_host_does_not_map(self) -> None:
        assert adapter_name_for_product_url("https://example.com/accessport-v3.html") != "cobbtuning"


class TestProductUrlRegex:
    """
    Shape guard for Cobb URLs. Category / CMS pages also end in .html, so this
    is not a positive product-page identifier — it rejects query strings (banned
    by robots.txt), off-host URLs, and common CMS / account / checkout paths.
    """

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_bare_root_slug(self) -> None:
        assert _is_product_url("https://www.cobbtuning.com/accessport-v3.html")

    def test_query_string_rejected(self) -> None:
        # robots.txt disallows /*? — any URL with a query string is off limits.
        assert not _is_product_url(SAMPLE_URL + "?utm_source=x")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/accessport-v3.html")

    def test_cms_path_rejected(self) -> None:
        # CMS pages (about, support, warranty, dealers, etc.) often end in .html
        # in Magento 2 — the runner shouldn't waste fetches on them.
        assert not _is_product_url("https://www.cobbtuning.com/about-us.html")
        assert not _is_product_url("https://www.cobbtuning.com/warranty.html")
        assert not _is_product_url("https://www.cobbtuning.com/dealers.html")

    def test_non_html_path_rejected(self) -> None:
        # Anything without the Magento 2 .html url_key suffix is not a product.
        assert not _is_product_url("https://www.cobbtuning.com/accessport-v3")
        assert not _is_product_url("https://www.cobbtuning.com/media/some-image.jpg")


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = CobbTuningAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("COBB")
        assert result.part_manufacturer == "COBB Tuning"
        assert result.part_number == "AP3-SUB-002"
        assert result.price_cents == 77500
        assert result.product_url == SAMPLE_URL
        assert result.image_urls and result.image_urls[0].endswith(".jpg")

    def test_non_product_url_returns_none(self) -> None:
        # Guard: parse entry rejects non-product URLs so the archive rescrape
        # pipeline can't feed CMS pages through this adapter.
        result = CobbTuningAdapter().parse_product_page(
            _product_html(),
            "https://www.cobbtuning.com/about-us.html",
        )
        assert result is None

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD at all — the adapter should still pull title / description /
        # price from og: meta tags and default the manufacturer to COBB Tuning.
        html = """
        <html><head>
          <meta property="og:title" content="COBB Stage 1+ Power Package WRX 2015-2021">
          <meta property="og:description" content="Stage 1+ software + SF intake for WRX 2015-2021.">
          <meta property="og:image" content="https://www.cobbtuning.com/media/product/stage1-wrx.jpg">
          <meta property="product:price:amount" content="1295.00">
        </head><body>
          <h1>COBB Stage 1+ Power Package WRX 2015-2021</h1>
          <p>SKU: 600X50-WRX</p>
        </body></html>
        """
        result = CobbTuningAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("COBB")
        # DOM-fallback path deliberately skips the title-first-word heuristic
        # and assigns the canonical "COBB Tuning" parent brand — better than
        # writing "COBB" / "Stage" / "Accessport" as a manufacturer from the
        # title's first token.
        assert result.part_manufacturer == "COBB Tuning"
        assert result.part_number == "600X50-WRX"
        assert result.price_cents == 129500

    def test_default_manufacturer_when_title_heuristic_fails(self) -> None:
        # Product title has no leading brand token the heuristic can latch onto
        # ("Accessport" is a product word). The adapter should default to
        # "COBB Tuning" rather than writing "Accessport" as a manufacturer.
        html = """
        <html><head>
          <meta property="og:title" content="Accessport V3 Flash Tuner">
          <meta property="og:image" content="https://www.cobbtuning.com/media/product/ap3.jpg">
        </head><body>
          <h1>Accessport V3 Flash Tuner</h1>
        </body></html>
        """
        result = CobbTuningAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "COBB Tuning"

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert CobbTuningAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """Cobb declares the TLS fetcher tier so the runner hands it curl_cffi."""

    def test_declares_tls_tier(self) -> None:
        assert CobbTuningAdapter.FETCHER_TIER == "tls"
