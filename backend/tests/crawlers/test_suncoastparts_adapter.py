"""Tests for suncoastparts.com adapter: product URL pattern, sitemap parsing, and Miva OG+gallery parsing."""

from app.crawlers.adapters.tier1_tls.suncoastparts import (
    SuncoastPartsAdapter,
    _extract_gallery_urls_from_js,
    _extract_product_urls_from_sitemap,
    _is_product_url,
    _normalize_graphics_url,
    _sku_from_url,
)

SAMPLE_URL = "https://www.suncoastparts.com/product/99755922100041.html"


def _product_html(
    *,
    # Suncoast HTML-escapes embedded double quotes in OG meta as ``&quot;`` —
    # the default fixture mirrors the real ``Emblem - "Speedster" in Black``
    # page source so parsing-side entity decoding gets exercised.
    og_title_raw: str = "Emblem - &quot;Speedster&quot; in Black",
    og_title_decoded: str = 'Emblem - "Speedster" in Black',
    og_brand: str = "Porsche",
    og_image: str = "https://www.suncoastparts.com/mm5/graphics/00000002/9/porsche%20speedster%20emblem.jpg",
    price_amount: str = "239",
    price_currency: str = "USD",
    availability: str = "instock",
    meta_description: str = (
        "Each emblem comes ready for installation, with adhesive on the backside. "
        "These emblems will fit any car, but is intended for the 2011 Speedster model."
    ),
    sku_span: str = "SKU: 99755922100041",
    main_image_data: str = "graphics/00000002/9/porsche speedster emblem.jpg",
    image_data_var_n: str = "12",
    gallery_paths: tuple[str, ...] = (
        "graphics/00000002/9/porsche speedster emblem.jpg",
        "graphics/00000002/9/porsche speedster emblem detail.jpg",
    ),
) -> str:
    """Minimal HTML that mirrors Suncoast's Miva shape: no JSON-LD Product, OG + image_data JS."""
    # Build the image_data JS array with (full, thumb, zoom) per entry.
    entries = ",".join(
        f'{{"type_code":"img{i}","image_data":["{path}","{path.rsplit(".",1)[0]}_80x51.jpg","{path}"]}}'
        for i, path in enumerate(gallery_paths)
    )
    return f"""
    <html><head>
      <meta property="og:title" content="{og_title_raw}">
      <meta property="og:type" content="product">
      <meta property="og:brand" content="{og_brand}">
      <meta property="og:image" content="{og_image}">
      <meta property="og:description" content="Check out the deal on {og_title_raw} at Suncoast Porsche Parts &amp; Accessories">
      <meta property="product:price:amount" content="{price_amount}">
      <meta property="product:price:currency" content="{price_currency}">
      <meta property="og:availability" content="{availability}">
      <meta name="description" content="{meta_description}">
    </head><body>
      <h1>{og_title_decoded}<span class="x-product-layout-purchase__productcode x-product-layout-purchase__sku">{sku_span}</span></h1>
      <figure>
        <div class="x-fasten-PROD_gallery">
          <div class="x-fasten-PROD_gallery-row">
            <span id="js-main-image-zoom" class="main-image" data-index="0">
              <img src="graphics/en-US/cssui/blank.gif" alt="{og_title_raw}" id="js-main-image" data-image="{main_image_data}" />
            </span>
          </div>
          <script type="text/javascript">var image_data{image_data_var_n} = [
          {entries}
          ]
          var im1 = new ImageMachine('SKU',0,'js-main-image','js-thumbnails','','','','', 'B',640,640,1,'B',960,960,1,80,80,1,'');
          </script>
        </div>
      </figure>
    </body></html>
    """


class TestProductUrlRegex:
    """Product URL gate. Filters sitemap entries and blocks category/legacy URLs from parse_product_page."""

    def test_valid_numeric_sku_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_valid_alphanumeric_sku_url(self) -> None:
        # Internal Suncoast codes (POHC, SGP996, SKURSTRACK) are also valid product URLs.
        assert _is_product_url("https://www.suncoastparts.com/product/POHC.html")
        assert _is_product_url("https://www.suncoastparts.com/product/SGP996.html")
        assert _is_product_url("https://www.suncoastparts.com/product/SKURSTRACK.html")

    def test_rejects_legacy_miva_query_url(self) -> None:
        # /mm5/merchant.mvc?Screen=PROD&Product_Code=X is the legacy Miva URL
        # shape and appears in the sitemap alongside canonical URLs. It
        # redirects to /product/<SKU>.html, so we must not crawl it directly
        # (would double-count and fail dedupe).
        assert not _is_product_url("https://www.suncoastparts.com/mm5/merchant.mvc?Screen=PROD&Product_Code=POHC")

    def test_rejects_category_and_non_product_paths(self) -> None:
        assert not _is_product_url("https://www.suncoastparts.com/category/brakes.html")
        assert not _is_product_url("https://www.suncoastparts.com/product/")
        assert not _is_product_url("https://www.suncoastparts.com/product/POHC")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/product/POHC.html")


class TestSkuFromUrl:
    """URL stem is the retailer SKU — authoritative part_number source."""

    def test_extracts_numeric_oem_mpn(self) -> None:
        assert _sku_from_url(SAMPLE_URL) == "99755922100041"

    def test_extracts_internal_code(self) -> None:
        assert _sku_from_url("https://www.suncoastparts.com/product/SKURSTRACK.html") == "SKURSTRACK"

    def test_returns_none_for_non_product_url(self) -> None:
        assert _sku_from_url("https://www.suncoastparts.com/category/brakes.html") is None


class TestNormalizeGraphicsUrl:
    """Miva graphics paths carry spaces — must be URL-quoted before emit."""

    def test_relative_path_with_spaces_becomes_absolute_and_quoted(self) -> None:
        result = _normalize_graphics_url("graphics/00000002/9/porsche speedster emblem.jpg")
        assert result == "https://www.suncoastparts.com/graphics/00000002/9/porsche%20speedster%20emblem.jpg"

    def test_absolute_url_with_spaces_gets_quoted(self) -> None:
        result = _normalize_graphics_url("https://www.suncoastparts.com/mm5/graphics/a/foo bar.jpg")
        assert result == "https://www.suncoastparts.com/mm5/graphics/a/foo%20bar.jpg"

    def test_already_encoded_url_preserved(self) -> None:
        src = "https://www.suncoastparts.com/mm5/graphics/a/foo%20bar.jpg"
        # quote(safe='/%') preserves the existing %20 rather than double-encoding to %2520.
        assert _normalize_graphics_url(src) == src


class TestSitemapExtraction:
    """Single flat urlset with product + legacy Miva URLs; only the canonical /product/<SKU>.html survives."""

    def test_filters_to_product_urls_only(self) -> None:
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://www.suncoastparts.com/product/POHC.html</loc></url>"
            "<url><loc>https://www.suncoastparts.com/product/99755922100041.html</loc></url>"
            "<url><loc>https://www.suncoastparts.com/mm5/merchant.mvc?Screen=PROD&amp;Product_Code=POHC</loc></url>"
            "<url><loc>https://www.suncoastparts.com/category/brakes.html</loc></url>"
            "</urlset>"
        )
        assert _extract_product_urls_from_sitemap(xml) == [
            "https://www.suncoastparts.com/product/POHC.html",
            "https://www.suncoastparts.com/product/99755922100041.html",
        ]

    def test_deduplicates(self) -> None:
        xml = (
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://www.suncoastparts.com/product/POHC.html</loc></url>"
            "<url><loc>https://www.suncoastparts.com/product/POHC.html</loc></url>"
            "</urlset>"
        )
        assert _extract_product_urls_from_sitemap(xml) == [
            "https://www.suncoastparts.com/product/POHC.html",
        ]

    def test_returns_empty_on_parse_error(self) -> None:
        assert _extract_product_urls_from_sitemap("<not valid xml") == []


class TestImageDataJsExtraction:
    """Miva ships the product gallery in an inline ``var image_data<N> = [...];`` block."""

    def test_takes_full_size_from_each_entry(self) -> None:
        js = """
        var image_data12 = [
          {"type_code":"main","image_data":["graphics/a/one.jpg","graphics/a/one_80x51.jpg","graphics/a/one.jpg"]},
          {"type_code":"img1","image_data":["graphics/a/two.jpg","graphics/a/two_80x51.jpg","graphics/a/two.jpg"]}
        ]
        var im1 = ...
        """
        urls = _extract_gallery_urls_from_js(js)
        assert urls == [
            "https://www.suncoastparts.com/graphics/a/one.jpg",
            "https://www.suncoastparts.com/graphics/a/two.jpg",
        ]

    def test_returns_empty_when_var_missing(self) -> None:
        assert _extract_gallery_urls_from_js("<html>no gallery</html>") == []


class TestParseProductPage:
    """End-to-end: real-shape Miva HTML → ScrapedPayload."""

    def test_full_page_parses_from_og_and_gallery(self) -> None:
        result = SuncoastPartsAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == 'Emblem - "Speedster" in Black'
        assert result.part_manufacturer == "Porsche"
        # URL stem wins — matches the OEM Porsche MPN.
        assert result.part_number == "99755922100041"
        assert result.price_cents == 23900
        assert result.description and "adhesive on the backside" in result.description
        # og:description is the templated "Check out the deal..." marketing blurb — must be dropped.
        assert result.description and "Check out the deal" not in result.description
        assert result.product_url == SAMPLE_URL

    def test_og_title_wins_over_h1_sku_concatenation(self) -> None:
        # Miva concatenates the SKU span into the H1 — H1.get_text() yields
        # "Emblem - \"Speedster\" in BlackSKU: 99755922100041" which is garbage.
        # og:title is the clean source.
        result = SuncoastPartsAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert not result.name.endswith("99755922100041")
        assert "SKU:" not in result.name

    def test_gallery_images_are_absolute_and_quoted(self) -> None:
        result = SuncoastPartsAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        # og:image (already encoded) leads, then the gallery full-size URLs.
        assert all(u.startswith("https://www.suncoastparts.com/") for u in result.image_urls)
        assert all(" " not in u for u in result.image_urls), "filenames with spaces must be %20-encoded"
        # Thumbnail variants (_80x51) must be dropped — we only keep full-size.
        assert all("_80x51" not in u for u in result.image_urls)

    def test_non_porsche_brand_passes_through(self) -> None:
        # Suncoast stocks third-party brands too; og:brand is not always "Porsche".
        result = SuncoastPartsAdapter().parse_product_page(
            _product_html(
                og_brand="AWE Tuning", og_title_raw="AWE Touring Exhaust", og_title_decoded="AWE Touring Exhaust"
            ),
            SAMPLE_URL,
        )
        assert result is not None
        assert result.part_manufacturer == "AWE Tuning"

    def test_internal_sku_is_used_as_part_number(self) -> None:
        # Internal codes like SKURSTRACK are still valid retailer SKUs —
        # keep them so listings dedupe per-URL even without an OEM MPN.
        url = "https://www.suncoastparts.com/product/SKURSTRACK.html"
        result = SuncoastPartsAdapter().parse_product_page(_product_html(), url)
        assert result is not None
        assert result.part_number == "SKURSTRACK"

    def test_non_product_url_returns_none(self) -> None:
        # Guard: archive rescrape pipeline must not run category pages through
        # this adapter just because the host matches.
        result = SuncoastPartsAdapter().parse_product_page(
            _product_html(),
            "https://www.suncoastparts.com/category/brakes.html",
        )
        assert result is None

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert SuncoastPartsAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """Suncoast must declare the TLS fetcher tier — Cloudflare JS challenge on plain requests."""

    def test_declares_tls_tier(self) -> None:
        assert SuncoastPartsAdapter.FETCHER_TIER == "tls"
