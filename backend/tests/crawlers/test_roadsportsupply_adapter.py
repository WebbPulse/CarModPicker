"""
Tests for roadsportsupply.com (RSS Manufacturing) adapter: URL shape guard,
registration, fetcher tier, JSON-LD parsing (primary), BCData / og price
fallback, and DOM fallback.

Road Sport Supply is a BigCommerce Stencil storefront — same theme family as
xph.com (root-slug URLs) and enjukuracing.com (JSON-LD Product). Unlike Enjuku,
Cloudflare is passive here, so the adapter stays at Tier-0 HTTP. These tests
run against *synthetic* HTML modeled on a real product page so they don't
depend on live network access.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.roadsportsupply import (
    RoadSportSupplyAdapter,
    _is_product_url,
    _is_products_child_sitemap,
    _price_cents_from_bcdata,
)

SAMPLE_URL = "https://roadsportsupply.com/323-thrust-arm-bushing-puck-non-castor-adjustable-front-axle/"


def _product_html(
    *,
    name: str = "323 Thrust Arm Bushing/Puck - Non Castor Adjustable - Front Axle",
    brand: str = "RSS",
    sku: str = "323",
    mpn: str = "",
    price: str = "290",
    description: str = "NON-ADJUSTABLE THRUST ARM BUSHING KIT - Front Axle. Improves handling and response of suspension system.",
    image: str = (
        "https://cdn11.bigcommerce.com/s-kmq200x97v/images/stencil/1280x1280/"
        "products/234/1163/df9a25c7-89b0-48bc-ba2d-ab98156e4169-800__04530.1529099407.jpg?c=2"
    ),
    bcdata_price_value: str = "290",
    include_json_ld: bool = True,
) -> str:
    """Minimal page mirroring Road Sport Supply's BigCommerce Stencil theme."""
    mpn_field = f'"mpn": "{mpn}",' if mpn else ""
    json_ld = ""
    if include_json_ld:
        json_ld = f"""
        <script type="application/ld+json">
        {{
          "@context": "https://schema.org/",
          "@type": "Product",
          "name": "{name}",
          "sku": "{sku}",
          {mpn_field}
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
        '"upc":null,"mpn":null,"gtin":null,"weight":null,"base":true,"image":null,'
        '"price":{"without_tax":{"formatted":"$' + bcdata_price_value + '.00",'
        '"value":' + bcdata_price_value + ',"currency":"USD"},"tax_label":"Tax"},'
        '"stock":null,"instock":true}}'
    )
    return f"""
    <html><head>
      <title>{name} - Road Sport Supply</title>
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
      <h1>{name}</h1>
      <section class="productView-images" data-image-gallery>
        <figure class="productView-image" data-image-gallery-main>
          <img src="{image}" alt="{name}" />
        </figure>
      </section>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_bare_host_routes_to_roadsportsupply(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "roadsportsupply"

    def test_www_host_routes_to_roadsportsupply(self) -> None:
        assert (
            adapter_name_for_product_url(
                "https://www.roadsportsupply.com/323-thrust-arm-bushing-puck-non-castor-adjustable-front-axle/"
            )
            == "roadsportsupply"
        )

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/roadsportsupply") == "generic"


class TestFetcherTier:
    """
    Road Sport Supply is Cloudflare-fronted but passive — plain ``fetch_page``
    returns 200 on product pages. Keep Tier-0.
    """

    def test_http_tier_default(self) -> None:
        assert RoadSportSupplyAdapter.FETCHER_TIER == "http"


class TestProductUrlShape:
    """Root-slug URL shape (``/<slug>/``), same as xph — not ``/products/...``."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/some-slug/")

    def test_root_path_rejected(self) -> None:
        # Empty path is the homepage, not a product.
        assert not _is_product_url("https://roadsportsupply.com/")

    def test_nested_path_rejected(self) -> None:
        # Category / CMS URLs with deeper nesting should not be picked up.
        assert not _is_product_url("https://roadsportsupply.com/brands/rss/")
        assert not _is_product_url("https://roadsportsupply.com/categories/suspension/bushings/")

    def test_known_non_product_slugs_rejected(self) -> None:
        # Known CMS / utility slugs served under the same ``/<slug>/`` shape.
        for slug in ("cart", "checkout", "account", "search", "brands", "categories", "rss"):
            assert not _is_product_url(f"https://roadsportsupply.com/{slug}/"), slug


class TestProductsChildSitemapFilter:
    """Discovery only walks ``type=products`` children; other types are skipped."""

    def test_products_child_accepted(self) -> None:
        for page in (1, 2, 6):
            url = f"https://roadsportsupply.com/xmlsitemap.php?type=products&page={page}"
            assert _is_products_child_sitemap(url), url

    def test_non_product_children_rejected(self) -> None:
        for bad in (
            "https://roadsportsupply.com/xmlsitemap.php?type=pages&page=1",
            "https://roadsportsupply.com/xmlsitemap.php?type=categories&page=1",
            "https://roadsportsupply.com/xmlsitemap.php?type=brands&page=1",
            "https://roadsportsupply.com/xmlsitemap.php?type=news&page=1",
            "https://roadsportsupply.com/323-thrust-arm-bushing-puck/",
        ):
            assert not _is_products_child_sitemap(bad), bad


class TestBCDataPriceFallback:
    """When JSON-LD ``offers.price`` is missing, BCData.price.without_tax.value wins."""

    def test_parses_numeric_value(self) -> None:
        blob = '{"product_attributes":{"price":{"without_tax":{"formatted":"$290.00","value":290,"currency":"USD"}}}}'
        assert _price_cents_from_bcdata(blob) == 29000

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
        result = RoadSportSupplyAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "323 Thrust Arm Bushing/Puck - Non Castor Adjustable - Front Axle"
        assert result.part_manufacturer == "RSS"
        assert result.part_number == "323"
        assert result.price_cents == 29000
        assert result.product_url == SAMPLE_URL
        assert result.description is not None and "THRUST ARM" in result.description.upper()
        assert result.image_urls is not None and len(result.image_urls) == 1
        assert "1280x1280" in result.image_urls[0]

    def test_third_party_brand_preserved(self) -> None:
        # RSS's storefront also resells third-party lines (Sharkwerks, Cargraphic,
        # Racetech, ...). JSON-LD ``brand.name`` is authoritative — we must not
        # overwrite it with the house brand.
        result = RoadSportSupplyAdapter().parse_product_page(
            _product_html(
                name="Shark Werks Sport 2.5 Exhaust for 992 Carrera S",
                brand="Sharkwerks",
                sku="Shax000",
                mpn="Shax000",
            ),
            "https://roadsportsupply.com/shark-werks-sport-2-5-exhaust-for-992-carrera-s-t-gts-turbo/",
        )
        assert result is not None
        assert result.part_manufacturer == "Sharkwerks"
        assert result.part_number == "Shax000"

    def test_rejects_non_product_url(self) -> None:
        # Even with a valid JSON-LD block, a non-product path should return None
        # so the runner never ingests category / CMS pages that accidentally
        # carry schema.org Product markup.
        assert (
            RoadSportSupplyAdapter().parse_product_page(_product_html(), "https://roadsportsupply.com/brands/rss/")
            is None
        )

    def test_bcdata_price_used_when_json_ld_missing_offers(self) -> None:
        # Strip only the offers block — JSON-LD still present so the primary
        # path runs, but payload.price_cents is None and the BCData fallback
        # must fill it in.
        html = _product_html()
        html = html.replace(
            '"offers": {\n            "@type": "Offer",\n            "priceCurrency": "USD",\n            "price": "290",\n            "itemCondition": "https://schema.org/NewCondition",\n            "availability": "https://schema.org/InStock",\n            "url": "'
            + SAMPLE_URL
            + '"\n          }',
            '"offers": {}',
        )
        result = RoadSportSupplyAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        # JSON-LD offer was emptied → BCData.price.without_tax.value = 290 wins.
        assert result.price_cents == 29000

    def test_dom_fallback_when_no_json_ld(self) -> None:
        # Theme shipped without a JSON-LD Product block (unlikely but possible).
        # The adapter should still recover a name from og:title and a price
        # from BCData / og meta so archive rescrapes don't drop to None.
        html = _product_html(include_json_ld=False)
        result = RoadSportSupplyAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("323 Thrust Arm Bushing")
        assert result.price_cents == 29000
        # No JSON-LD → no brand → heuristic picks first title token; may be None
        # for numeric-leading titles but must not raise.

    def test_missing_name_returns_none(self) -> None:
        # No JSON-LD, no og:title, no h1 → nothing to ingest.
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert RoadSportSupplyAdapter().parse_product_page(html, SAMPLE_URL) is None
