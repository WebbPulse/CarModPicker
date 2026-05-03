"""
Tests for sheepeyrace.com adapter: host routing (including the legacy
sheepeybuilt.com host), URL shape guard, manufacturer collapse, JSON-LD
parsing, and DOM/og fallback.

Sheepey Race is a modern Shopify storefront (Honda K/L turbo manifolds,
custom turbo kits — see RETAILER_BACKLOG.md). Tests run against synthetic
HTML modeled on the schema.org ``Product`` block Shopify emits by default,
with the real-site quirk that the JSON-LD ``sku`` field is absent and the
brand field is all-caps ``"SHEEPEYRACE"``.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.sheepeybuilt import (
    SheepeyBuiltAdapter,
    _is_product_url,
    _normalize_part_manufacturer,
)

SAMPLE_URL = "https://sheepeyrace.com/products/sheepey-built-honda-forward-facing-1300hp-intercooler"
LEGACY_URL = "https://www.sheepeybuilt.com/products/sheepey-race-honda-acura-k-series-sidewinder-manifold"


def _product_html(
    *,
    name: str = "SHEEPEYRACE FORWARD FACING 1000-1300HP INTERCOOLER",
    brand: str = "SHEEPEYRACE",
    sku: str = "",
    price: str = "800.00",
    description: str = "Sheepey Built forward-facing intercooler for high-HP Honda turbo setups.",
    image: str = "https://sheepeyrace.com/cdn/shop/files/FF-topaz-denoise-sharpen.jpg?v=1742320692",
) -> str:
    """
    Minimal page mirroring Shopify's default schema.org Product JSON-LD block.
    ``sku`` defaults to empty because the real storefront omits the field —
    every offer is variant-keyed by Shopify variant_id, not by a human MPN.
    """
    brand_field = f'"brand":{{"@type":"Brand","name":"{brand}"}},' if brand else ""
    sku_field = f'"sku":"{sku}",' if sku else ""
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
        {sku_field}
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
    """
    The host-to-adapter map routes sheepeyrace.com pages through this adapter,
    and also routes the legacy sheepeybuilt.com host (301s to sheepeyrace.com
    but archived scraped HTML still carries the old URL).
    """

    def test_sheepeyrace_host_routes_to_sheepeybuilt(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "sheepeybuilt"

    def test_www_sheepeyrace_host_routes_to_sheepeybuilt(self) -> None:
        assert adapter_name_for_product_url("https://www.sheepeyrace.com/products/foo") == "sheepeybuilt"

    def test_legacy_sheepeybuilt_host_routes_to_sheepeybuilt(self) -> None:
        assert adapter_name_for_product_url(LEGACY_URL) == "sheepeybuilt"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/products/sheepey-built") == "generic"


class TestProductUrlGuard:
    """
    Shape guard: any sheepeyrace.com or sheepeybuilt.com URL with ``/products/``
    in the path is a product page.
    """

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_legacy_host_is_product_shape(self) -> None:
        assert _is_product_url(LEGACY_URL)

    def test_bare_host_is_product_shape(self) -> None:
        assert _is_product_url("https://sheepeyrace.com/products/some-handle")

    def test_non_product_path_rejected(self) -> None:
        # Collections / CMS / cart pages do not have /products/ in the path.
        assert not _is_product_url("https://sheepeyrace.com/collections/intercoolers")
        assert not _is_product_url("https://sheepeyrace.com/pages/about-us")
        assert not _is_product_url("https://sheepeyrace.com/cart")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/products/foo")


class TestNormalizePartManufacturer:
    """
    Sheepey's Shopify vendor field is ``"SHEEPEYRACE"`` uppercase, but their
    catalog copy mixes ``"Sheepey Race"``, ``"Sheepey Built"``, and
    ``"Sheepey Inc"``. ``_normalize_part_manufacturer`` collapses all
    self-spellings to a single canonical brand without swallowing the rare
    co-branded third-party SKU.
    """

    def test_empty_brand_defaults_to_sheepey_race(self) -> None:
        assert _normalize_part_manufacturer("") == "Sheepey Race"
        assert _normalize_part_manufacturer(None) == "Sheepey Race"

    def test_sheepey_variants_all_collapse(self) -> None:
        for variant in (
            "SHEEPEYRACE",
            "Sheepey Race",
            "sheepey race",
            "sheepey-race",
            "Sheepey Built",
            "sheepey built",
            "sheepeybuilt",
            "Sheepey Inc",
            "Sheepey Inc.",
            "Sheepey, Inc.",
            "Sheepey",
        ):
            assert _normalize_part_manufacturer(variant) == "Sheepey Race", variant

    def test_third_party_brand_passes_through(self) -> None:
        # Rare, but Sheepey lists co-branded products. A JSON-LD brand that
        # isn't a Sheepey self-spelling must survive so the global
        # part-manufacturer table gets a real third-party row.
        assert _normalize_part_manufacturer("Daylight Performance") == "Daylight Performance"
        assert _normalize_part_manufacturer("Precision Turbo") == "Precision Turbo"

    def test_whitespace_around_variant_still_collapses(self) -> None:
        assert _normalize_part_manufacturer("  SHEEPEYRACE  ") == "Sheepey Race"


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape Shopify HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = SheepeyBuiltAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert "FORWARD FACING" in result.name
        assert result.part_manufacturer == "Sheepey Race"
        assert result.price_cents == 80000
        assert result.product_url == SAMPLE_URL
        assert result.image_urls and result.image_urls[0].startswith("https://sheepeyrace.com/cdn/shop/")

    def test_missing_brand_defaults_to_sheepey_race(self) -> None:
        # JSON-LD brand absent — the default kicks in rather than running the
        # title-first-word heuristic (which would pick up "SHEEPEYRACE" from
        # the title; defensive for product lines that lead with a hardware
        # descriptor like "FORWARD" or "K-SERIES").
        html = _product_html(brand="")
        result = SheepeyBuiltAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Sheepey Race"

    def test_brand_variant_collapsed_to_canonical(self) -> None:
        # Older SKUs still emit "Sheepey Built" as the vendor — must collapse
        # to the single canonical "Sheepey Race" row.
        html = _product_html(brand="Sheepey Built")
        result = SheepeyBuiltAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Sheepey Race"

    def test_third_party_brand_passed_through(self) -> None:
        html = _product_html(
            brand="Daylight Performance",
            name="Daylight Performance F150 Twin Turbo Kit [15-25]",
        )
        result = SheepeyBuiltAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Daylight Performance"

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape pipeline must not feed CMS/collection URLs here.
        result = SheepeyBuiltAdapter().parse_product_page(
            _product_html(),
            "https://sheepeyrace.com/collections/intercoolers",
        )
        assert result is None

    def test_legacy_sheepeybuilt_url_parses(self) -> None:
        # Archived HTML with the old sheepeybuilt.com URL still parses — the
        # product-URL guard accepts both hosts.
        result = SheepeyBuiltAdapter().parse_product_page(_product_html(), LEGACY_URL)
        assert result is not None
        assert result.product_url == LEGACY_URL or result.product_url.endswith("sidewinder-manifold")

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD — adapter should still pull title / description / price
        # from og: meta tags and default the manufacturer to Sheepey Race.
        html = """
        <html><head>
          <meta property="og:title" content="SHEEPEYRACE K-SERIES SIDEWINDER TURBO MANIFOLD">
          <meta property="og:description" content="Honda K-series sidewinder turbo manifold, Sheepey Built fabrication.">
          <meta property="og:image" content="https://sheepeyrace.com/cdn/shop/files/sidewinder.jpg">
          <meta property="product:price:amount" content="2495.00">
        </head><body>
          <h1>SHEEPEYRACE K-SERIES SIDEWINDER TURBO MANIFOLD</h1>
        </body></html>
        """
        result = SheepeyBuiltAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert "SIDEWINDER" in result.name
        assert result.part_manufacturer == "Sheepey Race"
        assert result.price_cents == 249500

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert SheepeyBuiltAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_empty_sku_label_does_not_leak_variant_label_as_part_number(self) -> None:
        # Real bug: every Audi RS3 / RS Q3 / TT-RS ECU page on this storefront
        # rendered the SKU sidebar as ``<p class="wt-product__sku">SKU:</p>``
        # (empty value) followed by a fuel-grade option labelled
        # ``FUEL: 93oct/98ron Gas …``. A page-wide ``SKU:`` regex captured
        # ``FUEL`` from the next visible word, tagging the entire catalog with
        # part_number='FUEL'. JSON-LD on these pages emits no ``sku`` (Shopify
        # variant-keyed offers), so the adapter falls back to the DOM SKU
        # element — which must return None when only the literal label is
        # present rather than reaching across whitespace into the next field.
        html = _product_html(
            name="AUDI RS3 2.5 TFSI STAGE 2 [ECU] [19-20]",
            brand="UNITRONIC",
            sku="",
        ).replace(
            "</body>",
            """
            <p class="wt-product__sku"><span class="visually-hidden">SKU:</span></p>
            <fieldset>
              <legend>FUEL: </legend>
              <label>93oct/98ron Gas</label>
              <label>91oct/95ron Gas</label>
            </fieldset>
            </body>
            """,
        )
        result = SheepeyBuiltAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert (
            result.part_number is None
        ), f"Expected no part_number when wt-product__sku is empty; got {result.part_number!r}"

    def test_real_sku_in_dom_element_is_extracted(self) -> None:
        # When the storefront actually populates ``.wt-product__sku``, the
        # numeric SKU must come through (this is the PT6466 / NEXT GEN
        # turbocharger case where the field is filled). JSON-LD lacks ``sku``
        # so this exercises the DOM-element fallback specifically.
        html = _product_html(
            name="NEXT GEN PT6466 SCP-COVER",
            brand="PRECISION TURBO",
            sku="",
        ).replace(
            "</body>",
            '<p class="wt-product__sku"><span class="visually-hidden">SKU:</span> 27304210139</p></body>',
        )
        result = SheepeyBuiltAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "27304210139"


class TestAdapterFetcherTier:
    """Sheepey starts on plain HTTP (tier0); promote to ``tls`` if Cloudflare fires."""

    def test_declares_http_tier(self) -> None:
        # Default tier — Sheepey's Shopify storefront is not TLS-fingerprint-
        # blocked today. If that changes, flip FETCHER_TIER to "tls".
        assert SheepeyBuiltAdapter.FETCHER_TIER == "http"
