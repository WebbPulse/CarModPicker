"""
Tests for wheelsboutique.com adapter: URL guard, registration, fetcher tier,
and the catalog-only parsing path (no prices, brand from URL for wheels,
iPE token detection for exhausts).
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.wheelsboutique import (
    WheelsBoutiqueAdapter,
    _is_product_url,
    _wheel_brand_display,
)

WHEEL_URL = "https://wheelsboutique.com/wheels/hre-wheels/520-series/hre-520"
EXHAUST_URL = "https://wheelsboutique.com/exhausts/porsche-718-gts-4-0-718-cayman-gt4-718-spyder-exhaust-system"


def _wheel_html(
    *,
    name: str = "HRE 520",
    description_text: str = "",
    og_description: str = "",
    og_image: str = "https://wheelsboutique.com/wp-content/uploads/2024/07/hre-520-hero.png",
    # Pages render a "More wheels on: <series>" cross-sell row of thumbnails
    # of *other* products. Those must not leak into image_urls.
    cross_sell_img: str = "https://wheelsboutique.com/wp-content/uploads/2024/07/hre-521-150x150.png",
) -> str:
    return f"""
    <html><head>
      <title>{name} | Wheels Boutique</title>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{og_description}">
      <meta property="og:image" content="{og_image}">
      <meta property="og:type" content="product">
    </head><body>
      <main>
        <h1 class="font-exo italic">{name}</h1>
        <div>
          <p class="font-small text-gray-900">Wheel Brand: <b><a href="https://wheelsboutique.com/wheels/hre-wheels/">Buy HRE Wheels</a></b></p>
          <div class="mt-8 border-t border-gray-200 pt-8">
            <h2 class="text-sm font-medium text-gray-900">Product Description</h2>
            <div class="prose prose-sm mt-4 text-gray-500">{description_text}</div>
          </div>
          <button id="openModalBtn">Request a Quote</button>
        </div>
        <div class="mt-8 lg:col-span-8">
          <h2 class="sr-only">Images</h2>
          <img src="{og_image}" alt="{name}">
        </div>
        <div>
          <p>More wheels on: 520 Series</p>
          <a href="https://wheelsboutique.com/wheels/hre-wheels/520-series/hre-521/">
            <img src="{cross_sell_img}" alt="HRE 521">
          </a>
        </div>
      </main>
    </body></html>
    """


def _exhaust_html(
    *,
    name: str = "Porsche 718 GTS 4.0 / 718 Cayman GT4 / 718 Spyder Exhaust System",
    og_description: str = (
        "Actual product may vary due to product enhancement. iPE reserves the right to "
        "revise, change, explain the product. Porsche>718"
    ),
    og_image: str = "https://wheelsboutique.com/wp-content/uploads/2024/10/product-porsche-718-muffler.jpg",
    description_text: str = (
        "Actual product may vary due to product enhancement. iPE reserves the right to revise, "
        "change, explain the product. Porsche>718"
    ),
) -> str:
    return f"""
    <html><head>
      <title>{name} | Wheels Boutique</title>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{og_description}">
      <meta property="og:image" content="{og_image}">
      <meta property="og:type" content="product">
    </head><body>
      <main>
        <h1>{name}</h1>
        <div class="mt-8 border-t border-gray-200 pt-8">
          <h2 class="text-sm font-medium text-gray-900">Product Description</h2>
          <div class="prose prose-sm mt-4 text-gray-500">
            <p>{description_text.split('Porsche>')[0].rstrip()}</p>
            <p>Porsche&gt;718</p>
          </div>
        </div>
        <button id="openModalBtn">Request a Quote</button>
      </main>
    </body></html>
    """


class TestAdapterRegistration:
    """Host mapping routes wheelsboutique.com to this adapter."""

    def test_bare_host_maps_to_wheelsboutique(self) -> None:
        assert adapter_name_for_product_url(WHEEL_URL) == "wheelsboutique"

    def test_www_host_maps_to_wheelsboutique(self) -> None:
        assert adapter_name_for_product_url("https://www.wheelsboutique.com/exhausts/foo") == "wheelsboutique"

    def test_unrelated_host_does_not_map(self) -> None:
        assert adapter_name_for_product_url("https://example.com/wheels/hre-wheels/hre-520") != "wheelsboutique"


class TestProductUrlGuard:
    """
    Product URL shapes:
    - Wheels must have ``/wheels/<brand>/<...>`` so brand-landing pages are rejected.
    - Exhausts are flat: ``/exhausts/<slug>``.
    Featured-vehicle blog posts and other CMS paths must not be treated as products.
    """

    def test_three_segment_wheel_url_valid(self) -> None:
        assert _is_product_url("https://wheelsboutique.com/wheels/hre-wheels/hre-520/")

    def test_four_segment_wheel_url_valid(self) -> None:
        assert _is_product_url(WHEEL_URL)
        assert _is_product_url(WHEEL_URL + "/")

    def test_wheel_brand_landing_rejected(self) -> None:
        # `/wheels/<brand>/` is a category page, not a product.
        assert not _is_product_url("https://wheelsboutique.com/wheels/hre-wheels/")

    def test_wheels_category_root_rejected(self) -> None:
        assert not _is_product_url("https://wheelsboutique.com/wheels/")

    def test_exhaust_url_valid(self) -> None:
        assert _is_product_url(EXHAUST_URL)

    def test_exhaust_category_root_rejected(self) -> None:
        assert not _is_product_url("https://wheelsboutique.com/exhausts/")

    def test_blog_post_rejected(self) -> None:
        assert not _is_product_url("https://wheelsboutique.com/featured-vehicle/ruby-star-turbo-s/")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/wheels/hre-wheels/hre-520/")


class TestWheelBrandDisplay:
    """Curated slug-to-display map + fallback heuristic for unknown brands."""

    def test_known_slugs(self) -> None:
        assert _wheel_brand_display("hre-wheels") == "HRE"
        assert _wheel_brand_display("anrky-wheels") == "ANRKY"
        assert _wheel_brand_display("ipe-wheels") == "iPE"
        assert _wheel_brand_display("ag-luxury-wheels") == "AG Luxury"
        assert _wheel_brand_display("techart-wheels-porsche") == "TechArt"

    def test_unknown_slug_strips_wheels_suffix(self) -> None:
        # Future-proofing: a hypothetical vossen brand slug should not land
        # as "Vossen-Wheels" but as "Vossen" after suffix stripping.
        assert _wheel_brand_display("vossen-wheels") == "Vossen"

    def test_unknown_slug_strips_compound_suffix(self) -> None:
        # Known pattern "techart-wheels-porsche" uses a -<suffix> after -wheels;
        # the heuristic handles the same shape for unknown brands too.
        assert _wheel_brand_display("forgeline-wheels-ford") == "Forgeline"


class TestParseWheelProductPage:
    """Wheel pages: brand from URL, hero-only image, description often empty."""

    def test_full_payload(self) -> None:
        result = WheelsBoutiqueAdapter().parse_product_page(_wheel_html(), WHEEL_URL)
        assert result is not None
        assert result.name == "HRE 520"
        assert result.part_manufacturer == "HRE"
        assert result.part_number is None
        # Catalog-only site: price must be None, not 0.
        assert result.price_cents is None
        assert result.product_url == WHEEL_URL

    def test_price_always_none_even_with_dollar_in_page(self) -> None:
        # Defensive: a stray dollar amount somewhere on the page (e.g. in an
        # unrelated banner) must not be pulled in as a price. The adapter
        # doesn't run a price extractor for WB at all.
        html = _wheel_html(description_text="Starting from $5,000 per wheel set.")
        result = WheelsBoutiqueAdapter().parse_product_page(html, WHEEL_URL)
        assert result is not None
        assert result.price_cents is None

    def test_image_is_hero_only_cross_sell_thumbs_excluded(self) -> None:
        result = WheelsBoutiqueAdapter().parse_product_page(_wheel_html(), WHEEL_URL)
        assert result is not None
        assert result.image_urls is not None
        assert len(result.image_urls) == 1
        joined = " ".join(result.image_urls)
        assert "hre-520-hero" in joined
        # The "More wheels on:" cross-sell thumbnail of a *different* product
        # must not leak into image_urls.
        assert "hre-521-150x150" not in joined

    def test_brand_from_url_on_unknown_slug(self) -> None:
        # A brand slug not in _WHEEL_BRAND_DISPLAY still produces a sensible
        # manufacturer via the heuristic (rather than None or a raw slug).
        unknown_url = "https://wheelsboutique.com/wheels/vossen-wheels/hybrid-forged/hf-3/"
        result = WheelsBoutiqueAdapter().parse_product_page(_wheel_html(name="HF-3"), unknown_url)
        assert result is not None
        assert result.part_manufacturer == "Vossen"

    def test_description_falls_back_to_og_when_prose_empty(self) -> None:
        # Wheel pages routinely ship with an empty `.prose` block. Adapter
        # must fall back to og:description so the catalog row isn't blank.
        html = _wheel_html(description_text="", og_description="Forged 1-piece monoblock wheel.")
        result = WheelsBoutiqueAdapter().parse_product_page(html, WHEEL_URL)
        assert result is not None
        assert result.description == "Forged 1-piece monoblock wheel."


class TestParseExhaustProductPage:
    """Exhaust pages: brand detected from the ``iPE`` token in copy."""

    def test_ipe_token_detected_as_brand(self) -> None:
        result = WheelsBoutiqueAdapter().parse_product_page(_exhaust_html(), EXHAUST_URL)
        assert result is not None
        assert result.part_manufacturer == "iPE"
        assert result.price_cents is None
        assert result.description and "iPE" in result.description

    def test_no_ipe_token_leaves_brand_none(self) -> None:
        # A future non-iPE exhaust without any recognisable brand token on
        # the page should not fabricate a manufacturer.
        html = _exhaust_html(
            og_description="Straight-through stainless-steel exhaust, part of the premium line.",
            description_text="Straight-through stainless-steel exhaust, part of the premium line.",
        )
        result = WheelsBoutiqueAdapter().parse_product_page(html, EXHAUST_URL)
        assert result is not None
        assert result.part_manufacturer is None

    def test_image_is_hero_only(self) -> None:
        result = WheelsBoutiqueAdapter().parse_product_page(_exhaust_html(), EXHAUST_URL)
        assert result is not None
        assert result.image_urls is not None
        assert len(result.image_urls) == 1
        assert "product-porsche-718-muffler" in result.image_urls[0]


class TestParseEdgeCases:
    """Guards for non-product URLs and malformed pages."""

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape guard: CMS paths must not be parsed as products.
        result = WheelsBoutiqueAdapter().parse_product_page(
            _wheel_html(),
            "https://wheelsboutique.com/about/",
        )
        assert result is None

    def test_brand_landing_returns_none(self) -> None:
        result = WheelsBoutiqueAdapter().parse_product_page(
            _wheel_html(),
            "https://wheelsboutique.com/wheels/hre-wheels/",
        )
        assert result is None

    def test_missing_name_returns_none(self) -> None:
        html = "<html><body><p>Page not found</p></body></html>"
        assert WheelsBoutiqueAdapter().parse_product_page(html, WHEEL_URL) is None

    def test_two_char_wheel_model_name_is_kept(self) -> None:
        # BBS model pages (FI, RN, XA, CH) use 2-char model names as the H1.
        # A length floor would silently drop every BBS forged-line product.
        bbs_url = "https://wheelsboutique.com/wheels/bbs-wheels/forged-line-exclusive-series/fi"
        result = WheelsBoutiqueAdapter().parse_product_page(
            _wheel_html(name="FI", description_text="One Piece Forged Aluminum Wheels."),
            bbs_url,
        )
        assert result is not None
        assert result.name == "FI"
        assert result.part_manufacturer == "BBS"


class TestAdapterFetcherTier:
    """Wheels Boutique is plain nginx/WordPress — no Cloudflare, no TLS challenge."""

    def test_declares_http_tier(self) -> None:
        assert WheelsBoutiqueAdapter.FETCHER_TIER == "http"
