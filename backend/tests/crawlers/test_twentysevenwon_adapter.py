"""
Tests for store.27won.com adapter: host routing, URL shape guard,
manufacturer collapse, JSON-LD parsing with CS-Cart gallery extraction, and
DOM/og fallback.

27WON's storefront is CS-Cart at ``store.27won.com`` (``www.27won.com`` is a
separate Squarespace marketing site with no products). Tests run against
synthetic HTML modeled on the schema.org ``Product`` block CS-Cart emits by
default, plus the ``/images/detailed/<product_id>/…`` gallery convention.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.twentysevenwon import (
    TwentySevenWonAdapter,
    _is_product_url,
    _normalize_part_manufacturer,
)

SAMPLE_URL = "https://store.27won.com/10th-gen-civic-performance-downpipe.html"


def _product_html(
    *,
    name: str = "2016-2021 Civic Turbo Performance Downpipe",
    brand: str = "27WON Performance",
    sku: str = "L15-6-209-11",
    price: str = "749.99",
    description: str = "Performance turbocharged engines love a free flowing exhaust and intake system.",
    image: str = "https://store.27won.com/images/detailed/17/3_inch_downpipe_for_1.5l_honda_Civic.jpg",
    extra_gallery_imgs: tuple[str, ...] = (
        "/images/detailed/17/Civic-Downpipe-CAD-1.PNG",
        "/images/detailed/17/27WON-Product-080917-FrontpipeADD-web_vef2-cr.jpg",
    ),
    related_thumb: str = "/images/thumbnails/345/467/detailed/19/Untitled-2.png",
) -> str:
    """
    Minimal page mirroring CS-Cart's default schema.org Product JSON-LD plus
    ``/images/detailed/<id>/…`` DOM gallery. The ``related_thumb`` points at a
    *different* product id — the gallery extractor must ignore it.
    """
    brand_field = f'"brand":{{"@type":"Brand","name":"{brand}"}},' if brand else ""
    store_base = "https://store.27won.com"
    extras_markup = "".join(f'<img src="{store_base}{p}">' for p in extra_gallery_imgs)
    related_markup = f'<img src="{store_base}{related_thumb}">'
    return f"""
    <html><head>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{description}">
      <meta property="og:image" content="{image}">
      <meta property="product:price:amount" content="{price}">
      <meta property="og:price:currency" content="USD">
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "{name}",
        "description": "{description}",
        {brand_field}
        "sku": "{sku}",
        "image": "{image}",
        "offers": {{
          "@type": "AggregateOffer",
          "price": "{price}",
          "priceCurrency": "USD",
          "availability": "https://schema.org/InStock"
        }}
      }}
      </script>
    </head><body>
      <h1>{name}</h1>
      <div class="product-details">
        <img src="{image}">
        {extras_markup}
      </div>
      <aside class="related-products">{related_markup}</aside>
    </body></html>
    """


class TestAdapterRegistration:
    """The host-to-adapter map routes every 27won.com page through this adapter."""

    def test_store_host_routes_to_27won(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "27won"

    def test_bare_host_routes_to_27won(self) -> None:
        # The host-routing map is intentionally broad (every 27won.com
        # subdomain maps here) so extension-submitted URLs from either the
        # marketing site or the store land on the same adapter.
        assert adapter_name_for_product_url("https://27won.com/products/foo") == "27won"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        # A host containing "27won" as a substring but not the actual domain
        # must not be mapped here.
        assert adapter_name_for_product_url("https://example.com/27won") == "generic"


class TestProductUrlGuard:
    """Shape guard: root-slug ``.html`` on ``store.27won.com`` is a product page."""

    def test_valid_product_url(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_root_slug_html_is_product_shape(self) -> None:
        assert _is_product_url("https://store.27won.com/some-handle.html")

    def test_nested_path_rejected(self) -> None:
        # Category listings expose nested paths — those are category pages,
        # not products.
        assert not _is_product_url("https://store.27won.com/civic-si-10th-gen/")
        assert not _is_product_url("https://store.27won.com/civic-si-10th-gen/foo.html")

    def test_store_closed_rejected(self) -> None:
        # robots.txt disallows this system page and so do we.
        assert not _is_product_url("https://store.27won.com/store_closed.html")

    def test_marketing_host_rejected(self) -> None:
        # The Squarespace marketing site has no products — rejecting this
        # host is the whole reason the adapter was rewritten.
        assert not _is_product_url("https://www.27won.com/products/fk8-civic-type-r-intake-manifold")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/foo.html")


class TestNormalizePartManufacturer:
    """
    27WON's vendor field is inconsistent (``27WON``, ``27WON Performance``,
    ``27 WON``, empty). ``_normalize_part_manufacturer`` collapses all self-
    spellings to a single canonical brand without losing rare co-branded SKUs.
    """

    def test_empty_brand_defaults_to_27won_performance(self) -> None:
        assert _normalize_part_manufacturer("") == "27WON Performance"
        assert _normalize_part_manufacturer(None) == "27WON Performance"

    def test_27won_variants_all_collapse(self) -> None:
        for variant in (
            "27WON",
            "27won",
            "27 WON",
            "27-WON",
            "27WON Performance",
            "27won performance",
            "27 Won Performance",
            "27WON Performance Inc",
            "27WON Performance, Inc.",
        ):
            assert _normalize_part_manufacturer(variant) == "27WON Performance", variant

    def test_third_party_brand_passes_through(self) -> None:
        # 27WON has shipped co-branded / collab SKUs with other Honda vendors.
        # A JSON-LD brand that isn't a 27WON self-spelling must survive so the
        # global part-manufacturer table gets a real third-party row rather
        # than being swallowed under 27WON's name.
        assert _normalize_part_manufacturer("Hondata") == "Hondata"
        assert _normalize_part_manufacturer("PRL Motorsports") == "PRL Motorsports"

    def test_whitespace_around_variant_still_collapses(self) -> None:
        assert _normalize_part_manufacturer("  27WON Performance  ") == "27WON Performance"


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape CS-Cart HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = TwentySevenWonAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("2016-2021 Civic")
        assert result.part_manufacturer == "27WON Performance"
        assert result.part_number == "L15-6-209-11"
        assert result.price_cents == 74999
        assert result.product_url == SAMPLE_URL
        assert result.image_urls
        # The gallery extractor picked up every /images/detailed/17/… reference
        # on the page and excluded the /images/thumbnails/…/detailed/19/…
        # related-product leak.
        assert all("/images/detailed/17/" in u for u in result.image_urls)
        assert not any("/detailed/19/" in u for u in result.image_urls)

    def test_brand_variant_collapsed_to_canonical(self) -> None:
        # Vendor field spelled "27WON" on this product — still maps to the
        # single canonical "27WON Performance" row.
        html = _product_html(brand="27WON")
        result = TwentySevenWonAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "27WON Performance"

    def test_missing_brand_defaults_to_27won_performance(self) -> None:
        # JSON-LD brand absent — the default kicks in rather than running the
        # title-first-word heuristic (which would pick "2016-2021" from the
        # title and fail the manufacturer rules, or land on a product word
        # like "Civic").
        html = _product_html(brand="")
        result = TwentySevenWonAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "27WON Performance"

    def test_third_party_brand_passed_through(self) -> None:
        # Co-branded SKU — the third-party brand survives verbatim so the
        # part lands on the real manufacturer row rather than being swallowed
        # under 27WON's name.
        html = _product_html(brand="Hondata", name="Hondata FlashPro for FK8 Civic Type R")
        result = TwentySevenWonAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Hondata"

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape pipeline must not feed category / nested-path URLs
        # here.
        result = TwentySevenWonAdapter().parse_product_page(
            _product_html(),
            "https://store.27won.com/civic-si-10th-gen/",
        )
        assert result is None

    def test_marketing_host_returns_none(self) -> None:
        # The marketing host has no products at all — guard against a
        # Chrome-extension submission accidentally routing there.
        result = TwentySevenWonAdapter().parse_product_page(
            _product_html(),
            "https://www.27won.com/products/fk8-civic-type-r-intake-manifold",
        )
        assert result is None

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD — adapter should still pull title / description / price
        # from og: meta tags and default the manufacturer to 27WON Performance.
        html = """
        <html><head>
          <meta property="og:title" content="27WON FL5 Civic Type R Short Shifter">
          <meta property="og:description" content="CNC-machined short shifter for the 2023+ FL5 Civic Type R 6-speed.">
          <meta property="og:image" content="https://store.27won.com/images/detailed/42/fl5-shifter.jpg">
          <meta property="product:price:amount" content="329.00">
        </head><body>
          <h1>27WON FL5 Civic Type R Short Shifter</h1>
          <p>SKU: 27W-SS-FL5-001</p>
        </body></html>
        """
        result = TwentySevenWonAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("27WON FL5")
        assert result.part_manufacturer == "27WON Performance"
        assert result.part_number == "27W-SS-FL5-001"
        assert result.price_cents == 32900

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert TwentySevenWonAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """27WON stays on plain HTTP (tier0); promote to ``tls`` if CS-Cart fires."""

    def test_declares_http_tier(self) -> None:
        # Default tier — store.27won.com answers plain requests fetches for
        # the sitemap, robots.txt, and product pages today. If that changes,
        # flip FETCHER_TIER to "tls".
        assert TwentySevenWonAdapter.FETCHER_TIER == "http"
