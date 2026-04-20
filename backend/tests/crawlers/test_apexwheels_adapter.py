"""
Tests for apexwheels.com adapter: host routing (including the legacy
apexraceparts.com domain), URL shape guard, manufacturer collapse, JSON-LD
parsing, and DOM/og fallback.

Apex rebranded from "Apex Race Parts" → "Apex Wheels" and moved off Shopify
onto a Nuxt + Sanity + Vercel stack. Live crawling is gated on FlareSolverr
(``FETCHER_TIER = "browser"``) because every surface on apexwheels.com —
including ``/robots.txt`` and ``/sitemap.xml`` — returns the Vercel
Security Checkpoint JS challenge to plain HTTP clients.

Tests run against synthetic HTML modeled on the real JSON-LD ``[{Product}]``
block Apex emits (confirmed via a wayback capture of ``/wheels/flow-formed/
classic-line/arc-8`` — see ``site_problem_notes/apexwheels.md``).
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier2_browser.apexwheels import (
    ApexWheelsAdapter,
    _is_product_url,
    _normalize_part_manufacturer,
)

SAMPLE_URL = "https://apexwheels.com/wheels/flow-formed/classic-line/arc-8"
LEGACY_URL = "https://www.apexraceparts.com/products/arc-8-forged"


def _product_html(
    *,
    name: str = "ARC-8 Wheels",
    brand: str | None = None,
    sku: str = "ARC81710ET25-5120-7256-M-AN",
    price: str = "334",
    description: str = "Our best seller for over 15 years, the Apex ARC-8 combines low weight with high strength.",
    image: str = "https://cdn.sanity.io/images/c8ihu5xk/production/239076efec-2000x2000.png",
) -> str:
    """
    Synthetic page mirroring Nuxt's JSON-LD ``[{Product}]`` list shape on
    apexwheels.com. ``brand`` is optional because the real pages don't emit
    one — the adapter defaults the manufacturer to the canonical ``"Apex"``.
    """
    brand_field = f'"brand":{{"@type":"Brand","name":"{brand}"}},' if brand is not None else ""
    return f"""
    <html><head>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{description}">
      <meta property="og:image" content="{image}">
      <script type="application/ld+json">
      [{{
        "@context":"https://schema.org/",
        "@type":"Product",
        "name":"{name}",
        "description":"{description}",
        {brand_field}
        "sku":"{sku}",
        "image":["{image}"],
        "offers":{{"@type":"Offer","priceCurrency":"USD","price":{price},"availability":"https://schema.org/InStock"}}
      }}]
      </script>
    </head><body><h1>{name}</h1></body></html>
    """


class TestAdapterRegistration:
    """Both the new and legacy hosts route to this adapter."""

    def test_apexwheels_host_maps_to_apexwheels(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "apexwheels"

    def test_www_apexwheels_host_maps_to_apexwheels(self) -> None:
        assert adapter_name_for_product_url("https://www.apexwheels.com/accessories/wheel-hardware") == "apexwheels"

    def test_legacy_apexraceparts_host_still_routes_here(self) -> None:
        # Archive-replay or still-cached extension submissions on the old
        # host must not fall through to the generic parser.
        assert adapter_name_for_product_url(LEGACY_URL) == "apexwheels"

    def test_unrelated_host_does_not_map(self) -> None:
        assert adapter_name_for_product_url("https://example.com/wheels/foo") != "apexwheels"


class TestProductUrlGuard:
    """
    Shape guard accepts:
      - /wheels/<tier>/<line>/<model>      (4 segments)
      - /accessories/<subcat>               (2 segments)
      - legacy apexraceparts.com/products/<handle> for archive routing
    """

    def test_wheels_four_segment_path_is_product(self) -> None:
        assert _is_product_url(SAMPLE_URL)
        assert _is_product_url("https://apexwheels.com/wheels/forged/sprint-line/ec-7rs")

    def test_wheels_category_paths_rejected(self) -> None:
        # Category landings at 2- and 3-segment depth under /wheels/ list
        # several models — they're not single shoppable products.
        assert not _is_product_url("https://apexwheels.com/wheels/flow-formed")
        assert not _is_product_url("https://apexwheels.com/wheels/flow-formed/classic-line")

    def test_accessories_subcategory_is_product(self) -> None:
        assert _is_product_url("https://apexwheels.com/accessories/wheel-hardware")
        assert _is_product_url("https://apexwheels.com/accessories/hubcentric-wheel-centering-rings")

    def test_root_and_unrelated_paths_rejected(self) -> None:
        assert not _is_product_url("https://apexwheels.com/")
        assert not _is_product_url("https://apexwheels.com/cart")
        assert not _is_product_url("https://apexwheels.com/blog/company-news/apex-wheels-rennsport-reunion-7-recap")

    def test_legacy_shopify_url_accepted_for_archive_routing(self) -> None:
        # The old /products/<handle> URLs no longer resolve, but captured
        # HTML from the archive still needs to route to this adapter so the
        # parser can replay stored pages.
        assert _is_product_url(LEGACY_URL)

    def test_non_apex_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/wheels/flow-formed/classic-line/arc-8")


class TestNormalizePartManufacturer:
    """
    Apex's vendor field spans ``Apex``, ``APEX``, ``Apex Wheels`` (new
    rebrand), and ``Apex Race Parts`` (old brand) — collapse them all to
    the single canonical ``"Apex"`` row without losing rare co-branded
    SKUs.
    """

    def test_empty_brand_defaults_to_apex(self) -> None:
        assert _normalize_part_manufacturer("") == "Apex"
        assert _normalize_part_manufacturer(None) == "Apex"

    def test_all_apex_variants_collapse(self) -> None:
        for variant in (
            "Apex",
            "APEX",
            "apex",
            "Apex Wheels",
            "apex wheels",
            "apexwheels",
            "Apex Race Parts",
            "apex race parts",
            "apexraceparts",
        ):
            assert _normalize_part_manufacturer(variant) == "Apex", variant

    def test_third_party_brand_passes_through(self) -> None:
        # Co-branded / resold SKUs (PFC pads, G-LOC, Motul) surface the
        # real third-party row rather than getting swallowed under "Apex".
        assert _normalize_part_manufacturer("PFC") == "PFC"
        assert _normalize_part_manufacturer("Motul") == "Motul"

    def test_whitespace_around_variant_still_collapses(self) -> None:
        assert _normalize_part_manufacturer("  Apex Wheels  ") == "Apex"


class TestFetcherTier:
    """Live crawling requires FlareSolverr; adapter must declare the browser tier."""

    def test_declares_browser_tier(self) -> None:
        assert ApexWheelsAdapter.FETCHER_TIER == "browser"


class TestDiscoverStub:
    """Discovery is a no-op until FlareSolverr is wired up."""

    def test_yields_no_urls(self) -> None:
        # Skip __init__ to avoid constructing the FlareSolverr fetcher,
        # which raises when FLARESOLVERR_URL isn't set in the test env.
        adapter = ApexWheelsAdapter.__new__(ApexWheelsAdapter)
        assert list(adapter.discover_product_urls()) == []


class TestParseProductPage:
    """End-to-end parse: synthetic (and real-shape) HTML → ScrapedPayload."""

    def _adapter(self) -> ApexWheelsAdapter:
        # Never hits the network in these tests — bypass fetcher construction.
        return ApexWheelsAdapter.__new__(ApexWheelsAdapter)

    def test_json_ld_parses(self) -> None:
        result = self._adapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "ARC-8 Wheels"
        assert result.part_number == "ARC81710ET25-5120-7256-M-AN"
        assert result.part_manufacturer == "Apex"
        assert result.price_cents == 33400
        assert result.product_url == SAMPLE_URL
        assert result.image_urls and result.image_urls[0].startswith("https://cdn.sanity.io/")

    def test_brand_variant_collapsed_to_canonical(self) -> None:
        # Some archived pages / extension submissions may carry an explicit
        # vendor field spelling — all self-spellings collapse.
        html = _product_html(brand="Apex Race Parts")
        result = self._adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Apex"

    def test_missing_brand_defaults_to_apex(self) -> None:
        # The real apexwheels.com JSON-LD omits ``brand`` — exercised here
        # with brand=None so the field is absent entirely. The default is
        # "Apex" rather than the title-first-word heuristic (which would
        # land on "ARC-8", a model code, not a manufacturer).
        html = _product_html(brand=None)
        result = self._adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Apex"

    def test_third_party_brand_passes_through(self) -> None:
        # Co-branded SKU — the third-party brand survives so the part
        # lands on the real manufacturer row.
        html = _product_html(brand="PFC", name="PFC Track Brake Pads")
        result = self._adapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "PFC"

    def test_legacy_url_parses(self) -> None:
        # Archive-replay path: the URL is the old Shopify shape but the
        # HTML body (e.g. a snapshot) is what the parser sees.
        result = self._adapter().parse_product_page(_product_html(), LEGACY_URL)
        assert result is not None
        assert result.product_url == LEGACY_URL

    def test_non_product_url_returns_none(self) -> None:
        # Category pages and blog posts must not slip through even when the
        # HTML body happens to contain a JSON-LD Product block.
        result = self._adapter().parse_product_page(
            _product_html(),
            "https://apexwheels.com/wheels/flow-formed",
        )
        assert result is None

    def test_missing_jsonld_falls_back_to_dom(self) -> None:
        # No JSON-LD — adapter should still pull title / description from
        # og: meta tags and default the manufacturer to Apex.
        html = """
        <html><head>
          <meta property="og:title" content="EC-7 Wheels">
          <meta property="og:description" content="Flow-formed EC-7 wheels for track duty.">
          <meta property="og:image" content="https://cdn.sanity.io/images/ec-7.png">
        </head><body>
          <h1>EC-7 Wheels</h1>
          <p>SKU: EC71710ET25-5120-7256-M-AN</p>
        </body></html>
        """
        result = self._adapter().parse_product_page(
            html,
            "https://apexwheels.com/wheels/flow-formed/classic-line/ec-7",
        )
        assert result is not None
        assert result.name == "EC-7 Wheels"
        assert result.part_manufacturer == "Apex"
        assert result.part_number == "EC71710ET25-5120-7256-M-AN"

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        result = self._adapter().parse_product_page(html, SAMPLE_URL)
        assert result is None
