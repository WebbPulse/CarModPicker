"""
Tests for good-win-racing.com adapter: URL shape gate, host routing,
JSON-LD parse path (the authoritative source on the live Interchange
theme), DOM fallback for pages that drop the block, and FETCHER_TIER.

Good-Win Racing's storefront emits a well-formed schema.org Product
JSON-LD block on every product URL sampled live. Tests exercise that
primary path end-to-end plus a DOM-only fallback that mirrors the
``<h1>`` + ``img#mainimage`` + ``<h5 class="price">`` shape the theme
renders when JSON-LD is absent.

The URL gate is the single most important guarantee because the site
has both singular (``/Mazda-Performance-Part/``) and plural
(``/Mazda-Performance-Parts/``) path segments — mixing them up would
feed category browse pages into the parse pipeline.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier1_tls.goodwinracing import (
    GoodWinRacingAdapter,
    _extract_product_links,
    _is_category_url,
    _is_product_url,
)

PRODUCT_URL = "https://www.good-win-racing.com/Mazda-Performance-Part/61-3447.html"
CATEGORY_URL = "https://www.good-win-racing.com/Mazda-Performance-Parts/Miata/Brakes/Pads.html"


def _product_html_with_json_ld(
    *,
    sku: str = "61-3447",
    name: str = "DBA XP Brake Pads - Rear",
    brand: str = "DBA",
    price: str = "89.00",
    image: str = "https://www.good-win-racing.com/images/items/485x485/61-3441.webp",
    description: str = (
        "DBA's XP compound brake pads have strong initial bite. "
        "High heat capacity for a street pad and stable friction across a wide range "
        "from cold make these suitable for aggressive street use and autocross."
    ),
) -> str:
    """Reproduce the live Interchange theme: a ``Product`` JSON-LD block
    with sku/name/brand/price/image/description, a DOM ``<h1>`` / main
    image / price strip as secondary sources, and a "related products"
    section below with other-SKU thumbnails that MUST NOT show up in the
    parsed gallery."""
    return f"""
    <html><head>
      <title>Good-Win Racing</title>
      <meta name="description" content="Miata Performance Part: Brakes Pads: 2001-2005 - Price: ${price}" />
      <meta property="og:image" content="https://www.good-win-racing.com/assets/images/layout/logo_bw.png" />
      <script type="application/ld+json">
      {{
        "@context": "http://schema.org/",
        "@type": "Product",
        "sku": "{sku}",
        "image": "{image}",
        "name": "{name}",
        "description": "{description}",
        "brand": {{ "@type": "Brand", "name": "{brand}" }},
        "offers": {{
          "@type": "Offer",
          "url": "{PRODUCT_URL}",
          "itemCondition": "http://schema.org/NewCondition",
          "availability": "http://schema.org/InStock",
          "price": "{price}",
          "priceCurrency": "USD"
        }}
      }}
      </script>
    </head><body>
      <h1><span class="matrix_description">{name}</span></h1>
      <img id="mainimage" src="/images/items/485x485/{sku}.webp" alt="{name}" />
      <div class="cat_item_price">
        <p class="retail_price">$139.00</p>
        <h5 class="price">${price}</h5>
      </div>
      <!-- Related products — other SKUs' thumbnails. Must NOT appear
           in the parsed gallery; only mainimage belongs to this product. -->
      <div class="related">
        <img src="/images/items/noimage.jpg" data-src="/images/items/300x300/Hawks.webp" />
        <img src="/images/items/noimage.jpg" data-src="/images/items/300x300/61-3448.webp" />
      </div>
    </body></html>
    """


def _product_html_dom_only(
    *,
    name: str = "ACT Stage 2 EXTREME DUTY Organic Clutch Kit",
    price_text: str = "$549.00",
    image_path: str = "/images/items/485x485/GWR-031.webp",
) -> str:
    """Page with the JSON-LD block missing — DOM fallback path. The
    Interchange theme still ships the ``<h1>`` title, ``img#mainimage``
    hero, and ``<h5 class="price">`` node, which the adapter must fall
    back to when ``extract_json_ld_product`` returns None."""
    return f"""
    <html><head>
      <title>Good-Win Racing</title>
      <meta name="description" content="Miata Performance Part: Bargain Bin - Price: {price_text}" />
    </head><body>
      <h1><span class="matrix_description">{name}</span></h1>
      <img id="mainimage" src="{image_path}" alt="{name}" />
      <div class="cat_item_price">
        <p class="retail_price">$599.00</p>
        <h5 class="price">{price_text}</h5>
      </div>
    </body></html>
    """


def _category_html_with_products(*, skus: tuple[str, ...] = ("61-3447", "13-1063", "BB1221")) -> str:
    """Reproduce the category browse page's product-card markup. Each
    card emits TWO hrefs pointing at the same product URL (the image
    wrap and the title link), always on the canonical www host and
    always with a trailing ``?id=<session>`` query string. The
    adapter's extractor must dedupe and must strip the query."""
    cards = []
    for sku in skus:
        cards.append(
            f'<div class="cat_item">'
            f'<a href="https://www.good-win-racing.com/Mazda-Performance-Part/{sku}.html?id=uCS3LnpB">'
            f'<img src="/images/items/noimage.jpg" /></a>'
            f'<h6><a href="https://www.good-win-racing.com/Mazda-Performance-Part/{sku}.html?id=uCS3LnpB">'
            f"Product {sku}</a></h6></div>"
        )
    return f"<html><body>{''.join(cards)}</body></html>"


class TestProductUrlShape:
    """The singular ``/Mazda-Performance-Part/`` path shape is the only
    form that should enter the parse pipeline."""

    def test_canonical_product_url_accepted(self) -> None:
        assert _is_product_url(PRODUCT_URL)

    def test_bare_host_accepted(self) -> None:
        # good-win-racing.com 302s to www., but the extension may
        # capture either form — both must route here.
        assert _is_product_url("https://good-win-racing.com/Mazda-Performance-Part/61-3447.html")

    def test_letter_prefixed_sku_accepted(self) -> None:
        # ``BB1221`` (bargain bin) and ``GWR-031`` (own-brand) both live
        # in the wild — the SKU character class must stay permissive.
        assert _is_product_url("https://www.good-win-racing.com/Mazda-Performance-Part/BB1221.html")
        assert _is_product_url("https://www.good-win-racing.com/Mazda-Performance-Part/GWR-031.html")

    def test_plural_category_path_rejected(self) -> None:
        # The *plural* ``Mazda-Performance-Parts`` path is the category
        # shape — must never be parsed as a product.
        assert not _is_product_url(CATEGORY_URL)

    def test_plural_top_level_rejected(self) -> None:
        assert not _is_product_url("https://www.good-win-racing.com/Mazda-Performance-Parts/Miata/Brakes.html")

    def test_non_product_root_rejected(self) -> None:
        assert not _is_product_url("https://www.good-win-racing.com/mazda/miata/contact.html")

    def test_off_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/Mazda-Performance-Part/61-3447.html")


class TestCategoryUrlShape:
    """The plural ``/Mazda-Performance-Parts/`` path is the category
    browse shape that the sitemap walk should target for link extraction."""

    def test_depth4_category_accepted(self) -> None:
        assert _is_category_url(CATEGORY_URL)

    def test_depth3_category_accepted(self) -> None:
        assert _is_category_url("https://www.good-win-racing.com/Mazda-Performance-Parts/Miata/Brakes.html")

    def test_singular_product_path_rejected(self) -> None:
        # The singular path is the product shape, not the category.
        assert not _is_category_url(PRODUCT_URL)


class TestHostRouting:
    """``adapter_name_for_product_url`` must route both good-win-racing
    hosts to ``goodwinracing``."""

    def test_www_host_routes(self) -> None:
        assert adapter_name_for_product_url(PRODUCT_URL) == "goodwinracing"

    def test_bare_host_routes(self) -> None:
        assert (
            adapter_name_for_product_url("https://good-win-racing.com/Mazda-Performance-Part/61-3447.html")
            == "goodwinracing"
        )


class TestCategoryLinkExtraction:
    """The sitemap walks category pages and harvests product links.
    The adapter must handle the common "same product linked twice per
    card" pattern and strip the ``?id=<session>`` query string."""

    def test_extracts_all_distinct_product_urls(self) -> None:
        html = _category_html_with_products(skus=("61-3447", "13-1063", "BB1221"))
        urls = _extract_product_links(html)
        assert urls == [
            "https://www.good-win-racing.com/Mazda-Performance-Part/61-3447.html",
            "https://www.good-win-racing.com/Mazda-Performance-Part/13-1063.html",
            "https://www.good-win-racing.com/Mazda-Performance-Part/BB1221.html",
        ]

    def test_dedupes_repeated_hrefs(self) -> None:
        # Each product card emits two hrefs for the same URL; dedup must
        # collapse them in document order so we don't fetch twice.
        html = _category_html_with_products(skus=("61-3447",))
        assert _extract_product_links(html) == [
            "https://www.good-win-racing.com/Mazda-Performance-Part/61-3447.html",
        ]

    def test_ignores_non_product_links(self) -> None:
        # A page might link to category peers in a sidebar; those must
        # NOT show up in the discovered product list.
        html = (
            '<a href="/Mazda-Performance-Parts/Miata/Brakes/Pads.html">Pads</a>'
            '<a href="https://www.good-win-racing.com/Mazda-Performance-Part/61-3447.html">Product</a>'
        )
        assert _extract_product_links(html) == [
            "https://www.good-win-racing.com/Mazda-Performance-Part/61-3447.html",
        ]


class TestParseJsonLdPath:
    """Primary parse path: the JSON-LD Product block carries every field
    we need and wins over DOM / meta sources."""

    def test_full_parse(self) -> None:
        result = GoodWinRacingAdapter().parse_product_page(_product_html_with_json_ld(), PRODUCT_URL)
        assert result is not None
        assert result.name == "DBA XP Brake Pads - Rear"
        assert result.part_number == "61-3447"
        assert result.part_manufacturer == "DBA"
        # $89.00 → 8900 cents. JSON-LD offers.price is authoritative.
        assert result.price_cents == 8900
        assert result.description is not None and "DBA" in result.description
        assert result.image_urls == ["https://www.good-win-racing.com/images/items/485x485/61-3441.webp"]
        assert result.product_url == PRODUCT_URL

    def test_brand_passed_through_unchanged(self) -> None:
        # Good-Win is a reseller — the JSON-LD brand (EBC, ACT, Jackson
        # Racing, …) is the real manufacturer and must not be overridden
        # by a hard-coded default.
        html = _product_html_with_json_ld(brand="Jackson Racing", name="Jackson Racing Supercharger")
        result = GoodWinRacingAdapter().parse_product_page(html, PRODUCT_URL)
        assert result is not None
        assert result.part_manufacturer == "Jackson Racing"

    def test_related_product_thumbnails_not_included(self) -> None:
        # The fixture embeds related-product thumbnails in a sibling
        # block. Only the JSON-LD ``image`` should appear in the gallery.
        result = GoodWinRacingAdapter().parse_product_page(_product_html_with_json_ld(), PRODUCT_URL)
        assert result is not None
        assert result.image_urls is not None
        assert len(result.image_urls) == 1
        assert "Hawks" not in result.image_urls[0]


class TestParseDomFallbackPath:
    """The JSON-LD block is dropped on a small subset of pages; the DOM
    fallback recovers name + price + image from the theme's stable nodes."""

    def test_name_price_image_recovered(self) -> None:
        result = GoodWinRacingAdapter().parse_product_page(_product_html_dom_only(), PRODUCT_URL)
        assert result is not None
        assert result.name == "ACT Stage 2 EXTREME DUTY Organic Clutch Kit"
        # DOM price comes from ``h5.price`` (current) not ``retail_price`` (MSRP strike-through).
        assert result.price_cents == 54900
        assert result.image_urls == ["https://www.good-win-racing.com/images/items/485x485/GWR-031.webp"]
        # DOM path can't recover brand; dedupe keeps working off part_number elsewhere.
        assert result.part_manufacturer is None
        assert result.part_number is None

    def test_meta_description_used_when_json_ld_absent(self) -> None:
        result = GoodWinRacingAdapter().parse_product_page(_product_html_dom_only(), PRODUCT_URL)
        assert result is not None
        assert result.description is not None
        assert "Miata Performance Part" in result.description


class TestParseGuards:
    """Defensive checks — bad input can't crash or pollute the catalog."""

    def test_category_url_returns_none(self) -> None:
        # Running a category page (caught by archive rescrape with a
        # wrong URL) through the adapter must not return a ScrapedPayload.
        result = GoodWinRacingAdapter().parse_product_page(_product_html_with_json_ld(), CATEGORY_URL)
        assert result is None

    def test_empty_dom_returns_none(self) -> None:
        html = "<html><body><p>Nothing product-shaped here.</p></body></html>"
        assert GoodWinRacingAdapter().parse_product_page(html, PRODUCT_URL) is None


class TestAdapterFetcherTier:
    """Cloudflare managed challenge blocks plain HTTP; ``tls`` tier is required."""

    def test_declares_tls_tier(self) -> None:
        assert GoodWinRacingAdapter.FETCHER_TIER == "tls"
