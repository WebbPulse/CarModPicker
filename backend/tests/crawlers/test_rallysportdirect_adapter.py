"""
Tests for rallysportdirect.com (RallySport Direct) adapter: host routing,
fetcher tier, Shopify sitemap child filtering, Shopify CDN image canonicalization,
JSON-LD Product parsing, and the multi-brand reseller brand policy.

RSD is a Shopify storefront (``/products/<handle>`` URLs, ``/cdn/shop/`` image
CDN, ``/sitemap.xml`` sitemap index) with Cloudflare fronting but no challenge
for plain ``requests``. Tests run against *synthetic* HTML modeled on a real
product page so they don't depend on live network access.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.rallysportdirect import (
    RallysportDirectAdapter,
    _canonical_image_url,
    _gtin_from_json_ld,
    _is_product_child_sitemap,
)

SAMPLE_URL = (
    "https://www.rallysportdirect.com/products/" "acl-5m8309h-50-acl-race-main-bearing-set-50-oversized-position-5"
)


def _product_page_html(
    *,
    name: str = "ACL Race Main Bearings Undersized -.020in - Subaru Models (inc. 2002-2014 WRX / 2004-2021 STI)",
    sku: str = "ACL5M8309H-.50",
    brand: str = "ACL",
    description: str = (
        "ACL Race Main Bearings Undersized -.020in Subaru Models. RallySport Direct carries a "
        "great variety of ACL Bearings to help you with your latest engine rebuild."
    ),
    price: str = "150.83",
    gtin: str = "9315726153185",
    hero_image: str = "https://www.rallysportdirect.com/cdn/shop/products/cdd4eaa54870ce2bbcbd9ecfc3b9cd4f.jpg?v=1694806514&width=1920",
    gallery_images: tuple[str, ...] = (
        "//www.rallysportdirect.com/cdn/shop/products/cdd4eaa54870ce2bbcbd9ecfc3b9cd4f.jpg?v=1694806514&width=1946",
        "//www.rallysportdirect.com/cdn/shop/products/00e1e912f8668afdf16e69d6656d9607.jpg?v=1694806514&width=1946",
        "//www.rallysportdirect.com/cdn/shop/products/7da9336396392269c592151d73ede8f4.jpg?v=1694806514&width=1946",
    ),
    include_json_ld: bool = True,
    include_brand: bool = True,
    include_gtin: bool = True,
) -> str:
    """Minimal page mirroring RSD's Shopify Dawn-lineage theme."""
    brand_field = f'"brand": {{"@type": "Brand", "name": "{brand}"}},' if include_brand else ""
    gtin_field = f'"gtin": "{gtin}",' if include_gtin else ""
    json_ld = ""
    if include_json_ld:
        json_ld = f"""
        <script type="application/ld+json">
        {{
          "@context": "http://schema.org/",
          "@type": "Product",
          "name": "{name}",
          "sku": "{sku}",
          {brand_field}
          {gtin_field}
          "description": "{description}",
          "image": "{hero_image}",
          "offers": {{
            "@type": "Offer",
            "price": "{price}",
            "priceCurrency": "USD",
            "availability": "http://schema.org/InStock",
            "url": "{SAMPLE_URL}"
          }},
          "url": "{SAMPLE_URL}"
        }}
        </script>
        """
    gallery_imgs = "\n".join(f'<img src="{u}" srcset="{u} 1946w" alt="{brand}">' for u in gallery_images)
    return f"""
    <html><head>
      <meta property="og:type" content="product">
      <meta property="og:title" content="{name}">
      <meta property="og:image:secure_url" content="{hero_image}">
      <meta property="product:price:amount" content="{price}">
      {json_ld}
    </head><body>
      <h1>{name}</h1>
      <div class="product__media-wrapper">
        <ul class="product__media-list contains-media grid">
          {gallery_imgs}
        </ul>
      </div>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_www_host_routes_to_rallysportdirect(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "rallysportdirect"

    def test_bare_host_routes_to_rallysportdirect(self) -> None:
        # Bare host redirects to www in production, but the Chrome extension
        # and archive rescrape must still route correctly before the redirect
        # resolves.
        assert adapter_name_for_product_url("https://rallysportdirect.com/products/some-slug") == "rallysportdirect"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/rallysportdirect") == "generic"


class TestFetcherTier:
    """
    RSD is Cloudflare-fronted but passive — plain ``fetch_page`` returns 200
    on sitemap and product pages. Keep Tier-0.
    """

    def test_http_tier_default(self) -> None:
        assert RallysportDirectAdapter.FETCHER_TIER == "http"


class TestIsProductChildSitemap:
    """Discovery only follows ``sitemap_products_N.xml`` children of the Shopify index."""

    def test_product_children_accepted(self) -> None:
        assert _is_product_child_sitemap("https://www.rallysportdirect.com/sitemap_products_1.xml?from=1&to=9")
        assert _is_product_child_sitemap("https://www.rallysportdirect.com/sitemap_products_42.xml")

    def test_non_product_children_rejected(self) -> None:
        for bad in (
            "https://www.rallysportdirect.com/sitemap_pages_1.xml",
            "https://www.rallysportdirect.com/sitemap_collections_1.xml",
            "https://www.rallysportdirect.com/sitemap_blogs_1.xml",
            "https://www.rallysportdirect.com/products/some-slug",
        ):
            assert not _is_product_child_sitemap(bad), bad


class TestCanonicalImageUrl:
    """Shopify CDN URLs only; responsive-srcset params collapse to one canonical form."""

    def test_protocol_relative_upgraded_to_https(self) -> None:
        url = _canonical_image_url("//www.rallysportdirect.com/cdn/shop/products/a.jpg?v=1")
        assert url == "https://www.rallysportdirect.com/cdn/shop/products/a.jpg?v=1"

    def test_width_param_stripped(self) -> None:
        url = _canonical_image_url("https://www.rallysportdirect.com/cdn/shop/products/a.jpg?v=1&width=720")
        assert url == "https://www.rallysportdirect.com/cdn/shop/products/a.jpg?v=1"

    def test_non_shopify_cdn_rejected(self) -> None:
        # Third-party tracking pixels / site chrome that isn't on the Shopify CDN.
        assert _canonical_image_url("https://example.com/img.jpg") is None

    def test_site_chrome_rejected(self) -> None:
        assert _canonical_image_url("https://www.rallysportdirect.com/cdn/shop/files/logo-nav.svg") is None


class TestGtinFromJsonLd:
    """GTIN extraction is adapter-local — the shared helper drops the field."""

    def test_product_level_gtin(self) -> None:
        assert _gtin_from_json_ld({"gtin": "9315726153185"}) == "9315726153185"

    def test_variant_gtin13(self) -> None:
        # Some Shopify themes surface gtin13 instead of plain gtin.
        assert _gtin_from_json_ld({"gtin13": "0123456789012"}) == "0123456789012"

    def test_offer_level_gtin(self) -> None:
        # When the product-level keys are absent, the shipping offer often
        # still carries a GTIN.
        item = {"offers": {"@type": "Offer", "gtin": "0123456789012"}}
        assert _gtin_from_json_ld(item) == "0123456789012"

    def test_missing_returns_none(self) -> None:
        assert _gtin_from_json_ld({"name": "no gtin here"}) is None


class TestParseProductPage:
    """End-to-end parsing against real-shape Shopify JSON-LD + DOM gallery HTML."""

    def test_json_ld_primary_path(self) -> None:
        result = RallysportDirectAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("ACL Race Main Bearings Undersized")
        assert result.part_manufacturer == "ACL"
        assert result.part_number == "ACL5M8309H-.50"
        assert result.price_cents == 15083
        assert result.gtin == "9315726153185"
        assert result.product_url == SAMPLE_URL
        assert result.description is not None and "ACL Bearings" in result.description

    def test_third_party_brand_preserved(self) -> None:
        # RSD resells every Subaru-compatible line (Cobb, Perrin, GrimmSpeed,
        # Whiteline, Cusco, ...). JSON-LD ``brand.name`` must pass through —
        # no retailer house brand override.
        result = RallysportDirectAdapter().parse_product_page(
            _product_page_html(
                name="COBB Tuning AccessPORT V3 - Subaru WRX / STI",
                brand="COBB Tuning",
                sku="AP3-SUB-004",
            ),
            "https://www.rallysportdirect.com/products/cobb-tuning-accessport-v3-subaru-wrx-sti",
        )
        assert result is not None
        assert result.part_manufacturer == "COBB Tuning"
        assert result.part_number == "AP3-SUB-004"

    def test_dom_gallery_expands_beyond_json_ld_hero(self) -> None:
        # JSON-LD ships only the single hero image URL. The Shopify
        # ``.product__media-list`` slideshow has the full gallery, so the
        # adapter should expand past the hero.
        result = RallysportDirectAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        # Canonical form strips width=; the three distinct files collapse to
        # three URLs, and the hero og:image (same file #1) dedupes.
        paths = {u.split("?")[0] for u in result.image_urls}
        assert "https://www.rallysportdirect.com/cdn/shop/products/cdd4eaa54870ce2bbcbd9ecfc3b9cd4f.jpg" in paths
        assert "https://www.rallysportdirect.com/cdn/shop/products/00e1e912f8668afdf16e69d6656d9607.jpg" in paths
        assert "https://www.rallysportdirect.com/cdn/shop/products/7da9336396392269c592151d73ede8f4.jpg" in paths
        # width=N should be stripped on every URL (it's a responsive srcset
        # param, not a stable identity).
        assert all("width=" not in u for u in result.image_urls)

    def test_missing_brand_falls_back_to_heuristic(self) -> None:
        # Defensive: if the brand field ever goes missing, the title-heuristic
        # fallback should still produce a usable manufacturer. Real product
        # titles lead with the brand ("ACL Race...", "COBB Tuning...").
        html = _product_page_html(include_brand=False)
        result = RallysportDirectAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        # Title leads with "ACL" — heuristic or fallback should catch it.
        assert result.part_manufacturer is not None
        assert result.part_manufacturer  # non-empty

    def test_missing_gtin_returns_none_gtin(self) -> None:
        # Not every SKU has a GTIN — the adapter must not fabricate one when
        # JSON-LD omits the field.
        html = _product_page_html(include_gtin=False)
        result = RallysportDirectAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.gtin is None

    def test_missing_json_ld_returns_none(self) -> None:
        # Soft-404 / non-product pages have no Product JSON-LD; skip them so
        # the runner doesn't ingest a blank row.
        html = "<html><head><title>Page Not Found</title></head><body></body></html>"
        assert RallysportDirectAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_html_entity_in_name_decoded(self) -> None:
        # Shopify JSON-LD escapes ``&`` as ``\u0026`` — the shared helper
        # decodes HTML entities, so "WRX \u0026 STI" becomes "WRX & STI".
        html = _product_page_html(name="ACL Race Main Bearings - Subaru WRX \\u0026 STI")
        result = RallysportDirectAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert "&" in result.name
