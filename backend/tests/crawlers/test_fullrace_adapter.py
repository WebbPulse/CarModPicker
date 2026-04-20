"""
Tests for full-race.com adapter: Magento 2 meta-tag + DOM parsing, Staylime
gallery regex-sweep (the theme renders the carousel client-side so a plain
``<img>`` walk misses every image past the hero), and the
``/store/<categories>`` vs root-slug product-URL distinction.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.fullrace import (
    FULLRACE_HOUSE_BRAND,
    FullRaceAdapter,
    _canonical_image_path,
    _is_product_url,
    _resolve_part_manufacturer,
)

SAMPLE_URL = "https://www.full-race.com/tial-mvs-38mm-external-wastegate"


def _product_page_html(
    *,
    title: str = "TiAL MVS 38mm External Wastegate",
    sku: str = "MVS",
    price: str = "319.97",
    short_description: str = "TiAL MVS 38mm External Wastegate with Full Race logo",
    detail_html: str = (
        "<p><strong>TiAL's MV-S wastegate offers a whole lot of performance in a very small package</strong></p>"
        "<p>This ultra-compact wastegate provides enormous flow capacity yet stands only 3.7&quot; in height "
        "(vs traditional 38mm WG's at 4.85&quot;). V-band wastegate and manifold connections mean reliable easy "
        "sealing — no more bolts or gaskets. Each wastegate comes with a full set of springs.</p>"
    ),
    hero_image: str = (
        "https://www.full-race.com/media/catalog/product/cache/"
        "908259106824c8afa194b0cd869f41b6/t/i/tial_mvs_wastegates_38mm.jpg"
    ),
    inline_script_images: tuple[str, ...] = (
        "https://www.full-race.com/media/catalog/product/cache/"
        "a6054347c40e40fa7e8fb31f82707f9e/t/i/tial_mvs_wastegates_38mm.jpg",
        "https://www.full-race.com/media/catalog/product/cache/"
        "7810f91fc579070f70436cba9234eeaa/t/i/tial_mvs_wastegates_38mm.jpg",
        "https://www.full-race.com/media/catalog/product/cache/"
        "aefa98ead183f7c08508a7d3ffd5ba53/t/i/tial_full_race_mvs_install.png",
    ),
    brand_logo: str = (
        "https://www.full-race.com/media/catalog/product/cache/"
        "32319b0268a74d30f7b019bbc1087544/t/i/tial_sport_brand.jpg"
    ),
) -> str:
    """
    Minimal page that mirrors the real Magento 2 (Staylime theme) shape:
    og:/product: meta tags, ``catalog-product-view`` body class, the
    ``form[data-product-sku]`` MPN attribute, the ``#details`` description
    block, and gallery images injected inside a ``<script>`` string literal.
    """
    script_block = "".join(
        f'\'<img class="default-picture" data-src="{u}" alt="gallery">\'+' for u in inline_script_images
    )
    return f"""
    <html>
    <head>
      <meta name="description" content="{short_description}"/>
      <meta property="og:type" content="product" />
      <meta property="og:title" content="{title}" />
      <meta property="og:image" content="{hero_image}" />
      <meta property="og:description" content="{short_description}" />
      <meta property="og:url" content="{SAMPLE_URL}" />
      <meta property="product:price:amount" content="{price}"/>
      <meta property="product:price:currency" content="USD"/>
    </head>
    <body id="html-body"
          class="page-product-configurable catalog-product-view product-tial-mvs-38mm-external-wastegate">
      <div class="page-title-wrapper product">
        <h1 class="page-title"><span class="base" data-ui-id="page-title-wrapper">{title}</span></h1>
      </div>
      <div class="hero__sku">SKU  {sku}</div>
      <div class="product__short-description"><p>{short_description}</p></div>
      <form data-product-sku="{sku}" action="/checkout/cart/add" method="post" id="product_addtocart_form"></form>
      <div class="product-info-price">
        <span class="price-wrapper" data-price-amount="{price}">
          <span class="price">${price}</span>
        </span>
      </div>
      <div class="records__window active" id="details">{detail_html}</div>
      <!-- Staylime theme renders the gallery inside a script string literal -->
      <script>
        require(['jquery'], function($) {{
          $('#gallery').html({script_block}'<img class="brand" data-src="{brand_logo}">');
        }});
      </script>
    </body>
    </html>
    """


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_bare_host_routes_to_fullrace(self) -> None:
        assert adapter_name_for_product_url("https://full-race.com/tial-mvs-38mm-external-wastegate") == "fullrace"

    def test_www_subdomain_routes_to_fullrace(self) -> None:
        assert adapter_name_for_product_url("https://www.full-race.com/tial-mvs-38mm-external-wastegate") == "fullrace"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/full-race") == "generic"


class TestIsProductUrl:
    """Sitemap filter: root-level slugs are products, ``/store/...`` is categories,
    and common CMS / account / checkout paths are rejected."""

    def test_root_level_slug_is_product(self) -> None:
        assert _is_product_url("https://www.full-race.com/tial-mvs-38mm-external-wastegate")
        assert _is_product_url("https://www.full-race.com/garrett-gen-2-gtx3071r-evo-x-bolt-on-twin-scroll-turbo")

    def test_store_category_rejected(self) -> None:
        for url in (
            "https://www.full-race.com/store/turbos/borg-warner-efr",
            "https://www.full-race.com/store/exhaust/turbo-manifolds",
            "https://www.full-race.com/store/wastegates",
        ):
            assert not _is_product_url(url), url

    def test_homepage_rejected(self) -> None:
        assert not _is_product_url("https://www.full-race.com/")
        assert not _is_product_url("https://www.full-race.com")

    def test_cms_and_account_paths_rejected(self) -> None:
        for url in (
            "https://www.full-race.com/customer/account/login",
            "https://www.full-race.com/checkout/cart/",
            "https://www.full-race.com/contact",
            "https://www.full-race.com/about-us",
            "https://www.full-race.com/privacy-policy",
            "https://www.full-race.com/blog/how-to-tune",
        ):
            assert not _is_product_url(url), url

    def test_wrong_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/tial-mvs-38mm-external-wastegate")


class TestCanonicalImagePath:
    """Gallery dedupe key: different Magento cache hashes for the same asset
    collapse to one path; non-product assets (brand tiles) return None."""

    def test_different_cache_hashes_for_same_asset_collapse(self) -> None:
        a = _canonical_image_path(
            "https://www.full-race.com/media/catalog/product/cache/"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/t/i/tial_mvs_wastegates_38mm.jpg"
        )
        b = _canonical_image_path(
            "https://www.full-race.com/media/catalog/product/cache/"
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/t/i/tial_mvs_wastegates_38mm.jpg"
        )
        assert a == b
        assert a is not None
        assert a.endswith("tial_mvs_wastegates_38mm.jpg")

    def test_brand_logo_rejected(self) -> None:
        assert (
            _canonical_image_path(
                "https://www.full-race.com/media/catalog/product/cache/"
                "32319b0268a74d30f7b019bbc1087544/t/i/tial_sport_brand.jpg"
            )
            is None
        )

    def test_non_magento_path_rejected(self) -> None:
        assert _canonical_image_path("https://www.full-race.com/media/logo/default/favicon.ico") is None
        assert _canonical_image_path("https://example.com/img.jpg") is None


class TestResolvePartManufacturer:
    """Full-Race is multi-brand; house SKUs canonicalize to ``Full-Race`` and
    reseller brands pass through via the shared title-token heuristic."""

    def test_reseller_brand_from_title(self) -> None:
        assert _resolve_part_manufacturer("TiAL MVS 38mm External Wastegate", None) == "TiAL"
        assert _resolve_part_manufacturer("Garrett G30-770 Turbocharger", None) == "Garrett"
        assert _resolve_part_manufacturer("Precision 6266 CEA Turbo", None) == "Precision"

    def test_house_brand_hyphenated_title(self) -> None:
        assert (
            _resolve_part_manufacturer("Full-Race Billet Vacuum Boost Reference Manifold Block", None)
            == FULLRACE_HOUSE_BRAND
        )

    def test_house_brand_space_separated_title(self) -> None:
        # "Full Race" (no hyphen) in the title should still canonicalize.
        assert _resolve_part_manufacturer("Full Race T3 Stainless V-Band Flange Kit", None) == FULLRACE_HOUSE_BRAND


class TestParseProductPage:
    """End-to-end parsing: real-shape Magento HTML → ScrapedPayload."""

    def test_full_page_parses(self) -> None:
        result = FullRaceAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "TiAL MVS 38mm External Wastegate"
        assert result.part_manufacturer == "TiAL"
        assert result.part_number == "MVS"
        assert result.price_cents == 31997
        assert result.product_url == SAMPLE_URL
        assert result.description is not None
        assert "ultra-compact wastegate" in result.description

    def test_gallery_sweeps_script_string_literals(self) -> None:
        # The Staylime theme builds the image carousel by injecting <img>
        # strings inside a $('#gallery').html(...) call — BeautifulSoup's
        # element walker can't see those. The regex sweep picks them up and
        # dedups against the og:image hero.
        result = FullRaceAdapter().parse_product_page(_product_page_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None

        paths = [_canonical_image_path(u) for u in result.image_urls]
        assert "t/i/tial_mvs_wastegates_38mm.jpg" in paths
        assert "t/i/tial_full_race_mvs_install.png" in paths
        # Brand-logo tile must be filtered — manufacturer badges are not
        # product photography.
        assert not any(p and "brand" in p for p in paths)
        # Same asset at multiple cache hashes must collapse to one entry.
        assert len(paths) == len(set(paths))

    def test_house_brand_product_defaults_manufacturer(self) -> None:
        # A Full-Race house-brand product — no reseller brand in the title —
        # should canonicalize the manufacturer to "Full-Race" rather than
        # returning a token like "Full-Race" that could drift over time.
        html = _product_page_html(
            title="Full-Race Billet Vacuum Boost Reference Manifold Block",
            sku="FR-VBRM-01",
            short_description="Billet aluminum boost reference block with -4 AN ports.",
        )
        result = FullRaceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == FULLRACE_HOUSE_BRAND
        assert result.part_number == "FR-VBRM-01"

    def test_missing_body_class_returns_none(self) -> None:
        # CMS / category pages crawled through the sitemap filter sometimes
        # still have an h1 and a meta description, so the body-class sanity
        # check is the only signal that rejects them cleanly.
        html = """
        <html><head>
          <meta property="og:title" content="About Full-Race">
          <meta property="og:description" content="Full-Race is a leading FI company.">
        </head><body class="cms-page-view">
          <h1>About Full-Race</h1>
        </body></html>
        """
        assert FullRaceAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_missing_title_returns_none(self) -> None:
        html = """
        <html><head></head>
        <body class="catalog-product-view"><div>Out of stock.</div></body></html>
        """
        assert FullRaceAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_sku_preferred_from_form_attribute(self) -> None:
        # The hero label prefix ("SKU  MVS") could trip simpler parsers — the
        # clean source is the add-to-cart form's data-product-sku attribute.
        html = _product_page_html(sku="FR-MAN-EF88-K24")
        result = FullRaceAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "FR-MAN-EF88-K24"
