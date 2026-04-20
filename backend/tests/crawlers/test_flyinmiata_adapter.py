"""
Tests for flyinmiata.com adapter: host routing, URL shape guard, JSON-LD
parsing (including the broken-``gtin13`` wart seen on a subset of product
pages), ``var meta`` fallback, and en-ca locale filtering during discovery.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.flyinmiata import (
    _BROKEN_GTIN_RE,
    FlyinMiataAdapter,
    _is_en_ca_locale_url,
    _is_product_url,
    _sanitize_json_ld,
)

SAMPLE_URL = "https://flyinmiata.com/products/mazda-competition-motor-mount"
# Real pages emit JSON-LD / og:image / og:image:secure_url all on the
# customer domain (``flyinmiata.com/cdn/shop/...``); cross-domain CDN URLs
# would be a sitemap-only artifact and shouldn't appear in the test fixture.
SAMPLE_IMAGE = (
    "https://flyinmiata.com/cdn/shop/products/"
    "04-70155_na_nb_mazda_comp_motor_mount_090221-4.jpg?v=1657921950&width=1920"
)


def _product_html(
    *,
    name: str = "Mazda Competition engine mount",
    vendor: str = "Mazda North American Operation",
    sku: str = "04-70155",
    price_dollars: float = 119.0,
    variant_price_cents: int = 11900,
    description: str = "Stiffer 40% rubber engine mount for NA/NB Miatas.",
    broken_gtin: bool = False,
    include_json_ld: bool = True,
    include_meta_var: bool = True,
    og_title_tagline: str = "Stiffer motor mount for high-power engines.",
) -> str:
    """
    Synthetic page modeled on a real flyinmiata.com product. ``broken_gtin``
    reproduces the real wart (unquoted raw token) seen on a subset of pages.
    ``og_title`` on this theme is the SEO tagline, not the product name —
    modelled here so fallback tests don't accidentally pick it up.
    """
    gtin_field = ""
    if broken_gtin:
        # Real wart: unquoted token with spaces, breaks json.loads.
        gtin_field = '"gtin13": NAY139040   Q,'

    json_ld = ""
    if include_json_ld:
        json_ld = f"""
        <script type="application/ld+json">
          {{
            "@context": "http://schema.org/",
            "@type": "Product",
            "name": "{name}",
            "url": "{SAMPLE_URL}",
            "image": ["{SAMPLE_IMAGE}"],
            "description": "{description}",
            "sku": "{sku}",
            "brand": {{"@type": "Brand", "name": "{vendor}"}},
            "offers": [{{
              "@type": "Offer",
              "sku": "{sku}",
              {gtin_field}
              "availability": "http://schema.org/InStock",
              "price": {price_dollars},
              "priceCurrency": "USD",
              "url": "{SAMPLE_URL}?variant=123"
            }}]
          }}
        </script>
        """

    meta_var = ""
    if include_meta_var:
        meta_var = (
            f'<script>var meta = {{"product":{{"id":1,"vendor":"{vendor}",'
            f'"handle":"mazda-competition-motor-mount","variants":'
            f'[{{"id":1,"price":{variant_price_cents},"name":"{name}","sku":"{sku}"}}]}}}};'
            f"</script>"
        )

    return f"""
    <html><head>
      <meta property="og:type" content="product">
      <meta property="og:title" content="{og_title_tagline}">
      <meta property="og:description" content="Short tagline (not the product description).">
      <meta property="og:image" content="http://flyinmiata.com/cdn/shop/products/04-70155_na_nb_mazda_comp_motor_mount_090221-4.jpg?v=1657921950">
      <meta property="og:image:secure_url" content="https://flyinmiata.com/cdn/shop/products/04-70155_na_nb_mazda_comp_motor_mount_090221-4.jpg?v=1657921950">
      <meta property="og:price:amount" content="{price_dollars:.2f}">
      <meta property="og:price:currency" content="USD">
      {meta_var}
      {json_ld}
    </head><body>
      <h1>{name}</h1>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-to-adapter routing covers the apex and any www subdomain."""

    def test_apex_routes_to_flyinmiata(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "flyinmiata"

    def test_www_subdomain_routes_to_flyinmiata(self) -> None:
        assert adapter_name_for_product_url("https://www.flyinmiata.com/products/foo") == "flyinmiata"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/products/foo") == "generic"


class TestProductUrlGuard:
    """Any flyinmiata host URL with ``/products/`` in the path is a product page."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_non_product_path_rejected(self) -> None:
        # Collections / CMS / cart pages don't live under /products/.
        assert not _is_product_url("https://flyinmiata.com/collections/suspension")
        assert not _is_product_url("https://flyinmiata.com/pages/about")
        assert not _is_product_url("https://flyinmiata.com/cart")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/products/foo")


class TestLocaleFilter:
    """``/en-ca/`` mirror is filtered out so we don't double-crawl the catalog."""

    def test_en_ca_locale_detected(self) -> None:
        assert _is_en_ca_locale_url("https://flyinmiata.com/en-ca/products/foo")
        assert _is_en_ca_locale_url("https://flyinmiata.com/en-ca/sitemap_products_1.xml")

    def test_canonical_locale_passes(self) -> None:
        assert not _is_en_ca_locale_url("https://flyinmiata.com/products/foo")
        assert not _is_en_ca_locale_url("https://flyinmiata.com/sitemap_products_1.xml")


class TestBrokenGtinSanitizer:
    """Malformed ``gtin13`` offers break ``json.loads`` — sanitize them out."""

    def test_removes_unquoted_gtin_token(self) -> None:
        raw = '"sku": "04-70155","gtin13": NAY139040   Q,"availability": "InStock"'
        cleaned = _BROKEN_GTIN_RE.sub("", raw)
        assert '"gtin' not in cleaned
        assert '"sku": "04-70155","availability": "InStock"' in cleaned

    def test_preserves_valid_quoted_gtin(self) -> None:
        raw = '"gtin13": "012345678905","price": 119'
        assert _BROKEN_GTIN_RE.sub("", raw) == raw

    def test_preserves_valid_numeric_gtin(self) -> None:
        raw = '"gtin13": 12345,"price": 119'
        assert _BROKEN_GTIN_RE.sub("", raw) == raw

    def test_sanitizer_is_noop_when_no_gtin_present(self) -> None:
        html = "<html><body>no gtin here</body></html>"
        assert _sanitize_json_ld(html) is html


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape FM HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = FlyinMiataAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "Mazda Competition engine mount"
        assert result.part_manufacturer == "Mazda North American Operation"
        assert result.part_number == "04-70155"
        assert result.price_cents == 11900
        assert result.product_url == SAMPLE_URL
        # og:image and og:image:secure_url collapse onto one canonical URL
        # after the ``v=`` and ``width=`` query params are stripped.
        assert result.image_urls and len(result.image_urls) == 1

    def test_broken_gtin_offer_still_parses(self) -> None:
        # Real wart: ``"gtin13": NAY139040   Q,`` — unquoted token breaks
        # json.loads. Adapter must sanitize and recover the Product block.
        result = FlyinMiataAdapter().parse_product_page(_product_html(broken_gtin=True), SAMPLE_URL)
        assert result is not None
        assert result.name == "Mazda Competition engine mount"
        assert result.part_number == "04-70155"
        assert result.price_cents == 11900
        assert result.part_manufacturer == "Mazda North American Operation"

    def test_third_party_vendor_passes_through(self) -> None:
        # FM resells IL Motorsports / Racing Beat / Koni hardware under the
        # real brand — the vendor string survives verbatim.
        result = FlyinMiataAdapter().parse_product_page(
            _product_html(vendor="IL Motorsports", name="IL Motorsport mount pair"),
            SAMPLE_URL,
        )
        assert result is not None
        assert result.part_manufacturer == "IL Motorsports"

    def test_missing_json_ld_falls_back_to_meta_var(self) -> None:
        # Older/newer theme variant without JSON-LD. Adapter recovers name
        # from the variant name in ``var meta`` (og:title is SEO tagline,
        # not usable as a name source), price from variant.price, SKU from
        # variant.sku, vendor from product.vendor.
        html = _product_html(include_json_ld=False)
        result = FlyinMiataAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name == "Mazda Competition engine mount"
        assert result.part_number == "04-70155"
        assert result.price_cents == 11900
        assert result.part_manufacturer == "Mazda North American Operation"

    def test_missing_json_ld_and_meta_var_falls_back_to_h1(self) -> None:
        # No JSON-LD, no meta var — last-resort name source is <h1>. Price
        # lands from og:price:amount; SKU is unrecoverable.
        html = _product_html(include_json_ld=False, include_meta_var=False)
        result = FlyinMiataAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name == "Mazda Competition engine mount"
        assert result.price_cents == 11900
        assert result.part_number is None

    def test_og_title_not_used_as_name(self) -> None:
        # Regression: og:title on this theme is the SEO tagline (e.g.
        # "Stiffer motor mount for high-power engines."), not the product
        # name. The adapter must prefer JSON-LD / variant name / h1 over it.
        html = _product_html(
            og_title_tagline="SEO TAGLINE THAT IS NOT THE NAME",
        )
        result = FlyinMiataAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert "TAGLINE" not in (result.name or "")
        assert result.name == "Mazda Competition engine mount"

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape pipeline must not feed CMS / collection URLs here.
        result = FlyinMiataAdapter().parse_product_page(
            _product_html(),
            "https://flyinmiata.com/collections/suspension",
        )
        assert result is None

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert FlyinMiataAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_draft_product_without_prices_keeps_name(self) -> None:
        # "Call for quote" products have variants but no positive integer
        # prices. Name / SKU / brand still land; price is None.
        html = _product_html(
            include_json_ld=False,
            variant_price_cents=0,
        ).replace('content="119.00"', 'content=""')
        result = FlyinMiataAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name == "Mazda Competition engine mount"
        assert result.part_number == "04-70155"
        assert result.price_cents is None


class TestAdapterFetcherTier:
    """flyinmiata.com works on plain HTTP (tier0)."""

    def test_declares_http_tier(self) -> None:
        # Shopify-hosted, Cloudflare passive for non-browser clients — plain
        # ``requests`` + crawler UA returns 200 on robots.txt, sitemap, and
        # product pages.
        assert FlyinMiataAdapter.FETCHER_TIER == "http"
