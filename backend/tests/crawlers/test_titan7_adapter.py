"""
Tests for titan7.com adapter: host routing, URL shape guard, manufacturer
collapse, JSON-LD parsing, and DOM/og fallback.

Titan7 is a direct-only forged wheel manufacturer on a modern Shopify theme
(see RETAILER_BACKLOG.md: "Shopify. Tier-0."). Tests run against synthetic
HTML modeled on the schema.org ``Product`` block Shopify emits by default.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.titan7 import (
    Titan7Adapter,
    _is_product_url,
    _normalize_part_manufacturer,
)

SAMPLE_URL = "https://titan7.com/products/t-s5"


def _product_html(
    *,
    name: str = "Titan 7 T-S5 Forged Wheel",
    brand: str = "Titan7",
    sku: str = "TS5-18105-5X120-BMW",
    price: str = "3200.00",
    description: str = "Titan7 T-S5 forged wheel, BMW F8x / G8x track fitment.",
    image: str = "https://cdn.shopify.com/s/files/1/0001/titan7-ts5.jpg",
) -> str:
    """Minimal page mirroring Shopify's default schema.org Product JSON-LD block."""
    brand_field = f'"brand":{{"@type":"Brand","name":"{brand}"}},' if brand else ""
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
        {brand_field}
        "sku": "{sku}",
        "image": ["{image}"],
        "offers": {{
          "@type": "Offer",
          "price": "{price}",
          "priceCurrency": "USD",
          "availability": "https://schema.org/InStock"
        }}
      }}
      </script>
    </head><body>
      <h1>{name}</h1>
      <media-gallery>
        <img src="{image}">
      </media-gallery>
    </body></html>
    """


class TestAdapterRegistration:
    """The host-to-adapter map routes every titan7.com page through this adapter."""

    def test_bare_host_routes_to_titan7(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "titan7"

    def test_www_host_routes_to_titan7(self) -> None:
        assert adapter_name_for_product_url("https://www.titan7.com/products/t-r10") == "titan7"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        # A substring match would be wrong: ``titan7motorsports.com`` (which
        # does not exist today, but the suffix check is what prevents a
        # future imposter host from inheriting this adapter).
        assert adapter_name_for_product_url("https://example.com/titan7") == "generic"


class TestProductUrlGuard:
    """Shape guard: any titan7.com URL with ``/products/`` in the path is a product page."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_www_host_is_product_shape(self) -> None:
        assert _is_product_url("https://www.titan7.com/products/some-handle")

    def test_non_product_path_rejected(self) -> None:
        # Collections / CMS / cart pages do not have ``/products/`` in the path.
        assert not _is_product_url("https://titan7.com/collections/bmw")
        assert not _is_product_url("https://titan7.com/pages/about")
        assert not _is_product_url("https://titan7.com/cart")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/products/foo")


class TestNormalizePartManufacturer:
    """
    Titan7's Shopify vendor field is inconsistent (``Titan7``, ``Titan 7``,
    occasionally empty). ``_normalize_part_manufacturer`` collapses all
    self-spellings to a single canonical brand without losing the rare
    co-branded third-party SKU.
    """

    def test_empty_brand_defaults_to_titan7(self) -> None:
        assert _normalize_part_manufacturer("") == "Titan7"
        assert _normalize_part_manufacturer(None) == "Titan7"

    def test_titan7_variants_all_collapse(self) -> None:
        for variant in ("Titan7", "titan7", "Titan 7", "TITAN 7", "titan-7", "Titan-7"):
            assert _normalize_part_manufacturer(variant) == "Titan7", variant

    def test_third_party_brand_passes_through(self) -> None:
        # Rare but possible co-branded SKU — a JSON-LD brand that isn't a
        # Titan7 self-spelling must survive so the global part-manufacturer
        # table gets the real third-party row.
        assert _normalize_part_manufacturer("BBS") == "BBS"
        assert _normalize_part_manufacturer("HRE") == "HRE"

    def test_whitespace_around_variant_still_collapses(self) -> None:
        assert _normalize_part_manufacturer("  Titan7  ") == "Titan7"


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape Shopify HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = Titan7Adapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Titan 7 T-S5")
        assert result.part_manufacturer == "Titan7"
        assert result.part_number == "TS5-18105-5X120-BMW"
        assert result.price_cents == 320000
        assert result.product_url == SAMPLE_URL
        assert result.image_urls and result.image_urls[0].startswith("https://cdn.shopify.com/")

    def test_brand_variant_collapsed_to_canonical(self) -> None:
        # Vendor field spelled "Titan 7" (space) — still maps to the single
        # canonical "Titan7" row.
        html = _product_html(brand="Titan 7")
        result = Titan7Adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Titan7"

    def test_missing_brand_defaults_to_titan7(self) -> None:
        # JSON-LD brand absent — the default kicks in rather than running
        # the title-first-word heuristic (which would pick up fitment tokens
        # like "BMW" / "Porsche" from titles like "Titan 7 T-S5 for BMW G80").
        html = _product_html(brand="")
        result = Titan7Adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Titan7"

    def test_third_party_brand_passed_through(self) -> None:
        # Co-branded SKU — the third-party brand survives verbatim.
        html = _product_html(brand="BBS", name="BBS-Forged Collab Wheel")
        result = Titan7Adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "BBS"

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape pipeline must not feed CMS / collection URLs here.
        result = Titan7Adapter().parse_product_page(
            _product_html(),
            "https://titan7.com/collections/bmw",
        )
        assert result is None

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD — adapter should still pull title / description / price
        # from og: meta tags and default the manufacturer to Titan7.
        html = """
        <html><head>
          <meta property="og:title" content="Titan 7 T-R10 Forged Wheel">
          <meta property="og:description" content="Titan7 T-R10 for Porsche 992 GT3, 20-inch forged.">
          <meta property="og:image" content="https://cdn.shopify.com/s/files/1/0001/titan7-tr10.jpg">
          <meta property="product:price:amount" content="3500.00">
        </head><body>
          <h1>Titan 7 T-R10 Forged Wheel</h1>
          <p>SKU: TR10-20115-5X130-PORSCHE</p>
        </body></html>
        """
        result = Titan7Adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Titan 7 T-R10")
        assert result.part_manufacturer == "Titan7"
        assert result.part_number == "TR10-20115-5X130-PORSCHE"
        assert result.price_cents == 350000

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert Titan7Adapter().parse_product_page(html, SAMPLE_URL) is None

    def test_fitment_string_in_jsonld_sku_is_rejected(self) -> None:
        # Real-corpus pattern: titan-7.com renders one schema.org Product per
        # supported chassis fitment on each wheel-model URL and abuses the
        # ``sku`` field to hold the fitment label (year shorthand + chassis
        # name). Trusting that string would tag every wheel SKU on the page
        # with the same bogus PN. Reject any sku that carries a year shorthand
        # like ``'23`` / ``'21-`` — real Titan7 SKUs never contain apostrophes.
        html = _product_html(name="T-R10 Forged 10 Spoke", sku="Acura Integra Type S '23-")
        result = Titan7Adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name == "T-R10 Forged 10 Spoke"
        assert result.part_number is None

    def test_real_titan7_sku_passes_through(self) -> None:
        # Defensive case: a real Titan7 wheel SKU has no apostrophes and must
        # survive the fitment-string guard intact.
        html = _product_html(sku="TR10-1995-5X1143-CB73")
        result = Titan7Adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "TR10-1995-5X1143-CB73"


class TestAdapterFetcherTier:
    """Titan7 starts on plain HTTP (tier0); promote to ``tls`` if Cloudflare fires."""

    def test_declares_http_tier(self) -> None:
        # Default tier — Titan7's Shopify storefront is not TLS-fingerprint-
        # blocked today. If that changes, flip FETCHER_TIER to "tls" and
        # switch the adapter's discover_product_urls to use self.fetcher.
        assert Titan7Adapter.FETCHER_TIER == "http"
