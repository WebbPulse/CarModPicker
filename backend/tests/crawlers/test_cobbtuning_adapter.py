"""
Tests for cobbtuning.com adapter: URL shape guard, registration, fetcher tier,
JSON-LD parse, DOM fallback, and the COBB-Tuning manufacturer default.

Cobb migrated the storefront from Magento 2's ``/<slug>.html`` URL scheme to a
WordPress-fronted Magento 2 hybrid where products live at
``/products/<category>/<slug>`` or ``/products/<slug>`` and no longer emit
JSON-LD. Legacy ``.html`` URLs now 404. These tests cover both the shape guard
updates and the post-migration DOM fallback.

Cobb is behind Cloudflare-style bot protection (see
``site_problem_notes/cobbtuning.md``); we have not captured a real product page
yet. These tests run against *synthetic* HTML modeled on the post-migration
Cobb product template (h1-based name, og meta, media-path image filename).
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier1_tls.cobbtuning import (
    CobbTuningAdapter,
    _extract_products_href,
    _extract_sku_from_image_urls,
    _extract_sku_from_name_parens,
    _is_product_url,
    _strip_site_prefix,
)

SAMPLE_URL = "https://www.cobbtuning.com/products/accessport/accessport-for-subaru-wrx-sti-2015-2021"


def _product_html(
    *,
    name: str = "COBB AccessPORT V3 Subaru WRX/STI 2015-2021",
    brand: str = "COBB Tuning",
    sku: str = "AP3-SUB-002",
    price: str = "775.00",
    description: str = "AccessPORT V3 handheld tuner for 2015-2021 Subaru WRX and STI.",
    image: str = "https://www.cobbtuning.com/media/catalog/product/a/p/ap3-sub-002.jpg",
) -> str:
    """
    Minimal page with JSON-LD Product. The legacy Magento 2 pages emitted this;
    kept for coverage because archive rescrape may still replay old captures.
    """
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


def _post_migration_product_html(
    *,
    site_title: str = "COBB Tuning - Redline Carbon Fiber Radiator Shroud 2017-2020 Gen2 Raptor",
    product_heading: str = "Redline Carbon Fiber Radiator Shroud for Ford F-150 Ecoboost Raptor 2017-2020",
    sku: str = "4F2660",
    description: str = "The Redline Carbon Fiber Radiator Shroud for the 2017-2020 Ford Raptor is constructed of carbon fiber.",
) -> str:
    """
    Minimal page modelling the post-migration Cobb product template: a generic
    ``<h1 class="page-title">COBB Tuning - Products</h1>`` site header plus a
    product-specific ``<h1 class="product--heading">`` with the real name, no
    JSON-LD, SKU carried only by the image filename, and a tracking pixel
    mixed into the ``<img>`` tags.
    """
    image_url = f"https://www.cobbtuning.com/media/catalog/products/resized/{sku}_main.jpg"
    return f"""
    <html><head>
      <meta property="og:title" content="{site_title}">
      <meta property="og:description" content="{description}">
      <meta property="og:image" content="{image_url}">
      <meta name="description" content="{description}">
    </head><body>
      <h1 class="page-title">COBB Tuning - Products</h1>
      <div class="product-wrap">
        <h1 class="product--heading text--center-mobile">{product_heading}</h1>
        <img src="{image_url}">
        <img src="https://www.cobbtuning.com/wp/content/themes/cobb/assets/images/COBB_Tuning_logo_white.svg">
        <img src="https://www.facebook.com/tr?id=12345&ev=PageView&noscript=1">
      </div>
    </body></html>
    """


class TestAdapterRegistration:
    """The host-to-adapter map routes every cobbtuning.com page through this adapter."""

    def test_host_maps_to_cobbtuning(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "cobbtuning"

    def test_bare_host_also_maps(self) -> None:
        assert adapter_name_for_product_url("https://cobbtuning.com/products/exhaust/some-slug") == "cobbtuning"

    def test_unrelated_host_does_not_map(self) -> None:
        assert adapter_name_for_product_url("https://example.com/products/x/y") != "cobbtuning"


class TestProductUrlRegex:
    """
    Shape guard for post-migration Cobb URLs. The guard accepts both 2-level
    ``/products/<category>/<slug>`` URLs (bulk of the catalog) and 1-level
    ``/products/<slug>`` URLs (featured SKUs). Category index pages like
    ``/products/exhaust`` also match the shape and get filtered later by the
    parser when the page turns out to be a category grid rather than a product.
    """

    def test_valid_two_level_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_valid_one_level_product_url(self) -> None:
        assert _is_product_url("https://www.cobbtuning.com/products/radiator-shroud-for-ford-raptor")

    def test_query_string_rejected(self) -> None:
        # robots.txt disallows /*? — any URL with a query string is off limits.
        assert not _is_product_url(SAMPLE_URL + "?utm_source=x")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/products/x/y")

    def test_legacy_magento_html_path_rejected(self) -> None:
        # Old Magento URLs all 404 now — the shape guard should reject so
        # archive-rescrape doesn't replay them against the live site.
        assert not _is_product_url("https://www.cobbtuning.com/accessport-v3.html")
        assert not _is_product_url("https://www.cobbtuning.com/about-us.html")
        assert not _is_product_url("https://www.cobbtuning.com/warranty.html")

    def test_catalog_root_rejected(self) -> None:
        # ``/products`` (and trailing-slash variant) is the catalog root, not a
        # product. Discovery surfaces this from the homepage; the guard must
        # drop it so we don't try to parse it as a product.
        assert not _is_product_url("https://www.cobbtuning.com/products")
        assert not _is_product_url("https://www.cobbtuning.com/products/")

    def test_too_deep_path_rejected(self) -> None:
        # Three-plus segment paths under /products/ aren't a real URL shape.
        assert not _is_product_url("https://www.cobbtuning.com/products/exhaust/cat-backs/some-slug")


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

    def test_post_migration_page_parses_via_dom(self) -> None:
        # The new Cobb storefront emits no JSON-LD and hydrates price/SKU
        # client-side. The adapter must still extract a clean name (from the
        # product-specific <h1>, not the "COBB Tuning - Products" page header
        # h1 nor the site-prefixed og:title) and recover the SKU from the
        # ``<SKU>_main.jpg`` image filename convention.
        url = "https://www.cobbtuning.com/products/cooling/redline-carbon-fiber-radiator-shroud"
        result = CobbTuningAdapter().parse_product_page(_post_migration_product_html(), url)
        assert result is not None
        assert result.name == "Redline Carbon Fiber Radiator Shroud for Ford F-150 Ecoboost Raptor 2017-2020"
        assert result.part_manufacturer == "COBB Tuning"
        assert result.part_number == "4F2660"
        # Price is hydrated client-side; server HTML carries nothing usable.
        assert result.price_cents is None
        # Tracking pixel and site logo must be filtered out; only the real
        # catalog image remains.
        assert result.image_urls is not None
        assert all("facebook.com" not in u for u in result.image_urls)
        assert all("COBB_Tuning_logo" not in u for u in result.image_urls)
        assert any("/media/catalog/products/" in u for u in result.image_urls)

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD, no product-heading h1 — only og tags. The adapter strips
        # the "COBB Tuning - " site prefix from og:title when falling back to it.
        html = """
        <html><head>
          <meta property="og:title" content="COBB Tuning - Stage 1+ Power Package WRX 2015-2021">
          <meta property="og:description" content="Stage 1+ software + SF intake for WRX 2015-2021.">
          <meta property="og:image" content="https://www.cobbtuning.com/media/catalog/products/600X50-WRX_main.jpg">
          <meta property="product:price:amount" content="1295.00">
        </head><body>
          <p>SKU: 600X50-WRX</p>
        </body></html>
        """
        result = CobbTuningAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        # "COBB Tuning - " prefix must be stripped; the real product name wins.
        assert result.name == "Stage 1+ Power Package WRX 2015-2021"
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
          <meta property="og:image" content="https://www.cobbtuning.com/media/catalog/products/ap3_main.jpg">
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


class TestDiscoveryHelpers:
    """Unit coverage for the category-crawl discovery primitives."""

    def test_extract_products_href_collects_and_dedupes(self) -> None:
        html = """
        <a href="/products/exhaust">Exhaust</a>
        <a href="/products/exhaust/">Exhaust (trailing slash)</a>
        <a href="/products/exhaust/ford-cat-back-exhaust">Ford Cat-back</a>
        <a href="https://www.cobbtuning.com/products/accessport/ap-for-subaru">Absolute URL</a>
        <a href="/about">About</a>
        <a href="/products/exhaust?utm=x">With query</a>
        """
        hrefs = _extract_products_href(html)
        # Dedupe: /products/exhaust and /products/exhaust/ collapse to one entry.
        assert "https://www.cobbtuning.com/products/exhaust" in hrefs
        assert "https://www.cobbtuning.com/products/exhaust/ford-cat-back-exhaust" in hrefs
        assert "https://www.cobbtuning.com/products/accessport/ap-for-subaru" in hrefs
        # Non-/products/ anchors and query-string URLs (regex has ``[^"#?]+``
        # for the href body, so a "?" in the href terminates the match) are
        # not surfaced.
        assert not any("about" in h for h in hrefs)
        assert not any("utm" in h for h in hrefs)

    def test_strip_site_prefix_handles_common_separators(self) -> None:
        assert _strip_site_prefix("COBB Tuning - Radiator Shroud") == "Radiator Shroud"
        assert _strip_site_prefix("COBB Tuning | Accessport") == "Accessport"
        assert _strip_site_prefix("Accessport V3 Flash Tuner") == "Accessport V3 Flash Tuner"

    def test_extract_sku_from_image_urls(self) -> None:
        # Cobb's image filename convention is the SKU carrier of last resort.
        urls = [
            "https://www.cobbtuning.com/media/catalog/products/resized/4F2660_main.jpg",
            "https://www.cobbtuning.com/wp/content/themes/cobb/logo.svg",
        ]
        assert _extract_sku_from_image_urls(urls) == "4F2660"

        # No catalog image in list → None.
        assert _extract_sku_from_image_urls(["https://www.cobbtuning.com/logo.svg"]) is None

    def test_extract_sku_from_name_parens_picks_up_accessport_skus(self) -> None:
        # Every Accessport variant carries its SKU in the trailing parens.
        # Cobb's post-migration pages emit no JSON-LD and the image-URL
        # convention only fires for products whose hero image is named after
        # the SKU; this fallback covers the rest.
        assert _extract_sku_from_name_parens("Mitsubishi Accessport V3 (AP3-MIT-002)") == "AP3-MIT-002"
        assert (
            _extract_sku_from_name_parens("Nissan GT-R Accessport V3 (AP3-NIS-006)  w/TCM Flashing")
            == "AP3-NIS-006"
        )
        # Multi-segment international SKU shape ``AP3-AU-SUB-NNN``.
        assert (
            _extract_sku_from_name_parens("Subaru International Accessport V3 (AP3-AU-SUB-006)")
            == "AP3-AU-SUB-006"
        )

    def test_extract_sku_from_name_parens_ignores_chassis_and_year_tokens(self) -> None:
        # Parenthesised chassis codes and bare numerics must NOT become SKUs.
        # Accessport titles for Mk7/Mk7.5 platforms embed multiple ``(Mk7)``
        # / ``(8V)`` parens that would pollute part_number if grabbed naively.
        assert (
            _extract_sku_from_name_parens(
                "Accessport for Volkswagen (Mk7) Golf, (Mk7/Mk7.5) GTI, Audi A3 (8V)"
            )
            is None
        )
        assert _extract_sku_from_name_parens("Subaru Accessport V3 WRX 6MT / CVT 2022-2025") is None
        # All-digit year/displacement parens are also rejected — the regex
        # requires an alpha lead character.
        assert _extract_sku_from_name_parens("Some Product (2024)") is None
        assert _extract_sku_from_name_parens(None) is None
        assert _extract_sku_from_name_parens("") is None

    def test_post_migration_sku_in_name_recovered_when_image_filename_misses(self) -> None:
        # Real-world shape from Cobb's Accessport pages: hero image is named
        # ``accessport_v3_<vehicle>.jpg`` (no SKU), so the image-filename
        # fallback misses. The product name's parenthesised SKU is what
        # actually survives the migration. This is the core regression this
        # fallback was added to fix — without it, every Accessport variant
        # ingests with part_number=NULL.
        html = """
        <html><head>
          <meta property="og:title" content="COBB Tuning - Mitsubishi Accessport V3">
          <meta property="og:description" content="Accessport V3 for Mitsubishi.">
          <meta property="og:image" content="https://www.cobbtuning.com/media/catalog/products/accessport_v3_mitsubishi.jpg">
        </head><body>
          <h1 class="page-title">COBB Tuning - Products</h1>
          <h1 class="product--heading">Mitsubishi Accessport V3 (AP3-MIT-002)</h1>
          <img src="https://www.cobbtuning.com/media/catalog/products/accessport_v3_mitsubishi.jpg">
        </body></html>
        """
        url = "https://www.cobbtuning.com/products/accessport/mitsubishi-accessport-v3-ap3-mit-002"
        result = CobbTuningAdapter().parse_product_page(html, url)
        assert result is not None
        assert result.name == "Mitsubishi Accessport V3 (AP3-MIT-002)"
        assert result.part_number == "AP3-MIT-002"
        assert result.part_manufacturer == "COBB Tuning"


class TestAdapterFetcherTier:
    """Cobb declares the TLS fetcher tier so the runner hands it curl_cffi."""

    def test_declares_tls_tier(self) -> None:
        assert CobbTuningAdapter.FETCHER_TIER == "tls"
