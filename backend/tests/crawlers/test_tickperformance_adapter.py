"""
Tests for tickperformance.com adapter: BigCommerce Stencil parsing with no
JSON-LD Product block — same theme family as x-ph.com, but Tick surfaces a
retailer-curated brand in ``productView-brand`` and titles routinely carry a
trailing ``", Part #<mpn>"`` token that we strip for a clean stored name.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.tickperformance import (
    TickPerformanceAdapter,
    _extract_bcdata,
    _image_dedup_key,
    _is_products_child_sitemap,
    _strip_trailing_part_number,
)

SAMPLE_URL = (
    "https://www.tickperformance.com/" "russell-twist-lok-hose-end-tight-radius-6-150-degree-anodized-part-626030/"
)


def _product_page_html(
    *,
    title: str = "Russell Twist Lok Hose End Tight Radius #6 150 Degree Anodized, Part #626030",
    brand: str = "Russell",
    sku: str = "RUS-626030",
    mpn: str = "",
    gtin: str = "",
    upc: str = "",
    price_dollars: str = "26.95",
    description_text: str = (
        "Russell Twist Lok Hose End Tight Radius #6 150 Degree Anodized, Part #626030. "
        "Tick Performance is proud to be a warehouse distributor for the entire "
        "Edelbrock/Russell line."
    ),
    zoom_image: str = (
        "https://cdn11.bigcommerce.com/s-75d0b/images/stencil/1280x1280/"
        "products/129283/104556/russel1__58225.1416759341.jpg?c=2"
    ),
    lowres_image: str = (
        "https://cdn11.bigcommerce.com/s-75d0b/images/stencil/500x500/"
        "products/129283/104556/russel1__58225.1416759341.jpg?c=2"
    ),
    og_image: str = (
        "https://cdn11.bigcommerce.com/s-75d0b/products/129283/images/104556/"
        "russel1__58225.1416759341.500.750.jpg?c=2"
    ),
) -> str:
    """Minimal page that mirrors the real tickperformance.com Stencil shape."""
    mpn_field = f'"mpn":"{mpn}",' if mpn else '"mpn":null,'
    gtin_field = f'"gtin":"{gtin}",' if gtin else '"gtin":null,'
    upc_field = f'"upc":"{upc}",' if upc else '"upc":null,'
    bcdata = (
        '{"product_attributes":{'
        f'"sku":"{sku}",'
        f"{upc_field}"
        f"{mpn_field}"
        f"{gtin_field}"
        '"weight":null,'
        '"price":{"without_tax":{"formatted":"$' + price_dollars + '",'
        '"value":' + price_dollars + ',"currency":"USD"},"tax_label":"NC State Sales Tax"}'
        "}}"
    )
    brand_block = (
        f'<h2 class="productView-brand">'
        f'<a href="https://www.tickperformance.com/brands/{brand}.html"><span>{brand}</span></a>'
        f"</h2>"
        if brand
        else ""
    )
    return f"""
    <html><head>
      <title>{title} - Tick Performance</title>
      <meta name="platform" content="bigcommerce.stencil" />
      <meta property="og:type" content="product" />
      <meta property="og:title" content="{title}" />
      <meta property="og:image" content="{og_image}" />
      <meta property="product:price:amount" content="{price_dollars}" />
      <meta property="product:price:currency" content="USD" />
      <script>
      var BCData = {bcdata};
      </script>
    </head><body>
      <section class="productView-details product-data">
        <div class="productView-product">
          <h1 class="productView-title">{title}</h1>
          {brand_block}
        </div>
      </section>
      <div class="price-section" itemprop="offers" itemscope>
        <meta itemprop="price" content="{price_dollars}">
        <meta itemprop="priceCurrency" content="USD">
      </div>
      <section class="productView-images" data-image-gallery>
        <figure class="productView-image" data-zoom-image="{zoom_image}">
          <img class="productView-image--default" data-src="{lowres_image}" alt="{title}">
        </figure>
      </section>
      <article class="productView-description">
        <ul class="tabs" data-tab>
          <li class="tab is-active"><a href="#tab-description">Description</a></li>
          <li class="tab"><a href="#tab-warranty">Warranty Information</a></li>
        </ul>
        <div class="tabs-contents">
          <div class="tab-content is-active" id="tab-description">
            {description_text}
          </div>
          <div class="tab-content" id="tab-warranty">
            All warranty questions should be directed to {brand}.
          </div>
        </div>
      </article>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_bare_host_routes_to_tickperformance(self) -> None:
        assert adapter_name_for_product_url("https://tickperformance.com/foo/") == "tickperformance"

    def test_www_subdomain_routes_to_tickperformance(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "tickperformance"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/tickperformance") == "generic"


class TestStripTrailingPartNumber:
    """Titles carry ``", Part #<mpn>"`` as a trailing token on many brands."""

    def test_strips_matching_part_number(self) -> None:
        assert (
            _strip_trailing_part_number(
                "Russell Twist Lok Hose End Tight Radius #6 150 Degree Anodized, Part #626030",
                "626030",
            )
            == "Russell Twist Lok Hose End Tight Radius #6 150 Degree Anodized"
        )

    def test_case_insensitive_match(self) -> None:
        assert _strip_trailing_part_number("Widget, Part #ABC-123", "abc-123") == "Widget"

    def test_non_matching_part_number_left_intact(self) -> None:
        # Trailing token is not the real MPN — keep the title unchanged rather
        # than guess at which suffix to drop.
        assert _strip_trailing_part_number("Widget, Part #SOMETHING-ELSE", "ABC-123") == "Widget, Part #SOMETHING-ELSE"

    def test_no_mpn_returns_title_unchanged(self) -> None:
        assert _strip_trailing_part_number("Widget", None) == "Widget"
        assert _strip_trailing_part_number("Widget", "") == "Widget"

    def test_title_without_part_suffix_untouched(self) -> None:
        assert _strip_trailing_part_number("Widget ABC-123", "ABC-123") == "Widget ABC-123"


class TestImageDedupKey:
    """The same photo appears at several stencil sizes — keys must collapse."""

    URLS = [
        "https://cdn11.bigcommerce.com/s-75d0b/images/stencil/1280x1280/products/129283/104556/russel1__58225.1416759341.jpg?c=2",
        "https://cdn11.bigcommerce.com/s-75d0b/images/stencil/500x500/products/129283/104556/russel1__58225.1416759341.jpg?c=2",
        "https://cdn11.bigcommerce.com/s-75d0b/products/129283/images/104556/russel1__58225.1416759341.500.750.jpg?c=2",
    ]

    def test_all_size_variants_collapse_to_one_key(self) -> None:
        keys = {_image_dedup_key(u) for u in self.URLS}
        assert len(keys) == 1

    def test_different_photos_keep_distinct_keys(self) -> None:
        a = _image_dedup_key(self.URLS[0])
        b = _image_dedup_key(
            "https://cdn11.bigcommerce.com/s-75d0b/images/stencil/1280x1280/"
            "products/129283/104557/other__11111.1416759342.jpg?c=2"
        )
        assert a != b


class TestIsProductsChildSitemap:
    """Discovery only crawls ``type=products&page=N`` children of the sitemap index."""

    def test_products_child_accepted(self) -> None:
        assert _is_products_child_sitemap("https://www.tickperformance.com/xmlsitemap.php?type=products&page=1")
        assert _is_products_child_sitemap("https://www.tickperformance.com/xmlsitemap.php?type=products&page=16")

    def test_non_product_children_rejected(self) -> None:
        for bad in (
            "https://www.tickperformance.com/xmlsitemap.php?type=pages&page=1",
            "https://www.tickperformance.com/xmlsitemap.php?type=categories&page=1",
            "https://www.tickperformance.com/xmlsitemap.php?type=brands&page=1",
            "https://www.tickperformance.com/xmlsitemap.php?type=news&page=1",
            "https://www.tickperformance.com/some-product/",
        ):
            assert not _is_products_child_sitemap(bad), bad


class TestExtractBCData:
    """BCData is the authoritative source for SKU/price on a Stencil theme."""

    def test_parses_inline_blob(self) -> None:
        html = (
            '<html><script>var BCData = {"product_attributes":'
            '{"sku":"RUS-626030","price":{"without_tax":{"value":26.95,"currency":"USD"}}}};'
            "</script></html>"
        )
        data = _extract_bcdata(html)
        assert data is not None
        assert data["product_attributes"]["sku"] == "RUS-626030"

    def test_missing_blob_returns_none(self) -> None:
        assert _extract_bcdata("<html><body>no BCData here</body></html>") is None

    def test_malformed_json_returns_none(self) -> None:
        assert _extract_bcdata("<script>var BCData = {not json};</script>") is None


class TestParseProductPage:
    """End-to-end parsing against real-shape BigCommerce HTML."""

    def test_full_page_parses_with_brand_block_and_mpn_suffix_strip(self) -> None:
        # When MPN is set and matches the trailing ``Part #`` token, the
        # title gets cleaned up; brand is read from productView-brand.
        html = _product_page_html(mpn="626030")
        result = TickPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name == "Russell Twist Lok Hose End Tight Radius #6 150 Degree Anodized"
        assert result.part_manufacturer == "Russell"
        # MPN wins over the retailer-prefixed SKU.
        assert result.part_number == "626030"
        assert result.price_cents == 2695
        assert result.product_url == SAMPLE_URL
        assert result.image_urls is not None
        assert len(result.image_urls) == 1
        assert "1280x1280" in result.image_urls[0]

    def test_sku_used_when_mpn_missing(self) -> None:
        # No MPN populated — keep the retailer-prefixed SKU as part_number
        # rather than guessing at the split, and leave the title's trailing
        # ``Part #...`` token intact (it's not proven to match the MPN).
        html = _product_page_html(mpn="")
        result = TickPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "RUS-626030"
        assert "Part #626030" in result.name

    def test_gtin_falls_back_to_upc(self) -> None:
        # Real Tick product pages often populate UPC but not GTIN; the
        # adapter treats UPC as a GTIN-equivalent source.
        html = _product_page_html(gtin="", upc="012345678905")
        result = TickPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.gtin == "012345678905"

    def test_description_reads_description_tab_not_warranty(self) -> None:
        # The article wraps both tabs — we must target ``#tab-description``
        # so warranty prose doesn't leak into the product description.
        html = _product_page_html()
        result = TickPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.description is not None
        assert "warehouse distributor" in result.description
        assert "warranty questions" not in result.description

    def test_brand_falls_back_to_title_heuristic_when_brand_block_missing(self) -> None:
        # Rare but possible: some products don't have a brand row on the PDP.
        html = _product_page_html(brand="")
        result = TickPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer  # heuristic found *something*

    def test_price_falls_back_to_microdata_when_bcdata_missing(self) -> None:
        html = (
            "<html><head>"
            '<meta name="platform" content="bigcommerce.stencil" />'
            '<meta property="og:title" content="Generic Part ABC123" />'
            "</head><body>"
            '<h1 class="productView-title">Generic Part ABC123</h1>'
            '<div itemprop="offers" itemscope>'
            '  <meta itemprop="price" content="249.99">'
            '  <meta itemprop="priceCurrency" content="USD">'
            "</div>"
            "</body></html>"
        )
        result = TickPerformanceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.price_cents == 24999

    def test_missing_name_returns_none(self) -> None:
        # No h1, no og:title → cannot identify product; return None so the
        # runner skips rather than ingesting a blank row.
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert TickPerformanceAdapter().parse_product_page(html, SAMPLE_URL) is None
