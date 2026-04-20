"""
Tests for enjukuracing.com adapter: URL shape guard, registration, fetcher tier,
JSON-LD parsing (primary), BCData / og price fallback, and DOM fallback.

Enjuku Racing is a BigCommerce Stencil storefront behind Cloudflare (see
``site_problem_notes/enjukuracing.md``). These tests run against *synthetic*
HTML modeled on a real product page — JSON-LD ``Product`` + BCData price blob
+ og meta — so they don't depend on live network access.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier1_tls.enjukuracing import (
    EnjukuRacingAdapter,
    _is_product_url,
    _is_products_child_sitemap,
    _price_cents_from_bcdata,
)

SAMPLE_URL = "https://www.enjukuracing.com/products/isr-performance-inner-tie-rods-nissan-240sx.html"


def _product_html(
    *,
    name: str = "ISR Performance Inner Tie Rods - Nissan 240sx",
    brand: str = "ISR Performance",
    sku: str = "IS-ITR-240",
    mpn: str = "IS-ITR-240",
    price: str = "73.15",
    description: str = "ISR Performance Inner Tie Rods are strengthened for improved durability and increase steering angle at full lock.",
    image: str = (
        "https://cdn11.bigcommerce.com/s-79xyvl/images/stencil/1280x1280/"
        "products/19887/188041/P1200464__84896.1630073060.jpg?c=2"
    ),
    bcdata_price_value: str = "73.15",
    include_json_ld: bool = True,
) -> str:
    """Minimal page mirroring Enjuku's BigCommerce Stencil theme (JSON-LD + BCData + og)."""
    json_ld = ""
    if include_json_ld:
        json_ld = f"""
        <script type="application/ld+json">
        {{
          "@context": "https://schema.org/",
          "@type": "Product",
          "name": "{name}",
          "sku": "{sku}",
          "mpn": "{mpn}",
          "url": "{SAMPLE_URL}",
          "brand": {{"@type": "Brand", "name": "{brand}"}},
          "description": "{description}",
          "image": "{image}",
          "offers": {{
            "@type": "Offer",
            "priceCurrency": "USD",
            "price": "{price}",
            "itemCondition": "https://schema.org/NewCondition",
            "availability": "https://schema.org/InStock",
            "url": "{SAMPLE_URL}"
          }}
        }}
        </script>
        """
    bcdata = (
        '{"product_attributes":{"sku":"' + sku + '",'
        '"upc":null,"mpn":"' + mpn + '","gtin":null,"weight":null,"base":true,"image":null,'
        '"price":{"without_tax":{"formatted":"$' + bcdata_price_value + '",'
        '"value":' + bcdata_price_value + ',"currency":"USD"},"tax_label":"Sales Tax"},'
        '"stock":null,"instock":true}}'
    )
    return f"""
    <html><head>
      <title>{name} - Enjuku Racing</title>
      <meta property="og:type" content="product" />
      <meta property="og:title" content="{name}" />
      <meta property="og:image" content="{image}" />
      <meta property="product:price:amount" content="{price}" />
      <meta property="product:price:currency" content="USD" />
      {json_ld}
      <script>
      var BCData = {bcdata};
      </script>
    </head><body>
      <h1 class="et-productView-title">{name}</h1>
      <section class="productView-images" data-image-gallery>
        <figure class="productView-image" data-image-gallery-main>
          <img src="{image}" alt="{name}" />
        </figure>
      </section>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_www_host_routes_to_enjukuracing(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "enjukuracing"

    def test_bare_host_routes_to_enjukuracing(self) -> None:
        assert (
            adapter_name_for_product_url(
                "https://enjukuracing.com/products/isr-performance-inner-tie-rods-nissan-240sx.html"
            )
            == "enjukuracing"
        )

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/enjukuracing") == "generic"


class TestFetcherTier:
    """
    Enjuku is Cloudflare-gated (``cf-mitigated: challenge`` on plain requests);
    the adapter must declare the TLS tier so the runner hands it a curl_cffi
    fetcher. Backlog originally estimated Tier-0 — override is intentional.
    """

    def test_tls_tier_declared(self) -> None:
        assert EnjukuRacingAdapter.FETCHER_TIER == "tls"


class TestProductUrlShape:
    """``/products/<slug>.html`` is the positive filter (unlike xph root slugs)."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_bare_host_accepted(self) -> None:
        assert _is_product_url("https://enjukuracing.com/products/some-slug.html")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/products/some-slug.html")

    def test_non_products_path_rejected(self) -> None:
        # Categories, brands, news, pages live under other prefixes — skip them.
        assert not _is_product_url("https://www.enjukuracing.com/categories/drift.html")
        assert not _is_product_url("https://www.enjukuracing.com/brands/isr-performance.html")
        assert not _is_product_url("https://www.enjukuracing.com/about-us.html")

    def test_missing_html_suffix_rejected(self) -> None:
        # BigCommerce Stencil pairs /products/ with a trailing .html — a bare
        # slug is a category listing, not a product page.
        assert not _is_product_url("https://www.enjukuracing.com/products/")
        assert not _is_product_url("https://www.enjukuracing.com/products/some-slug")


class TestProductsChildSitemapFilter:
    """Discovery only walks ``type=products`` children; other types are skipped."""

    def test_products_child_accepted(self) -> None:
        for page in (1, 2, 6):
            url = f"https://www.enjukuracing.com/xmlsitemap.php?type=products&page={page}"
            assert _is_products_child_sitemap(url), url

    def test_non_product_children_rejected(self) -> None:
        for bad in (
            "https://www.enjukuracing.com/xmlsitemap.php?type=pages&page=1",
            "https://www.enjukuracing.com/xmlsitemap.php?type=categories&page=1",
            "https://www.enjukuracing.com/xmlsitemap.php?type=brands&page=1",
            "https://www.enjukuracing.com/xmlsitemap.php?type=news&page=1",
            "https://www.enjukuracing.com/products/foo.html",
        ):
            assert not _is_products_child_sitemap(bad), bad


class TestBCDataPriceFallback:
    """When JSON-LD ``offers.price`` is missing, BCData.price.without_tax.value wins."""

    def test_parses_numeric_value(self) -> None:
        blob = '{"product_attributes":{"price":{"without_tax":{"formatted":"$73.15","value":73.15,"currency":"USD"}}}}'
        assert _price_cents_from_bcdata(blob) == 7315

    def test_parses_string_value(self) -> None:
        blob = '{"product_attributes":{"price":{"without_tax":{"formatted":"$20.00","value":"20","currency":"USD"}}}}'
        assert _price_cents_from_bcdata(blob) == 2000

    def test_missing_blob_returns_none(self) -> None:
        assert _price_cents_from_bcdata("<html>no BCData here</html>") is None

    def test_zero_value_returns_none(self) -> None:
        blob = '{"product_attributes":{"price":{"without_tax":{"value":0,"currency":"USD"}}}}'
        assert _price_cents_from_bcdata(blob) is None


class TestParseProductPage:
    """End-to-end parsing against real-shape JSON-LD + BCData + og HTML."""

    def test_json_ld_primary_path(self) -> None:
        result = EnjukuRacingAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "ISR Performance Inner Tie Rods - Nissan 240sx"
        assert result.part_manufacturer == "ISR Performance"
        assert result.part_number == "IS-ITR-240"
        assert result.price_cents == 7315
        assert result.product_url == SAMPLE_URL
        assert result.description is not None and "steering angle" in result.description
        assert result.image_urls is not None and len(result.image_urls) == 1
        assert "1280x1280" in result.image_urls[0]

    def test_rejects_non_product_url(self) -> None:
        # Even with a valid JSON-LD block, a non-product path should return None
        # so the runner never ingests category / CMS pages that accidentally
        # carry schema.org Product markup.
        assert (
            EnjukuRacingAdapter().parse_product_page(
                _product_html(), "https://www.enjukuracing.com/categories/drift.html"
            )
            is None
        )

    def test_bcdata_price_used_when_json_ld_missing_offers(self) -> None:
        # Strip only the offers block — JSON-LD still present so the primary
        # path runs, but payload.price_cents is None and the BCData fallback
        # must fill it in.
        html = _product_html()
        html = html.replace(
            '"offers": {\n            "@type": "Offer",\n            "priceCurrency": "USD",\n            "price": "73.15",\n            "itemCondition": "https://schema.org/NewCondition",\n            "availability": "https://schema.org/InStock",\n            "url": "'
            + SAMPLE_URL
            + '"\n          }',
            '"offers": {}',
        )
        result = EnjukuRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        # JSON-LD offer was emptied → BCData.price.without_tax.value = 73.15 wins.
        assert result.price_cents == 7315

    def test_dom_fallback_when_no_json_ld(self) -> None:
        # Theme shipped without a JSON-LD Product block (unlikely but possible).
        # The adapter should still recover a name from og:title and a price
        # from BCData / og meta so archive rescrapes don't drop to None.
        html = _product_html(include_json_ld=False)
        result = EnjukuRacingAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name == "ISR Performance Inner Tie Rods - Nissan 240sx"
        assert result.price_cents == 7315
        # No JSON-LD → no brand → heuristic picks first title token.
        assert result.part_manufacturer is not None

    def test_missing_name_returns_none(self) -> None:
        # No JSON-LD, no og:title, no h1 → nothing to ingest.
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert EnjukuRacingAdapter().parse_product_page(html, SAMPLE_URL) is None
