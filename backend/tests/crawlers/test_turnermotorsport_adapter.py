"""Tests for turnermotorsport.com adapter: product URL pattern, malformed sitemap extraction, and microdata parsing."""

from app.crawlers.adapters.tier1_tls.turnermotorsport import (
    TurnerMotorsportAdapter,
    _extract_sitemap_index_children,
    _extract_urls_from_malformed_sitemap,
    _is_product_url,
)

SAMPLE_URL = "https://www.turnermotorsport.com/p-3-e46-m3-motorsport-thermostat-55-degree-c/"


def _product_html(
    *,
    h1: str = "Genuine BMW Motorsport BMW Motorsport Thermostat - 55C - E46 S54 3.2L ",
    brand: str = "Genuine BMW Motorsport",
    description: str = "E46 M3 Motorsport Thermostat, 55*C. Opens at a lower temperature than stock.",
    sku: str = "3",
    mpn_primary: str = "11531417215",
    mpn_dashed: str = "11-53-1-417-215",
    price: str = "206.99",
    currency: str = "USD",
    primary_image_id: str = "812277",
    gallery_image_ids: tuple[str, ...] = ("812277", "388266", "388267", "1058393"),
) -> str:
    """Minimal HTML that mirrors Turner's microdata shape: no JSON-LD, itemprop everywhere."""
    og_title = h1.strip()
    og_image = f"https://assets.turnermotorsport.com/product_library_tms/{primary_image_id}_x600.jpg"
    carousel_items = "".join(f"""
        <div class="carousel-item">
          <link itemprop="image" href="https://assets.turnermotorsport.com/product_library_tms/{gid}_x800.jpg" />
          <picture>
            <source type="image/webp" data-lazy-srcset="https://assets.turnermotorsport.com/product_library_tms/{gid}_x600.webp">
            <img src="https://assets.turnermotorsport.com/product_library_tms/{gid}_x600.jpg">
          </picture>
        </div>
        """ for gid in gallery_image_ids)
    return f"""
    <html><head>
      <meta property="og:title" content="{og_title}">
      <meta property="og:image" content="{og_image}">
      <meta property="og:description" content="Generic OG marketing blurb, should not win.">
    </head><body>
      <h1>{h1}</h1>
      <div class="d-none" itemprop="description">{description}</div>
      <meta itemprop="brand" content="{brand}" />
      <!-- Brand logo: must NOT be scraped as a product image -->
      <img src="https://assets.turnermotorsport.com/static/img/brands/{brand}.gif">
      <div class="product-numbers">
        <span itemprop="sku">{sku}</span>
        <span itemprop="mpn" class="js-partnumber">{mpn_primary}</span>
        <span itemprop="mpn">{mpn_dashed}</span>
      </div>
      <div itemprop="offers" itemscope itemtype="http://schema.org/Offer">
        <link itemprop="availability" href="http://schema.org/InStock" />
        <meta content="{currency}" itemprop="priceCurrency">
        <span class="d-none" itemprop="price">{price}</span>
      </div>
      {carousel_items}
    </body></html>
    """


class TestProductUrlRegex:
    """Product URL gate. Used to filter sitemap entries and to reject non-product URLs fed into parse_product_page."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_trailing_slash_optional(self) -> None:
        assert _is_product_url("https://www.turnermotorsport.com/p-33-afe-pro5r-filter")

    def test_numeric_id_required(self) -> None:
        # /b-<brand-slug>/... was Turner's old SEO URL shape and currently 404s;
        # we only crawl the /p-<digits>- pattern the sitemap ships.
        assert not _is_product_url("https://www.turnermotorsport.com/b-afe/some-product/")
        assert not _is_product_url("https://www.turnermotorsport.com/category/brakes/")
        assert not _is_product_url("https://www.turnermotorsport.com/p-foo-bar/")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/p-3-foo/")


class TestMalformedSitemap:
    """
    Turner child sitemaps have every closing tag URL-encoded into the URL
    body (``</loc>`` → ``%3C%2Floc%3E``, ``/`` → ``%2F``). Standard XML parsers
    raise 'mismatched tag', so we extract via regex and URL-decode.
    """

    def test_extracts_and_decodes_urls(self) -> None:
        body = (
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://www.turnermotorsport.com/p-3-e46-m3-motorsport-thermostat-55-degree-c"
            "%2F%3C%2Floc%3E%3Clastmod%3E2025-12-17%3C%2Flastmod%3E%3C%2Furl%3E"
            "<url><loc>https://www.turnermotorsport.com/p-33-afe-performance-pro5r-air-filter"
            "%2F%3C%2Floc%3E%3Clastmod%3E2026-03-23%3C%2Flastmod%3E%3C%2Furl%3E"
        )
        urls = _extract_urls_from_malformed_sitemap(body)
        assert urls == [
            "https://www.turnermotorsport.com/p-3-e46-m3-motorsport-thermostat-55-degree-c/",
            "https://www.turnermotorsport.com/p-33-afe-performance-pro5r-air-filter/",
        ]

    def test_skips_non_product_paths(self) -> None:
        body = (
            "<url><loc>https://www.turnermotorsport.com/about-us"
            "%2F%3C%2Floc%3E%3Clastmod%3E2024-01-01%3C%2Flastmod%3E%3C%2Furl%3E"
            "<url><loc>https://www.turnermotorsport.com/p-8-manual-bmw-shift-knob-anatomic"
            "%2F%3C%2Floc%3E%3Clastmod%3E2024-01-01%3C%2Flastmod%3E%3C%2Furl%3E"
        )
        assert _extract_urls_from_malformed_sitemap(body) == [
            "https://www.turnermotorsport.com/p-8-manual-bmw-shift-knob-anatomic/",
        ]

    def test_index_lists_child_sitemaps(self) -> None:
        index = (
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<sitemap><loc>https://www.turnermotorsport.com/sitemap_product_0.xml</loc></sitemap>"
            "<sitemap><loc>https://www.turnermotorsport.com/sitemap_product_1.xml</loc></sitemap>"
            "</sitemapindex>"
        )
        children = _extract_sitemap_index_children(index)
        assert children == [
            "https://www.turnermotorsport.com/sitemap_product_0.xml",
            "https://www.turnermotorsport.com/sitemap_product_1.xml",
        ]


class TestParseProductPage:
    """End-to-end: real-shape microdata HTML → ScrapedPayload."""

    def test_full_page_parses_from_microdata(self) -> None:
        result = TurnerMotorsportAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Genuine BMW Motorsport BMW Motorsport Thermostat")
        # H1 has a trailing space on Turner pages — make sure we strip it.
        assert not result.name.endswith(" ")
        assert result.part_manufacturer == "Genuine BMW Motorsport"
        # First itemprop=mpn wins — the clean, non-dashed form.
        assert result.part_number == "11531417215"
        assert result.price_cents == 20699
        # itemprop=description wins over og:description.
        assert result.description and "Thermostat" in result.description
        assert "Generic OG marketing blurb" not in result.description
        assert result.product_url == SAMPLE_URL

    def test_never_uses_turner_internal_sku_as_part_number(self) -> None:
        # itemprop="sku" is Turner's T# (``3``, ``33``) — an internal id that
        # also appears in the URL path. We must use itemprop="mpn" instead so
        # dedupe across retailers works against real MPNs.
        result = TurnerMotorsportAdapter().parse_product_page(_product_html(sku="3"), SAMPLE_URL)
        assert result is not None
        assert result.part_number != "3"

    def test_house_brand_passes_through(self) -> None:
        # Turner-house-branded SKUs carry itemprop="brand" content="Packaged by Turner"
        # — pass through so the listing is still attributed, even though there's
        # no cross-retailer arbitrage on these.
        html = _product_html(brand="Packaged by Turner", mpn_primary="E46M3HEADERKIT")
        result = TurnerMotorsportAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Packaged by Turner"
        assert result.part_number == "E46M3HEADERKIT"

    def test_image_gallery_deduped_by_id_and_prefers_jpg(self) -> None:
        result = TurnerMotorsportAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        # Distinct image IDs only; no webp/variant-size duplicates.
        ids = [u.rsplit("/", 1)[1].split("_", 1)[0] for u in result.image_urls]
        assert ids == ["812277", "388266", "388267", "1058393"]
        # Prefer jpg over webp.
        assert all(u.endswith(".jpg") for u in result.image_urls)
        # og:image (id 812277) seeds the first slot; within an id we keep the
        # largest jpg we saw, so _x800 wins over _x600 from the carousel link.
        assert result.image_urls[0].endswith("812277_x800.jpg")

    def test_brand_logo_filtered_from_images(self) -> None:
        # assets.turnermotorsport.com/static/img/brands/<Brand>.gif must not
        # leak into the product gallery — it's retailer chrome, not product photography.
        result = TurnerMotorsportAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        assert all("/static/img/brands/" not in u for u in result.image_urls)

    def test_non_product_url_returns_none(self) -> None:
        # Guard: archive rescrape pipeline must not run category pages through
        # this adapter just because the host matches.
        result = TurnerMotorsportAdapter().parse_product_page(
            _product_html(),
            "https://www.turnermotorsport.com/category/brakes/",
        )
        assert result is None

    def test_missing_name_returns_none(self) -> None:
        html = "<html><body><p>Out of stock.</p></body></html>"
        assert TurnerMotorsportAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """Turner must declare the TLS fetcher tier — Cloudflare blocks plain requests."""

    def test_declares_tls_tier(self) -> None:
        assert TurnerMotorsportAdapter.FETCHER_TIER == "tls"
