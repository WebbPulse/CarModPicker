"""
Tests for steeda.com adapter: host routing, BigCommerce sitemap filter,
JSON-LD / BCData parsing, SKU-vs-MPN preference, Steeda house-brand
collapse, and image dedup across BC Stencil size variants.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.core.car_inference import generations_for_make_model_year_range
from app.crawlers.base import ScrapedPayload
from app.crawlers.adapters.tier0_http.steeda import (
    SteedaAdapter,
    _extract_steeda_model,
    _extract_year_range,
    _image_dedup_key,
    _is_products_child_sitemap,
    _mpn_from_json_ld,
    _normalize_part_manufacturer,
)

SAMPLE_URL = "https://www.steeda.com/mishimoto-mmts-mus-86a-mustang-thermostat"

# Canonical image path shape: /images/stencil/<size>/products/<product_id>/<batch>/<file>
_IMG_CDN = "https://cdn11.bigcommerce.com/s-67g50tl419/images/stencil"
_IMG_HERO_ORIGINAL = f"{_IMG_CDN}/original/products/5810/14620/mmts-mus-86__77844.1683201088.png?c=1"
_IMG_HERO_1280W = f"{_IMG_CDN}/1280w/products/5810/14620/mmts-mus-86__77844.1683201088.png?c=1"
_IMG_HERO_1280X1280 = f"{_IMG_CDN}/1280x1280/products/5810/14620/mmts-mus-86__77844.1683201088.png?c=1"
_IMG_HERO_500X659 = f"{_IMG_CDN}/500x659/products/5810/14620/mmts-mus-86__77844.1683201088.png?c=1"
_IMG_ALT_1280X1280 = f"{_IMG_CDN}/1280x1280/products/5810/14621/mmts-mus-86_alt__77844.1683201088.png?c=1"


def _product_html(
    *,
    name: str = "Mishimoto Mustang GT/Cobra 82C Street Thermostat (1985-1995)",
    brand: str = "Mishimoto",
    sku: str = "075 MMTS-MUS-86A",
    mpn: str = "MMTS-MUS-86A",
    gtin: str = "748354803396",
    price: float = 68.95,
    description: str = (
        "The Mishimoto street thermostat for the 1986-1995 Ford Mustang will promote greater cooling efficiency. "
        "It opens at a lower temperature than OEM thermostats, allowing coolant to flow through the engine quicker."
    ),
    include_jsonld: bool = True,
    include_bcdata: bool = True,
    extra_gallery_images: tuple[str, ...] = (),
) -> str:
    """Minimal page that mirrors Steeda's BC Stencil + Rich Snippets shape."""
    brand_block = (
        f'"brand":{{"@type":"Brand","@id":"https://www.steeda.com/mishimoto#Brand","name":"{brand}"}},' if brand else ""
    )
    jsonld = (
        f"""
    <script type="application/ld+json" id="wsa-rich-snippets-jsonld-product">
    {{
      "@context": "https://schema.org",
      "@type": "Product",
      "@id": "{SAMPLE_URL}#Product",
      "url": "{SAMPLE_URL}",
      "name": "{name}",
      "description": "{description}",
      "image": ["{_IMG_HERO_ORIGINAL}", "{_IMG_HERO_1280W}", "{_IMG_HERO_1280X1280}", "{_IMG_HERO_500X659}"],
      "sku": "{sku}",
      "mpn": "{mpn}",
      "gtin": "{gtin}",
      {brand_block}
      "offers": {{
        "@type": "Offer",
        "url": "{SAMPLE_URL}",
        "price": {price},
        "priceCurrency": "USD",
        "availability": "InStock"
      }}
    }}
    </script>
    """
        if include_jsonld
        else ""
    )
    bcdata = (
        f"""
    <script>
      var BCData = {{
        "product_attributes": {{
          "sku": "{sku}",
          "mpn": "{mpn}",
          "gtin": "{gtin}",
          "upc": "{gtin}",
          "weight": null,
          "price": {{
            "without_tax": {{"formatted": "${price}", "value": {price}, "currency": "USD"}}
          }}
        }}
      }};
    </script>
    """
        if include_bcdata
        else ""
    )
    gallery_figures = (
        f'<figure class="productView-image" data-zoom-image="{_IMG_HERO_1280X1280}">'
        f'<img data-src="{_IMG_HERO_500X659}">'
        "</figure>"
    )
    for extra in extra_gallery_images:
        gallery_figures += f'<figure class="productView-image"><img data-src="{extra}"></figure>'
    return f"""
    <html><head>
      <meta property="og:title" content="{name}">
      <meta property="og:description" content="{description}">
      <meta property="og:image" content="{_IMG_HERO_ORIGINAL}">
      <meta property="product:price:amount" content="{price}">
      <meta property="product:price:currency" content="USD">
      {jsonld}
      {bcdata}
    </head><body>
      <h1 class="productView-title">{name}</h1>
      <section class="productView-images">
        {gallery_figures}
      </section>
      <article class="productView-description">
        <h2>Product Description</h2>
        <p>{description}</p>
      </article>
    </body></html>
    """


class TestAdapterRegistration:
    """Host-to-adapter map routes every steeda.com page through this adapter."""

    def test_www_host_routes_to_steeda(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "steeda"

    def test_bare_host_routes_to_steeda(self) -> None:
        assert adapter_name_for_product_url("https://steeda.com/some-product") == "steeda"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/steeda/foo") == "generic"


class TestSitemapDiscovery:
    """Steeda's ``xmlsitemap.php`` sitemap index exposes ``type=`` children for
    pages, products, categories, and brands. Only the ``products`` type should
    enter the crawler queue."""

    def test_products_child_sitemap_matches(self) -> None:
        assert _is_products_child_sitemap("https://www.steeda.com/xmlsitemap.php?type=products&page=1")
        assert _is_products_child_sitemap("https://www.steeda.com/xmlsitemap.php?type=products&page=2")

    def test_non_products_children_skipped(self) -> None:
        for url in (
            "https://www.steeda.com/xmlsitemap.php?type=pages&page=1",
            "https://www.steeda.com/xmlsitemap.php?type=categories&page=1",
            "https://www.steeda.com/xmlsitemap.php?type=brands&page=1",
        ):
            assert not _is_products_child_sitemap(url), url

    def test_unrelated_sitemap_path_skipped(self) -> None:
        # Not the Steeda sitemap entrypoint — guards against accidentally
        # accepting some other BC Stencil URL that happens to carry type=products.
        assert not _is_products_child_sitemap("https://www.steeda.com/some/path.xml?type=products")


class TestMpnFromJsonLd:
    """SKU on Steeda is ``<BC-variant-id> <MPN>``; MPN is the clean code."""

    def test_mpn_preferred_over_sku(self) -> None:
        assert _mpn_from_json_ld({"sku": "075 MMTS-MUS-86A", "mpn": "MMTS-MUS-86A"}) == "MMTS-MUS-86A"

    def test_sku_prefix_stripped_when_mpn_missing(self) -> None:
        # Defensive: if MPN is ever absent, strip the numeric BC-id prefix off
        # the SKU so cross-retailer dedup on the clean part still works.
        assert _mpn_from_json_ld({"sku": "161 M-7553-E302"}) == "M-7553-E302"

    def test_returns_none_when_both_missing(self) -> None:
        assert _mpn_from_json_ld({}) is None

    def test_steeda_house_brand_sku_falls_back_to_mpn(self) -> None:
        # Steeda-branded SKU: dash vs. space divergence. MPN ("555-4044") wins.
        assert _mpn_from_json_ld({"sku": "555 4044", "mpn": "555-4044"}) == "555-4044"


class TestNormalizePartManufacturer:
    """Steeda self-variants collapse to one canonical spelling; third-party
    brands pass through verbatim."""

    def test_self_variants_collapse(self) -> None:
        for variant in ("Steeda", "steeda", "STEEDA", "Steeda Autosports", "Steeda Autosports LLC"):
            assert _normalize_part_manufacturer(variant) == "Steeda Autosports", variant

    def test_third_party_brand_passes_through(self) -> None:
        for brand in ("Mishimoto", "Ford Performance", "MBRP", "K&N", "Alpharex"):
            assert _normalize_part_manufacturer(brand) == brand, brand

    def test_empty_returns_none(self) -> None:
        assert _normalize_part_manufacturer("") is None
        assert _normalize_part_manufacturer(None) is None
        assert _normalize_part_manufacturer("   ") is None


class TestImageDedupKey:
    """Size variants of the same BC Stencil photo must share a dedup key."""

    def test_size_variants_collapse(self) -> None:
        key = _image_dedup_key(_IMG_HERO_ORIGINAL)
        assert _image_dedup_key(_IMG_HERO_1280W) == key
        assert _image_dedup_key(_IMG_HERO_1280X1280) == key
        assert _image_dedup_key(_IMG_HERO_500X659) == key

    def test_distinct_photos_keep_distinct_keys(self) -> None:
        assert _image_dedup_key(_IMG_HERO_ORIGINAL) != _image_dedup_key(_IMG_ALT_1280X1280)

    def test_trailing_dimensions_in_alt_url_shape_stripped(self) -> None:
        # BigCommerce also serves the same photo under /products/<id>/images/...
        # with trailing `.W.H.jpg` dimensions — these should collapse with the
        # matching /stencil/ URL of the same file.
        dims = "https://cdn11.bigcommerce.com/s-67g50tl419/products/5810/images/14620/mmts-mus-86__77844.1683201088.386.513.jpg?c=1"
        # same last two segments after stripping `.W.H`
        assert _image_dedup_key(dims) == "14620/mmts-mus-86__77844.1683201088.jpg"


class TestParseProductPage:
    """End-to-end adapter parsing: real-shape Steeda HTML → ScrapedPayload."""

    def test_full_page_parses_from_json_ld(self) -> None:
        result = SteedaAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Mishimoto Mustang")
        assert result.part_manufacturer == "Mishimoto"
        # MPN, not SKU — verifies we ignore the BC variant-id prefix.
        assert result.part_number == "MMTS-MUS-86A"
        assert result.price_cents == 6895
        assert result.gtin == "748354803396"
        assert result.product_url == SAMPLE_URL

    def test_steeda_house_brand_sku_uses_mpn(self) -> None:
        # Steeda-branded part: BC SKU "555 4044" (space), MPN "555-4044" (dash).
        # MPN is the identifier that matches other retailers.
        html = _product_html(
            name="Steeda S197 Mustang Rear Shock Bushings (05-14)",
            brand="Steeda Autosports",
            sku="555 4044",
            mpn="555-4044",
            gtin="",
        )
        result = SteedaAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_number == "555-4044"
        assert result.part_manufacturer == "Steeda Autosports"

    def test_steeda_variant_collapses_to_canonical(self) -> None:
        # Bare "Steeda" brand still maps to the canonical "Steeda Autosports"
        # so the global part-manufacturer table doesn't split one house brand
        # into two rows.
        html = _product_html(brand="Steeda")
        result = SteedaAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.part_manufacturer == "Steeda Autosports"

    def test_third_party_brand_passes_through(self) -> None:
        # Steeda is a multi-brand reseller — each brand keeps its identity.
        for brand in ("Ford Performance", "MBRP", "K&N", "Alpharex", "Russell"):
            html = _product_html(brand=brand)
            result = SteedaAdapter().parse_product_page(html, SAMPLE_URL)
            assert result is not None, brand
            assert result.part_manufacturer == brand, brand

    def test_image_size_variants_collapsed_to_single_entry(self) -> None:
        # JSON-LD emits four size variants of one hero photo; the DOM mirrors
        # the same URLs. All of them should collapse to a single entry.
        result = SteedaAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        # All URLs in the result should have unique photo identities.
        keys = {_image_dedup_key(u) for u in result.image_urls}
        assert len(keys) == len(result.image_urls)
        # Exactly one unique photo for this product.
        assert len(keys) == 1

    def test_multi_image_gallery_captures_alt_photos(self) -> None:
        # A second product image only in the DOM gallery (not in JSON-LD's
        # image[]) must still make it through.
        html = _product_html(extra_gallery_images=(_IMG_ALT_1280X1280,))
        result = SteedaAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        keys = {_image_dedup_key(u) for u in result.image_urls}
        assert len(keys) == 2

    def test_site_chrome_images_filtered_out(self) -> None:
        # Logos / BBB / PCI badges live under /cdn11... paths but aren't
        # product images — they must not leak into image_urls.
        chrome = (
            "https://cdn11.bigcommerce.com/s-67g50tl419/images/stencil/250x64/steeda-small-logo3__80334.original.png",
            "https://cdn11.bigcommerce.com/s-67g50tl419/stencil/theme/img/bbb.png",
            "https://cdn11.bigcommerce.com/s-67g50tl419/stencil/theme/img/PCI_DSS_Validated_blue2.png",
        )
        html = _product_html(extra_gallery_images=chrome)
        result = SteedaAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        for url in result.image_urls:
            assert "logo" not in url.lower()
            assert "bbb.png" not in url.lower()
            assert "pci_dss" not in url.lower()

    def test_missing_jsonld_falls_back_to_bcdata_dom(self) -> None:
        # Defensive: if the Rich Snippets app is ever removed, the BCData blob
        # and Stencil DOM are still enough to parse a product page.
        html = _product_html(include_jsonld=False)
        result = SteedaAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Mishimoto Mustang")
        assert result.part_number == "MMTS-MUS-86A"
        assert result.price_cents == 6895
        assert result.gtin == "748354803396"

    def test_non_product_page_returns_none(self) -> None:
        # Category / brand landing pages share the root URL namespace on BC
        # Stencil. Without a JSON-LD Product block and without a BCData
        # product_attributes section, the adapter must return None.
        html = """
        <html><head><title>Mustang Parts | Steeda</title></head>
        <body><h1>Mustang</h1><div>Browse Mustang parts by year.</div></body></html>
        """
        assert SteedaAdapter().parse_product_page(html, "https://www.steeda.com/mustang") is None

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert SteedaAdapter().parse_product_page(html, SAMPLE_URL) is None


class TestAdapterFetcherTier:
    """Steeda starts on plain HTTP; promote to ``tls`` if CF fires."""

    def test_declares_http_tier(self) -> None:
        assert SteedaAdapter.FETCHER_TIER == "http"


class TestExtractYearRange:
    def test_canonical_yyyy_yyyy(self) -> None:
        assert _extract_year_range("Steeda Mustang GT (2015-2023)") == (2015, 2023)

    def test_open_ended_yyyy_plus(self) -> None:
        assert _extract_year_range("Some Bronco Part (2021+)") == (2021, 9999)

    def test_single_year(self) -> None:
        assert _extract_year_range("Bilstein F-150 Front Shock (1997)") == (1997, 1997)

    def test_unicode_dash(self) -> None:
        assert _extract_year_range("Steeda IRS Brackets (1999–2004)") == (1999, 2004)

    def test_two_digit_tail_carries_century(self) -> None:
        assert _extract_year_range("Cams (2005-10)") == (2005, 2010)

    def test_no_year_tag_returns_none(self) -> None:
        assert _extract_year_range("Steeda Mustang Suspension Kit") is None

    def test_implausible_range_rejected(self) -> None:
        assert _extract_year_range("(1850-1900)") is None
        assert _extract_year_range("(2050-2099)") is None


class TestExtractSteedaModel:
    def test_mustang(self) -> None:
        assert _extract_steeda_model("Steeda Mustang GT Subframe") == ("Ford", "Mustang")

    def test_shelby_gt350_maps_to_mustang(self) -> None:
        assert _extract_steeda_model("Steeda Shelby GT350 H-Pipe") == ("Ford", "Mustang")

    def test_cobra_maps_to_mustang(self) -> None:
        assert _extract_steeda_model("Steeda Cobra Mustang IRS Subframe Brackets") == ("Ford", "Mustang")

    def test_f150(self) -> None:
        assert _extract_steeda_model("Bilstein F-150 2WD Shock") == ("Ford", "F-150")

    def test_raptor_maps_to_f150(self) -> None:
        assert _extract_steeda_model("AWE Raptor Performance Exhaust") == ("Ford", "F-150")

    def test_super_duty_maps_to_super_duty(self) -> None:
        assert _extract_steeda_model("AlphaRex Super Duty Headlights") == ("Ford", "F-Series Super Duty")

    def test_f250_maps_to_super_duty(self) -> None:
        assert _extract_steeda_model("KYB F-250 Front Shock") == ("Ford", "F-Series Super Duty")

    def test_bronco(self) -> None:
        assert _extract_steeda_model("Whipple Bronco 2.7L EcoBoost Stage 1 Kit") == ("Ford", "Bronco")

    def test_explorer(self) -> None:
        assert _extract_steeda_model("MRT Explorer Extreme Axle-Back") == ("Ford", "Explorer")

    def test_no_match_returns_none(self) -> None:
        assert _extract_steeda_model("Mishimoto Aluminum Catch Can") is None


class TestIntersectGenerations:
    """Steeda's hook delegates to the shared
    ``generations_for_make_model_year_range`` helper; these tests anchor
    the contract for the inputs Steeda actually emits."""

    def test_mustang_2015_2023_returns_6th_gen(self) -> None:
        assert generations_for_make_model_year_range("Ford", "Mustang", (2015, 2023)) == [
            ("Ford", "Mustang", "6th Gen"),
        ]

    def test_mustang_2011_2014_returns_5th_gen(self) -> None:
        assert generations_for_make_model_year_range("Ford", "Mustang", (2011, 2014)) == [
            ("Ford", "Mustang", "5th Gen"),
        ]

    def test_mustang_overlap_two_generations(self) -> None:
        # 2003-2007 spans tail of 4th Gen (1994-2004) and head of 5th Gen.
        assert generations_for_make_model_year_range("Ford", "Mustang", (2003, 2007)) == [
            ("Ford", "Mustang", "4th Gen"),
            ("Ford", "Mustang", "5th Gen"),
        ]

    def test_f150_2021_open_ended(self) -> None:
        # (2021, 9999) overlaps 14th Gen (2021-2024). 15th Gen exists in
        # the live DB but is not present in the declarative
        # ``car_generations_data`` snapshot today, so it is correctly absent.
        assert generations_for_make_model_year_range("Ford", "F-150", (2021, 9999)) == [
            ("Ford", "F-150", "14th Gen"),
        ]

    def test_explorer_returns_empty_when_no_overlap(self) -> None:
        # Static data has no Explorer generation overlapping 2020-2026,
        # so the helper returns []; the hook then returns None and ingest
        # falls back to the universal pipeline.
        assert generations_for_make_model_year_range("Ford", "Explorer", (2020, 2026)) == []


class TestInferCarForPart:
    """End-to-end: model + year-range in title → resolved triples."""

    def _payload(self, name: str) -> ScrapedPayload:
        return ScrapedPayload(name=name, product_url=f"https://www.steeda.com/{name[:20]}")

    def test_mustang_year_range_resolves(self) -> None:
        adapter = SteedaAdapter()
        triples = adapter.infer_car_for_part(
            self._payload("Steeda Mustang GT Ultimate Induction Pack (2011-2014)")
        )
        assert triples == [("Ford", "Mustang", "5th Gen")]

    def test_f150_year_range_resolves(self) -> None:
        adapter = SteedaAdapter()
        triples = adapter.infer_car_for_part(
            self._payload("Bilstein F-150 4WD B8 5100 Rear Shock (2015-2019)")
        )
        assert triples == [("Ford", "F-150", "13th Gen")]

    def test_f250_routes_to_super_duty(self) -> None:
        adapter = SteedaAdapter()
        triples = adapter.infer_car_for_part(
            self._payload("KYB F-250 Excel-G Front Shock (2008-2021)")
        )
        # 2008-2021 spans 2nd, 3rd, and 4th gen Super Duty.
        assert triples == [
            ("Ford", "F-Series Super Duty", "2nd Gen"),
            ("Ford", "F-Series Super Duty", "3rd Gen"),
            ("Ford", "F-Series Super Duty", "4th Gen"),
        ]

    def test_bronco_open_ended_range(self) -> None:
        adapter = SteedaAdapter()
        triples = adapter.infer_car_for_part(
            self._payload("Ford Performance Bronco Modular Bumper Red Tow Hooks (2021+)")
        )
        assert triples == [("Ford", "Bronco", "6th Gen")]

    def test_no_year_tag_returns_none(self) -> None:
        adapter = SteedaAdapter()
        assert adapter.infer_car_for_part(self._payload("Steeda Mustang Decal")) is None

    def test_no_known_model_returns_none(self) -> None:
        # Generic third-party item without a model token — the hook must
        # punt to the universal pipeline rather than guess.
        adapter = SteedaAdapter()
        assert adapter.infer_car_for_part(self._payload("Mishimoto Catch Can (2018-2023)")) is None

    def test_explorer_with_no_db_rows_returns_none(self) -> None:
        # Title matches Explorer but the model has no generation entries
        # in our table; the hook returns None so ingest tries the universal
        # pipeline rather than emitting an unresolvable triple.
        adapter = SteedaAdapter()
        assert (
            adapter.infer_car_for_part(self._payload("MRT Explorer Extreme Axle-Back (2020-2026)"))
            is None
        )

    def test_empty_name_returns_none(self) -> None:
        adapter = SteedaAdapter()
        assert adapter.infer_car_for_part(ScrapedPayload(name="", product_url="https://x")) is None
