"""
Tests for lingenfelter.com adapter: host routing, URL shape filter, microdata
parsing, brand resolution (title heuristic wins over the always-LPE
``itemprop=brand`` on third-party SKUs), Miva ``image_data`` gallery
extraction, and flat-sitemap discovery. Fixtures are synthetic HTML modeled
on real product pages so tests don't need network access.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http import lingenfelter as lpe_mod
from app.crawlers.adapters.tier0_http.lingenfelter import (
    LPE_BRAND,
    LingenfelterAdapter,
    _discover_via_sitemap,
    _extract_image_gallery,
    _is_product_url,
    _normalize_brand,
    _resolve_brand,
)

SAMPLE_URL = "https://www.lingenfelter.com/product/BOR-140838.html"
SAMPLE_LPE_URL = "https://www.lingenfelter.com/product/L010086509.html"


def _image_data_script(*entries: tuple[str, str]) -> str:
    """
    Build a ``var image_data<N> = [ {type_code, image_data:[...]} ]`` block
    with one entry per (type_code, full_filename) pair. Each entry's
    ``image_data`` is ``[thumb_540, thumb_100, full]`` — the adapter must
    always take the last URL. Miva serializes forward slashes as ``\\/``;
    Python json.loads accepts either form, so we emit plain ``/``.
    """
    items = []
    for type_code, filename in entries:
        base = filename.rsplit(".", 1)[0]
        ext = filename.rsplit(".", 1)[1] if "." in filename else "jpg"
        items.append(
            '{"type_code": "%s", "image_data": ["graphics/00000001/4/%s_540x304.%s", '
            '"graphics/00000001/4/%s_100x56.%s", "graphics/00000001/4/%s"]}'
            % (type_code, base, ext, base, ext, filename)
        )
    return "<script>var image_data5954 = [" + ",".join(items) + "];</script>"


def _product_html(
    *,
    name: str = "BORLA S-Type 2020-2025 Chevrolet C8 Corvette Stingray Cat-Back Exhaust System - Chrome Tips",
    mpn: str = "BOR-140838",
    sku: str = "BOR-140838",
    brand: str = "Lingenfelter Performance Engineering",
    description: str = (
        "BORLA S-Type 2020-2025 Chevrolet Corvette Stingray Cat-Back Exhaust System. "
        "Features Polyphonic Harmonizer and SwitchFire technology."
    ),
    image_meta: str = "https://www.lingenfelter.com/mm5/",
    price: str = "5444.99",
    data_base_price: str = "5444.99",
    gallery: tuple[tuple[str, str], ...] = (
        ("", "140838-main-2-large.png"),
        ("", "140838-vehicle-1-large.png"),
        ("main", "140838-main-1-large.png"),
        ("", "140838-tip-1-large.png"),
    ),
) -> str:
    """
    Minimal page mirroring Lingenfelter's Miva Merchant microdata shape:
    a Product scope with meta itemprops for name/mpn/sku/description/brand,
    a nested Offer scope for priceCurrency/price/availability, a DOM
    ``#js-price-value[data-base-price]`` backup, and the ``image_data<N>``
    JS gallery. The ``<base href="https://www.lingenfelter.com/mm5/">``
    matches what the real storefront emits — relative ``graphics/...`` URLs
    in the gallery resolve against this base.
    """
    gallery_script = _image_data_script(*gallery) if gallery else ""
    return f"""
    <!doctype html>
    <html lang="en"><head>
      <base href="https://www.lingenfelter.com/mm5/" />
      <title>{name}</title>
    </head><body>
      <div itemscope itemtype="http://schema.org/Product">
        <meta itemprop="mpn" content="{mpn}" />
        <meta itemprop="sku" content="{sku}" />
        <meta itemprop="name" content="{name}" />
        <meta itemprop="image" content="{image_meta}" />
        <meta itemprop="category" content="New Products" />
        <meta itemprop="description" content="{description}" />
        <meta itemprop="brand" content="{brand}" />
        <div itemprop="offers" itemscope itemtype="http://schema.org/Offer">
          <meta itemprop="url" content="{SAMPLE_URL}" />
          <meta itemprop="sku" content="{sku}" />
          <meta itemprop="priceCurrency" content="USD" />
          <meta itemprop="price" content="{price}" />
          <meta itemprop="availability" content="InStock" />
          <h1 class="nm"><span class="normal">{name}</span></h1>
          <div id="js-price-value" class="h3 charcoal nm" data-base-price="{data_base_price}">$5,444.99</div>
        </div>
      </div>
      {gallery_script}
    </body></html>
    """


class TestAdapterRegistration:
    """Host routing sends lingenfelter.com pages through this adapter."""

    def test_www_host_routes_to_lingenfelter(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "lingenfelter"

    def test_bare_host_routes_to_lingenfelter(self) -> None:
        assert adapter_name_for_product_url("https://lingenfelter.com/product/BOR-140838.html") == "lingenfelter"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/lingenfelter") == "generic"


class TestFetcherTier:
    """No Cloudflare interstitial on Lingenfelter — plain requests suffices."""

    def test_http_tier_default(self) -> None:
        assert LingenfelterAdapter.FETCHER_TIER == "http"


class TestProductUrlShape:
    """
    Accept both canonical ``/product/<code>.html`` and SEO ``/product/<slug>``
    forms; reject categories, the Miva-native ``Screen=CTGY`` URL, and the
    VIN lookup feature page.
    """

    def test_html_suffixed_product_url_valid(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_pretty_slug_product_url_valid(self) -> None:
        # Storefront nav serves SEO URLs without ``.html`` — chrome-extension
        # scrapes arrive in this form.
        assert _is_product_url(
            "https://www.lingenfelter.com/product/eliminator-spec-s-7l-427-lt2-naturally-aspirated-c8-corvette-engine"
        )

    def test_category_path_rejected(self) -> None:
        assert not _is_product_url("https://www.lingenfelter.com/category/C4_Corvette_1985-1996.html")

    def test_miva_native_category_url_rejected(self) -> None:
        assert not _is_product_url("https://www.lingenfelter.com/mm5/merchant.mvc?Screen=CTGY&Category_Code=Engines")

    def test_vin_lookup_feature_page_rejected(self) -> None:
        # Not a catalog product — the nav/footer helper page.
        assert not _is_product_url("https://www.lingenfelter.com/product/VIN_LookUp.html")

    def test_root_rejected(self) -> None:
        assert not _is_product_url("https://www.lingenfelter.com/")

    def test_empty_slug_rejected(self) -> None:
        assert not _is_product_url("https://www.lingenfelter.com/product/")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/product/BOR-140838.html")


class TestNormalizeBrand:
    """Any ``Lingenfelter …`` variant collapses to the canonical full name."""

    def test_bare_lingenfelter_normalized(self) -> None:
        # ``part_manufacturer_from_title`` returns bare ``"Lingenfelter"``
        # on first-party LPE titles; normalize to the canonical DB name.
        assert _normalize_brand("Lingenfelter") == LPE_BRAND

    def test_canonical_passthrough(self) -> None:
        assert _normalize_brand(LPE_BRAND) == LPE_BRAND

    def test_lingenfelter_suffix_variant_normalized(self) -> None:
        assert _normalize_brand("Lingenfelter Performance") == LPE_BRAND

    def test_case_insensitive(self) -> None:
        assert _normalize_brand("lingenfelter performance engineering") == LPE_BRAND

    def test_third_party_passthrough(self) -> None:
        assert _normalize_brand("BORLA") == "BORLA"
        assert _normalize_brand("Magnuson") == "Magnuson"
        assert _normalize_brand("Borla Performance") == "Borla Performance"

    def test_empty_returns_none(self) -> None:
        assert _normalize_brand(None) is None
        assert _normalize_brand("") is None
        assert _normalize_brand("   ") is None


class TestResolveBrand:
    """
    Title heuristic wins over the always-LPE microdata brand; chassis-first
    titles fall back to LPE so first-party engine packages don't leak
    ``"CTS-V"`` as a manufacturer.
    """

    def test_title_brand_preferred_over_itemprop(self) -> None:
        # Third-party resold brand — microdata says LPE (useless co-brand),
        # but title starts with "BORLA" which is the real manufacturer.
        assert _resolve_brand("BORLA S-Type Cat-Back Exhaust", LPE_BRAND) == "BORLA"

    def test_magnuson_supercharger_title(self) -> None:
        assert _resolve_brand("Magnuson TVS2650 C8 E-Ray Corvette Supercharger", LPE_BRAND) == "Magnuson"

    def test_first_party_lingenfelter_title_canonical(self) -> None:
        # Title starts with "Lingenfelter"; heuristic returns bare token;
        # _normalize_brand expands to canonical full name.
        result = _resolve_brand(
            "Lingenfelter Eliminator Spec S 7.0L 427 LT2 Naturally Aspirated C8 Corvette Engine",
            LPE_BRAND,
        )
        assert result == LPE_BRAND

    def test_chassis_first_title_falls_back_to_lpe(self) -> None:
        # "CTS-V LSA Supercharged Engine Package 700+ HP 2009-15" — title
        # heuristic rejects chassis-like first tokens, so we fall back to
        # the LPE itemprop brand rather than leaking "CTS-V" as a
        # manufacturer. All first-party LPE built-engine packages look like
        # this.
        result = _resolve_brand(
            "CTS-V LSA Supercharged Engine Package 700+ HP 2009-15",
            LPE_BRAND,
        )
        assert result == LPE_BRAND


class TestImageGallery:
    """
    Miva ``image_data<N>`` JS array — ``type_code="main"`` entry wins hero
    slot; others follow in declaration order; the last URL in each
    ``image_data`` is the full-size.
    """

    def test_main_type_code_promoted_to_hero(self) -> None:
        html = _product_html()
        urls = _extract_image_gallery(html)
        assert len(urls) == 4
        # ``main`` entry is third in the fixture but must come first.
        assert urls[0].endswith("140838-main-1-large.png")
        # Others retain declaration order.
        assert urls[1].endswith("140838-main-2-large.png")
        assert urls[2].endswith("140838-vehicle-1-large.png")
        assert urls[3].endswith("140838-tip-1-large.png")

    def test_relative_paths_resolve_against_mm5_base(self) -> None:
        # ``graphics/...`` is the raw path; the store base is
        # ``https://www.lingenfelter.com/mm5/`` so the absolute URL must
        # include ``/mm5/``. The <base> tag in the real page is irrelevant
        # here — we use a hard-coded IMAGE_BASE constant.
        urls = _extract_image_gallery(_product_html())
        for u in urls:
            assert u.startswith("https://www.lingenfelter.com/mm5/graphics/")

    def test_takes_full_size_last_url_not_thumbnails(self) -> None:
        urls = _extract_image_gallery(_product_html())
        # No ``_540x304`` or ``_100x56`` suffixes in the output (those are
        # thumb sizes that appear at image_data[0] and [1]).
        for u in urls:
            assert "_540x304" not in u
            assert "_100x56" not in u

    def test_dedup_by_path_ignores_query_variants(self) -> None:
        # Same file at two query strings collapses to one entry.
        html = (
            "<script>var image_data1 = ["
            '{"type_code":"main","image_data":["a","b","https://x/img.jpg?v=1"]},'
            '{"type_code":"","image_data":["a","b","https://x/img.jpg?v=2"]}'
            "];</script>"
        )
        urls = _extract_image_gallery(html)
        assert urls == ["https://x/img.jpg?v=1"]

    def test_missing_gallery_returns_empty(self) -> None:
        assert _extract_image_gallery("<html><body>no gallery here</body></html>") == []

    def test_malformed_json_returns_empty(self) -> None:
        # Marker present but the array never closes.
        assert _extract_image_gallery('<script>var image_data1 = [ {"type_code"') == []

    def test_entries_without_image_data_skipped(self) -> None:
        # Defensive: real pages sometimes carry video entries or malformed
        # rows; skip anything that doesn't have a non-empty image_data list.
        html = (
            "<script>var image_data1 = ["
            '{"type_code":"main","image_data":[]},'
            '{"type_code":"","image_data":["t","m","https://x/real.jpg"]},'
            '{"type_code":""}'
            "];</script>"
        )
        assert _extract_image_gallery(html) == ["https://x/real.jpg"]


class TestParseProductPage:
    """End-to-end parse: synthetic microdata + JS gallery → ScrapedPayload."""

    def test_third_party_brand_extracted_from_title(self) -> None:
        # BORLA exhaust resold by LPE: microdata brand is LPE (co-brand noise),
        # but the real manufacturer is in the title.
        result = LingenfelterAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "BORLA"
        assert result.part_number == "BOR-140838"
        assert result.price_cents == 544499  # $5,444.99
        assert result.name.startswith("BORLA S-Type")
        assert result.description is not None
        assert "Polyphonic Harmonizer" in result.description
        assert result.image_urls is not None
        assert len(result.image_urls) == 4
        assert result.image_urls[0].endswith("140838-main-1-large.png")
        assert result.product_url == SAMPLE_URL

    def test_first_party_lpe_built_engine(self) -> None:
        # L-prefix SKU, title starts with "Lingenfelter", dollars-only price
        # (``"13999"`` → $13,999.00 — no decimal point in the microdata).
        html = _product_html(
            name="Lingenfelter 427 LT1 Supercharged 700HP C7 Corvette Engine Package",
            mpn="L011370024",
            sku="L011370024",
            price="13999",
            data_base_price="13999",
            gallery=(("main", "L011370024-1.jpg"),),
        )
        result = LingenfelterAdapter().parse_product_page(html, SAMPLE_LPE_URL)
        assert result is not None
        assert result.part_manufacturer == LPE_BRAND
        assert result.part_number == "L011370024"
        assert result.price_cents == 1399900

    def test_chassis_first_title_resolves_to_lpe(self) -> None:
        # CTS-V LSA engine package — no brand token in title; microdata
        # brand defaults us to LPE rather than leaking "CTS-V".
        html = _product_html(
            name="CTS-V LSA Supercharged Engine Package 700+ HP 2009-15",
            mpn="L010086509",
            sku="L010086509",
            price="13999",
            data_base_price="13999",
        )
        result = LingenfelterAdapter().parse_product_page(html, SAMPLE_LPE_URL)
        assert result is not None
        assert result.part_manufacturer == LPE_BRAND
        assert result.part_number == "L010086509"

    def test_prefers_mpn_over_sku(self) -> None:
        # Rare on LPE (mpn/sku are usually identical) but defensively picks
        # the clean MPN when a retailer-prefixed SKU diverges.
        html = _product_html(mpn="140838", sku="BOR-140838")
        result = LingenfelterAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "140838"

    def test_non_product_url_returns_none(self) -> None:
        # Category URL matching the host must not be parsed as a product.
        result = LingenfelterAdapter().parse_product_page(
            _product_html(), "https://www.lingenfelter.com/category/C4_Corvette_1985-1996.html"
        )
        assert result is None

    def test_missing_microdata_returns_none(self) -> None:
        # Typical Miva 404 landing: nav chrome with no Product scope.
        html = "<html><head><base href='https://www.lingenfelter.com/mm5/'/></head><body>404 Not Found</body></html>"
        assert LingenfelterAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_gallery_missing_falls_back_to_itemprop_image(self) -> None:
        # When ``image_data<N>`` JS is absent, use the ``itemprop=image`` meta
        # value — unless it's the ``/mm5/`` stub that Miva sometimes emits
        # on newer SKUs.
        html = _product_html(
            image_meta="https://www.lingenfelter.com/mm5/graphics/00000001/09_CTS_V_6_900.jpg",
            gallery=(),
        )
        result = LingenfelterAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls == ["https://www.lingenfelter.com/mm5/graphics/00000001/09_CTS_V_6_900.jpg"]

    def test_gallery_missing_stub_itemprop_image_dropped(self) -> None:
        # The ``/mm5/`` stub is not a real image — must not be stored.
        html = _product_html(image_meta="https://www.lingenfelter.com/mm5/", gallery=())
        result = LingenfelterAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls is None

    def test_price_falls_back_to_data_base_price(self) -> None:
        # itemprop=price empty — use the DOM ``#js-price-value[data-base-price]``.
        html = _product_html(price="", data_base_price="32495")
        result = LingenfelterAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.price_cents == 3249500  # $32,495.00


class TestDiscoverViaSitemap:
    """
    Flat urlset: keep ``/product/*.html`` entries, drop Miva-native
    ``Screen=PROD`` duplicates (which appear for the same product) and
    ``/category/`` URLs.
    """

    SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://www.lingenfelter.com/product/BOR-140838.html</loc>
        <lastmod>2020-06-22</lastmod>
      </url>
      <url>
        <loc>https://www.lingenfelter.com/product/L010086509.html</loc>
        <lastmod>2020-06-22</lastmod>
      </url>
      <url>
        <loc>https://www.lingenfelter.com/mm5/merchant.mvc?Screen=PROD&amp;Product_Code=BOR-140838</loc>
        <lastmod>2020-06-22</lastmod>
      </url>
      <url>
        <loc>https://www.lingenfelter.com/category/C4_Corvette_1985-1996.html</loc>
        <lastmod>2020-06-22</lastmod>
      </url>
      <url>
        <loc>https://www.lingenfelter.com/product/VIN_LookUp.html</loc>
        <lastmod>2020-06-22</lastmod>
      </url>
    </urlset>
    """

    def test_filters_to_product_html_only(self, monkeypatch) -> None:
        monkeypatch.setattr(lpe_mod, "fetch_page", lambda url, timeout=30: self.SITEMAP_XML)
        urls = _discover_via_sitemap()
        assert urls == [
            "https://www.lingenfelter.com/product/BOR-140838.html",
            "https://www.lingenfelter.com/product/L010086509.html",
        ]

    def test_returns_empty_on_fetch_failure(self, monkeypatch) -> None:
        def _raise(url, timeout=30):
            raise RuntimeError("sitemap unavailable")

        monkeypatch.setattr(lpe_mod, "fetch_page", _raise)
        assert _discover_via_sitemap() == []

    def test_returns_empty_on_malformed_xml(self, monkeypatch) -> None:
        monkeypatch.setattr(lpe_mod, "fetch_page", lambda url, timeout=30: "not xml at all")
        assert _discover_via_sitemap() == []


class TestDiscoverProductUrls:
    """Env override wins; sitemap next; falls back to DEFAULT_START_URLS."""

    def test_env_override_filters_to_product_urls(self, monkeypatch) -> None:
        monkeypatch.setenv(
            "CRAWLER_LINGENFELTER_START_URLS",
            (
                "https://www.lingenfelter.com/product/BOR-140838.html,"
                "https://www.lingenfelter.com/category/C4_Corvette_1985-1996.html,"
                "https://example.com/not-lpe.html"
            ),
        )
        urls = list(LingenfelterAdapter().discover_product_urls())
        assert urls == ["https://www.lingenfelter.com/product/BOR-140838.html"]

    def test_falls_back_to_default_when_sitemap_empty(self, monkeypatch) -> None:
        monkeypatch.delenv("CRAWLER_LINGENFELTER_START_URLS", raising=False)
        monkeypatch.setattr(lpe_mod, "_discover_via_sitemap", lambda: [])
        urls = list(LingenfelterAdapter().discover_product_urls())
        assert urls == list(lpe_mod.DEFAULT_START_URLS)
