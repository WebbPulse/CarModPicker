"""
Tests for hasportperformance.com adapter: WordPress + WooCommerce + Yoast
JSON-LD. Covers host routing (including the ``hasport.com`` alias that 301s
to ``hasportperformance.com``), URL-shape guard, canonicalization, the
leading-uppercase-token SKU extraction that replaces the useless numeric
JSON-LD ``sku``, hardcoded ``"Hasport"`` manufacturer stamping, WooCommerce
gallery anchor harvesting, and end-to-end Product parsing.
"""

from bs4 import BeautifulSoup

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.hasport import (
    HasportAdapter,
    _canonical_product_url,
    _extract_gallery_images,
    _extract_leading_sku,
    _is_product_url,
)

SAMPLE_URL = "https://hasportperformance.com/products/fdstk/"


def _product_html(
    *,
    name: str = "FDSTK Stock replacement mount kit for 2006-2011 Civic Si",
    description: str = (
        "Mount kit for replacement of the stock mount in the 2006-2011 Civic Si. "
        "Uses urethane bushings for a firmer feel with minimal NVH penalty."
    ),
    sku: int = 643,
    price: str = "633.33",
    json_ld_image: str = "https://hasportperformance.com/wp-content/uploads/2019/09/fdstk.jpg",
    gallery_full_urls: tuple[str, ...] = (
        "https://hasportperformance.com/wp-content/uploads/2019/09/fdstk.jpg",
        "https://hasportperformance.com/wp-content/uploads/2019/09/fdstk-alt.jpg",
    ),
    url: str = SAMPLE_URL,
) -> str:
    """
    Minimal Hasport product page. Reproduces the real page's two JSON-LD
    blocks (Yoast WebPage graph + unclassed Product graph) so
    ``extract_json_ld_product`` exercises the same selection path it will in
    production. The gallery block mirrors WooCommerce's real DOM: each
    ``.woocommerce-product-gallery__image`` div wraps an ``<a>`` to the
    full-size upload and an ``<img>`` to the resized thumbnail. Site-chrome
    ``<img>`` tags are deliberately added to prove they are not swept in
    (we only look at gallery anchors, not DOM-wide images).
    """
    gallery_divs = "".join(
        (
            '<div class="woocommerce-product-gallery__image">'
            f'<a href="{full}"><img src="{full.replace(".jpg", "-600x450.jpg")}" /></a>'
            "</div>"
        )
        for full in gallery_full_urls
    )
    return f"""
    <html><head>
      <title>{name} &ndash; Hasport Performance</title>
      <meta property="og:type" content="article" />
      <meta property="og:url" content="{url}" />
      <meta property="og:image" content="{json_ld_image}" />
      <script type="application/ld+json" class="yoast-schema-graph">{{
        "@context":"https://schema.org","@graph":[
          {{"@type":"WebPage","@id":"{url}","url":"{url}","name":"{name}"}},
          {{"@type":"Organization","name":"Hasport Performance"}}
        ]
      }}</script>
    </head><body>
      <header>
        <img src="https://hasportperformance.com/wp-content/uploads/2020/02/Hasport-Mount-Man.png" alt="logo" />
      </header>
      <main>
        <h1 class="product_title entry-title">{name}</h1>
        <div class="woocommerce-product-gallery">
          <figure class="woocommerce-product-gallery__wrapper">{gallery_divs}</figure>
        </div>
      </main>
      <script type="application/ld+json">{{
        "@context":"https://schema.org/","@graph":[
          {{"@type":"BreadcrumbList","itemListElement":[]}},
          {{
            "@context":"https://schema.org/",
            "@type":"Product",
            "name":"{name}",
            "url":"{url}",
            "description":"{description}",
            "image":"{json_ld_image}",
            "sku":{sku},
            "offers":[{{
              "@type":"Offer",
              "price":"{price}",
              "priceCurrency":"USD",
              "availability":"http://schema.org/InStock",
              "url":"{url}"
            }}]
          }}
        ]
      }}</script>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-based routing — both the canonical host and the 301 alias map here."""

    def test_canonical_host_routes_to_hasport(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "hasport"

    def test_alias_host_routes_to_hasport(self) -> None:
        # hasport.com 301-redirects to hasportperformance.com, but an
        # extension capture (or a legacy link) can still land on the alias.
        assert adapter_name_for_product_url("https://hasport.com/products/fdstk/") == "hasport"

    def test_www_prefix_routes_to_hasport(self) -> None:
        assert adapter_name_for_product_url("https://www.hasportperformance.com/products/fdstk/") == "hasport"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/products/fdstk/") == "generic"


class TestIsProductUrl:
    """URL-shape guard: ``/products/<single-slug>/`` only, on the Hasport hosts."""

    def test_canonical_product_url_accepted(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_alias_host_accepted(self) -> None:
        assert _is_product_url("https://hasport.com/products/egk-k-series-mount-kit/")

    def test_trailing_slash_optional(self) -> None:
        assert _is_product_url("https://hasportperformance.com/products/fdstk")

    def test_shop_landing_rejected(self) -> None:
        # ``/products/`` with no slug is the shop landing, not a product.
        assert not _is_product_url("https://hasportperformance.com/products/")

    def test_category_url_rejected(self) -> None:
        assert not _is_product_url("https://hasportperformance.com/product-category/mounts/")

    def test_offsite_rejected(self) -> None:
        assert not _is_product_url("https://example.com/products/fdstk/")


class TestCanonicalProductUrl:
    """Query-strip + alias-host fold + trailing-slash normalization for dedupe."""

    def test_alias_host_folds_to_canonical(self) -> None:
        assert (
            _canonical_product_url("https://hasport.com/products/fdstk/")
            == "https://hasportperformance.com/products/fdstk/"
        )

    def test_query_and_fragment_dropped(self) -> None:
        assert (
            _canonical_product_url("https://hasportperformance.com/products/fdstk/?utm_source=x#frag")
            == "https://hasportperformance.com/products/fdstk/"
        )

    def test_trailing_slash_added(self) -> None:
        # Yoast sitemap entries are trailing-slashed, but some captures
        # drop it — canonicalize to the sitemap shape.
        assert (
            _canonical_product_url("https://hasportperformance.com/products/fdstk")
            == "https://hasportperformance.com/products/fdstk/"
        )


class TestExtractLeadingSku:
    """
    JSON-LD ``sku`` is the WooCommerce post_id (e.g. 643) — unusable. The
    real SKU is the leading uppercase token of the product name.
    """

    def test_single_token_sku(self) -> None:
        assert _extract_leading_sku("FDSTK Stock replacement mount kit for 2006-2011 Civic Si") == "FDSTK"

    def test_three_letter_token(self) -> None:
        assert _extract_leading_sku("EGK K-series Mount Kit 92-95 Civic, 94-01 Integra, and Del Sol") == "EGK"

    def test_alphanumeric_token(self) -> None:
        assert _extract_leading_sku("P72BB Bolt-in K-swap bracket") == "P72BB"

    def test_descriptive_title_returns_none(self) -> None:
        # "Urethane Mount Bushings" has no uppercase-alnum SKU prefix;
        # better to emit no SKU than a noisy word.
        assert _extract_leading_sku("Urethane Mount Bushings") is None

    def test_empty_returns_none(self) -> None:
        assert _extract_leading_sku("") is None
        assert _extract_leading_sku("   ") is None

    def test_single_letter_rejected(self) -> None:
        # Single letters (``"A widget"``) could easily be an article word,
        # not a SKU — require ≥2 chars.
        assert _extract_leading_sku("A Widget") is None


class TestExtractGalleryImages:
    """Gallery sweep: only ``.woocommerce-product-gallery__image > a[href]`` links."""

    def test_collects_full_res_anchors(self) -> None:
        soup = BeautifulSoup(_product_html(), "html.parser")
        images = _extract_gallery_images(soup)
        assert images == [
            "https://hasportperformance.com/wp-content/uploads/2019/09/fdstk.jpg",
            "https://hasportperformance.com/wp-content/uploads/2019/09/fdstk-alt.jpg",
        ]

    def test_site_chrome_img_is_skipped(self) -> None:
        # The synthetic HTML includes a header logo ``<img>``; only anchors
        # inside ``.woocommerce-product-gallery__image`` should count.
        soup = BeautifulSoup(_product_html(), "html.parser")
        images = _extract_gallery_images(soup)
        for img in images:
            assert "Hasport-Mount-Man" not in img

    def test_missing_gallery_returns_empty(self) -> None:
        soup = BeautifulSoup("<html><body><h1>No gallery</h1></body></html>", "html.parser")
        assert _extract_gallery_images(soup) == []


class TestParseProductPage:
    """End-to-end parsing against synthetic Hasport HTML modeled on real pages."""

    def test_full_page_parses(self) -> None:
        result = HasportAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "FDSTK Stock replacement mount kit for 2006-2011 Civic Si"
        assert result.part_manufacturer == "Hasport"
        # JSON-LD sku=643 is the post_id and must be discarded in favor of
        # the leading-token extraction from the title.
        assert result.part_number == "FDSTK"
        assert result.price_cents == 63333
        assert result.description is not None
        assert "Mount kit for replacement" in result.description
        assert result.image_urls is not None
        assert result.image_urls[0] == "https://hasportperformance.com/wp-content/uploads/2019/09/fdstk.jpg"

    def test_alias_host_url_canonicalized(self) -> None:
        # An extension capture on hasport.com must store the canonical
        # hasportperformance.com URL so both resolve to the same row.
        alias_url = "https://hasport.com/products/fdstk/?utm=x"
        result = HasportAdapter().parse_product_page(_product_html(url=alias_url), alias_url)
        assert result is not None
        assert result.product_url == SAMPLE_URL

    def test_descriptive_title_emits_no_sku(self) -> None:
        # "Urethane Mount Bushings" has no uppercase-code prefix; we'd
        # rather store None than ship a noisy word as a SKU.
        html = _product_html(name="Urethane Mount Bushings")
        result = HasportAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Hasport"
        assert result.part_number is None

    def test_gallery_wins_over_json_ld_image(self) -> None:
        # DOM gallery has two images; JSON-LD emits one. The gallery sweep
        # should replace the single JSON-LD image, not append to it.
        result = HasportAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        assert len(result.image_urls) == 2

    def test_json_ld_image_fallback_when_gallery_missing(self) -> None:
        html = _product_html(gallery_full_urls=())
        result = HasportAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls == ["https://hasportperformance.com/wp-content/uploads/2019/09/fdstk.jpg"]

    def test_non_product_url_returns_none(self) -> None:
        # Category pages share the same template shell; the URL guard must
        # stop the adapter before it parses them as products.
        assert (
            HasportAdapter().parse_product_page(
                _product_html(), "https://hasportperformance.com/product-category/mounts/"
            )
            is None
        )

    def test_missing_json_ld_returns_none(self) -> None:
        # Without the Product JSON-LD the page could be a Yoast-only landing
        # variant; skip it rather than fabricating a payload from DOM alone.
        html = '<html><body><h1 class="product_title">Stray</h1></body></html>'
        assert HasportAdapter().parse_product_page(html, SAMPLE_URL) is None
