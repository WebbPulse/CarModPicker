"""
Tests for x-ph.com (Extreme Power House) adapter: BigCommerce Stencil parsing
with no JSON-LD Product block — the adapter reads the inline ``BCData`` JSON,
Schema.org microdata, and gallery DOM.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.xph import (
    XPHAdapter,
    _extract_bcdata,
    _image_dedup_key,
    _is_products_child_sitemap,
    _strip_trailing_sku,
)

SAMPLE_URL = (
    "https://x-ph.com/bbs-ch-r-nurburgring-edition-19x9-5-5x120-et35-"
    "satin-black-red-lip-wheel-82mm-pfs-clip-req-bbsch106ne/"
)


def _product_page_html(
    *,
    title: str = (
        "BBS CH-R Nurburgring Edition 19x9.5 5x120 ET35 Satin Black/Red Lip Wheel " "- 82mm PFS/Clip Req. bbsCH106NE"
    ),
    sku: str = "bbsCH106NE",
    mpn: str = "",
    gtin: str = "",
    price_dollars: str = "875",
    zoom_image: str = (
        "https://cdn11.bigcommerce.com/s-gd6olw6/images/stencil/1280x1280/"
        "products/43474/81243/92675cdda59bef76174ccdd85cdbf748__01565.1662095305.jpg?c=2"
    ),
    lowres_image: str = (
        "https://cdn11.bigcommerce.com/s-gd6olw6/images/stencil/500x459/"
        "products/43474/81243/92675cdda59bef76174ccdd85cdbf748__01565.1662095305.jpg?c=2"
    ),
    og_image: str = (
        "https://cdn11.bigcommerce.com/s-gd6olw6/products/43474/images/81243/"
        "92675cdda59bef76174ccdd85cdbf748__01565.1662095305.500.750.jpg?c=2"
    ),
    description_text: str = (
        "BBS CH-R Nurburgring Edition 19x9.5 5x120 ET35 Satin Black/Red Lip Wheel " "- 82mm PFS/Clip Req."
    ),
) -> str:
    """Minimal page that mirrors the real x-ph.com BigCommerce Stencil shape."""
    mpn_field = f'"mpn":"{mpn}",' if mpn else '"mpn":null,'
    gtin_field = f'"gtin":"{gtin}"' if gtin else '"gtin":null'
    bcdata = (
        '{"product_attributes":{'
        f'"sku":"{sku}",'
        '"upc":null,'
        f"{mpn_field}"
        f"{gtin_field},"
        '"price":{"without_tax":{"formatted":"$' + price_dollars + '.00",'
        '"value":' + price_dollars + ',"currency":"USD"},"tax_label":"Tax"}'
        "}}"
    )
    return f"""
    <html><head>
      <title>{title} - Extreme Power House</title>
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
      <h1 class="productView-title" itemprop="name">{title}</h1>
      <div class="price-section" itemprop="offers" itemscope itemtype="http://schema.org/Offer">
        <div itemprop="priceSpecification" itemscope itemtype="http://schema.org/PriceSpecification">
          <meta itemprop="price" content="{price_dollars}">
          <meta itemprop="priceCurrency" content="USD">
        </div>
      </div>
      <section class="productView-images" data-image-gallery>
        <figure class="productView-image" data-zoom-image="{zoom_image}">
          <img class="productView-image--default" data-src="{lowres_image}" alt="{title}">
        </figure>
      </section>
      <article class="productView-description" itemprop="description">
        <p class="productView-title">Description</p>
        <div class="productView-description">
          <p>{description_text}</p>
        </div>
      </article>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_bare_host_routes_to_xph(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "xph"

    def test_www_subdomain_routes_to_xph(self) -> None:
        assert adapter_name_for_product_url("https://www.x-ph.com/some-product/") == "xph"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/x-ph") == "generic"


class TestStripTrailingSku:
    """SKU is appended to product titles on this site; strip it for a clean name."""

    def test_strips_matching_suffix_preserving_punctuation(self) -> None:
        # Trailing period on "Req." is part of an abbreviation — must survive.
        assert (
            _strip_trailing_sku("BBS CH-R 19x9.5 PFS/Clip Req. bbsCH106NE", "bbsCH106NE")
            == "BBS CH-R 19x9.5 PFS/Clip Req."
        )

    def test_case_insensitive(self) -> None:
        assert _strip_trailing_sku("Wheel BBSCH106NE", "bbsch106ne") == "Wheel"

    def test_no_match_returns_title_unchanged(self) -> None:
        assert _strip_trailing_sku("BBS CH-R Wheel", "unrelated") == "BBS CH-R Wheel"

    def test_empty_sku_returns_title_unchanged(self) -> None:
        assert _strip_trailing_sku("BBS CH-R Wheel", None) == "BBS CH-R Wheel"
        assert _strip_trailing_sku("BBS CH-R Wheel", "") == "BBS CH-R Wheel"


class TestImageDedupKey:
    """The same photo appears at several stencil sizes — keys must collapse."""

    URLS = [
        "https://cdn11.bigcommerce.com/s-gd6olw6/images/stencil/1280x1280/products/43474/81243/abc__01565.1662095305.jpg?c=2",
        "https://cdn11.bigcommerce.com/s-gd6olw6/images/stencil/500x459/products/43474/81243/abc__01565.1662095305.jpg?c=2",
        "https://cdn11.bigcommerce.com/s-gd6olw6/products/43474/images/81243/abc__01565.1662095305.500.750.jpg?c=2",
    ]

    def test_all_size_variants_collapse_to_one_key(self) -> None:
        keys = {_image_dedup_key(u) for u in self.URLS}
        assert len(keys) == 1

    def test_different_photos_keep_distinct_keys(self) -> None:
        a = _image_dedup_key(self.URLS[0])
        b = _image_dedup_key(
            "https://cdn11.bigcommerce.com/s-gd6olw6/images/stencil/1280x1280/"
            "products/43474/81244/xyz__01566.1662095306.jpg?c=2"
        )
        assert a != b


class TestIsProductsChildSitemap:
    """Discovery only crawls ``type=products&page=N`` children of the sitemap index."""

    def test_products_child_accepted(self) -> None:
        assert _is_products_child_sitemap("https://x-ph.com/xmlsitemap.php?type=products&page=1")
        assert _is_products_child_sitemap("https://x-ph.com/xmlsitemap.php?type=products&page=8")

    def test_non_product_children_rejected(self) -> None:
        for bad in (
            "https://x-ph.com/xmlsitemap.php?type=pages&page=1",
            "https://x-ph.com/xmlsitemap.php?type=categories&page=1",
            "https://x-ph.com/xmlsitemap.php?type=brands&page=1",
            "https://x-ph.com/xmlsitemap.php?type=news&page=1",
            "https://x-ph.com/some-product/",
        ):
            assert not _is_products_child_sitemap(bad), bad


class TestExtractBCData:
    """BCData is the authoritative source for SKU/price on a Stencil theme."""

    def test_parses_inline_blob(self) -> None:
        html = (
            '<html><script>var BCData = {"product_attributes":'
            '{"sku":"X1","price":{"without_tax":{"value":100,"currency":"USD"}}}};'
            "</script></html>"
        )
        data = _extract_bcdata(html)
        assert data is not None
        assert data["product_attributes"]["sku"] == "X1"

    def test_missing_blob_returns_none(self) -> None:
        assert _extract_bcdata("<html><body>no BCData here</body></html>") is None

    def test_malformed_json_returns_none(self) -> None:
        assert _extract_bcdata("<script>var BCData = {not json};</script>") is None


class TestParseProductPage:
    """End-to-end parsing against real-shape BigCommerce HTML."""

    def test_full_page_parses(self) -> None:
        result = XPHAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        # SKU suffix ("bbsCH106NE") is stripped, trailing period on "Req." preserved.
        assert result.name == (
            "BBS CH-R Nurburgring Edition 19x9.5 5x120 ET35 " "Satin Black/Red Lip Wheel - 82mm PFS/Clip Req."
        )
        assert result.part_manufacturer == "BBS"
        assert result.part_number == "bbsCH106NE"
        assert result.price_cents == 87500
        assert result.gtin is None
        assert result.product_url == SAMPLE_URL
        # All three CDN variants of the same photo collapse to one entry.
        assert result.image_urls is not None
        assert len(result.image_urls) == 1
        assert "1280x1280" in result.image_urls[0]

    def test_mpn_preferred_over_sku(self) -> None:
        # When BigCommerce populates MPN, it's the clean manufacturer code and
        # should win over the retailer-prefixed SKU — same trick as Summit.
        html = _product_page_html(sku="bbsCH106NE", mpn="CH106-NE")
        result = XPHAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "CH106-NE"

    def test_gtin_passed_through_when_present(self) -> None:
        html = _product_page_html(gtin="00012345678905")
        result = XPHAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.gtin == "00012345678905"

    def test_price_falls_back_to_microdata_when_bcdata_missing(self) -> None:
        html = (
            "<html><head>"
            '<meta name="platform" content="bigcommerce.stencil" />'
            '<meta property="og:title" content="Generic Part ABC123" />'
            "</head><body>"
            '<h1 class="productView-title" itemprop="name">Generic Part ABC123</h1>'
            '<div itemprop="offers" itemscope>'
            '  <meta itemprop="price" content="249.99">'
            '  <meta itemprop="priceCurrency" content="USD">'
            "</div>"
            "</body></html>"
        )
        result = XPHAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.price_cents == 24999

    def test_missing_name_returns_none(self) -> None:
        # No h1, no og:title → cannot identify product; return None so the
        # runner skips rather than ingesting a blank row.
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert XPHAdapter().parse_product_page(html, SAMPLE_URL) is None
