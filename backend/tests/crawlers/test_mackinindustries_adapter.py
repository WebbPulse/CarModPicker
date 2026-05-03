"""Tests for mackinindustries.com adapter: URL shape, og-driven parse, brand map, price/SKU only on /product/."""

from app.crawlers.adapters.tier1_tls.mackinindustries import (
    MackinIndustriesAdapter,
    _brand_from_tokens,
    _canonicalize_product_url,
    _image_dedup_key,
    _is_catalog_child_sitemap,
    _is_product_url,
)

ITEM_URL = "https://mackin-ind.com/item/57cr-glossy-gray/"
# WooCommerce /product/ fixture. The slug used to be ``rays-t-shirt-white``
# (matching a real Mackin SKU), but the parser now drops apparel/swag SKUs at
# parse time so the catalog stays clean — that filter would short-circuit
# every WooCommerce assertion below. Switched to a real wheel-accessory slug
# (Rays Volk Racing locking-lugnut set) which exercises the same WooCommerce
# price-on-sale + SKU-in-product_meta DOM shape without tripping the merch
# rejector.
PRODUCT_URL = "https://mackin-ind.com/product/volk-racing-locking-lugnut-set/"


def _item_html(
    *,
    og_title: str = "57CR Glossy Gray - Mackin Industries",
    og_description: str = (
        "Recent gramLIGHTS models incorporate the use of low visibility colors, "
        "now available as a standard finish in a limited fashion."
    ),
    og_image: str = "https://mackin-ind.com/wp-content/uploads/2021/11/57CR-gg-feature.jpg",
    h1: str = "57CR Glossy Gray",
) -> str:
    """Minimal /item/ page: og:* meta + H1 + gallery lightbox anchors, no price/SKU."""
    return f"""
    <html><head>
      <title>{og_title}</title>
      <meta property="og:title" content="{og_title}" />
      <meta property="og:description" content="{og_description}" />
      <meta property="og:image" content="{og_image}" />
    </head><body>
      <!-- Site-chrome logo must NOT leak into product gallery. -->
      <img src="https://mackin-ind.com/wp-content/uploads/2020/07/Mackin-Logo-White-100x64.png" />
      <article id="post-8415" class="post-8415 item type-item status-publish">
        <h1>{h1}</h1>
        <div class="product-detail wide-wrapper">
          <div class="lightbox-container row m-0">
            <a href="https://mackin-ind.com/wp-content/uploads/2021/11/57cr-gg.jpg"
               data-lightbox="Glossy+Gray">
              <img src="https://mackin-ind.com/wp-content/uploads/2021/11/57cr-gg-60x58.jpg"
                   data-srcset="https://mackin-ind.com/wp-content/uploads/2021/11/57cr-gg-100x100.jpg 100w,
                                https://mackin-ind.com/wp-content/uploads/2021/11/57cr-gg-250x243.jpg 250w,
                                https://mackin-ind.com/wp-content/uploads/2021/11/57cr-gg.jpg 477w" />
            </a>
            <a href="https://mackin-ind.com/wp-content/uploads/2021/11/51667424982_e2bece7bf8_c.jpg"
               data-lightbox="Glossy+Gray">
              <img src="https://mackin-ind.com/wp-content/uploads/2021/11/51667424982_e2bece7bf8_c-60x45.jpg" />
            </a>
          </div>
          <p>{og_description}</p>
          <ul>
            <li>Method: Cast 1pc. Wheel</li>
            <li>Color: Glossy Gray (AG)</li>
          </ul>
        </div>
      </article>
    </body></html>
    """


def _product_html(
    *,
    og_title: str = "Volk Racing Locking Lugnut Set - Mackin Industries",
    og_description: str = "Volk Racing 12x1.5 locking lugnut set in Mag Blue.",
    og_image: str = "https://mackin-ind.com/wp-content/uploads/2022/01/41240443882_e52fd0e0a5_c.jpg",
    h1: str = "Volk Racing Locking Lugnut Set",
    sku: str = "WK-VR-LLN-12150-MB",
    sale_current: str = "15.00",
    sale_original: str = "30.00",
) -> str:
    """Minimal /product/ (WooCommerce) page: price as <del>/<ins>, SKU in product_meta."""
    return f"""
    <html><head>
      <title>{og_title}</title>
      <meta property="og:title" content="{og_title}" />
      <meta property="og:description" content="{og_description}" />
      <meta property="og:image" content="{og_image}" />
    </head><body>
      <article id="post-9018" class="post-9018 product type-product">
        <div class="summary entry-summary">
          <h1 class="product_title entry-title">{h1}</h1>
          <p class="price">
            <del aria-hidden="true">
              <span class="woocommerce-Price-amount amount">
                <bdi><span class="woocommerce-Price-currencySymbol">$</span>{sale_original}</bdi>
              </span>
            </del>
            <ins aria-hidden="true">
              <span class="woocommerce-Price-amount amount">
                <bdi><span class="woocommerce-Price-currencySymbol">$</span>{sale_current}</bdi>
              </span>
            </ins>
          </p>
          <div class="woocommerce-product-details__short-description">
            <p>{og_description}</p>
          </div>
          <div class="product_meta">
            <span class="sku_wrapper">SKU: <span class="sku">{sku}</span></span>
            <span class="posted_in">Category: <a href="#">Clearance</a></span>
          </div>
        </div>
      </article>
    </body></html>
    """


class TestProductUrlShape:
    """URL gate: /item/<slug>/ and /product/<slug>/ under the mackin hosts are accepted."""

    def test_item_url_is_product(self) -> None:
        assert _is_product_url(ITEM_URL)

    def test_product_url_is_product(self) -> None:
        assert _is_product_url(PRODUCT_URL)

    def test_accepts_legacy_mackinindustries_alias(self) -> None:
        # The retailer backlog names mackinindustries.com; the live site
        # redirects to mackin-ind.com. URL-shape gate must accept both so
        # extension-captured URLs against the legacy host still route here.
        assert _is_product_url("https://www.mackinindustries.com/item/te37-ultra/")

    def test_category_url_rejected(self) -> None:
        assert not _is_product_url("https://mackin-ind.com/brands/rays/")
        assert not _is_product_url("https://mackin-ind.com/shop/")
        assert not _is_product_url("https://mackin-ind.com/item/")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://www.example.com/item/foo/")


class TestCanonicalize:
    """Canonical host is mackin-ind.com (no www.); legacy alias is folded onto it."""

    def test_strips_www_prefix(self) -> None:
        assert (
            _canonicalize_product_url("https://www.mackin-ind.com/item/57cr-glossy-gray/")
            == "https://mackin-ind.com/item/57cr-glossy-gray/"
        )

    def test_folds_mackinindustries_alias_onto_canonical_host(self) -> None:
        # Legacy landing-page domain is a UTF-16 meta-refresh redirect; any
        # URL that leaks through must land on the canonical host so archive
        # dedupe collapses on one product_url per product.
        assert (
            _canonicalize_product_url("http://www.mackinindustries.com/item/te37-ultra")
            == "https://mackin-ind.com/item/te37-ultra/"
        )

    def test_adds_trailing_slash(self) -> None:
        # WordPress redirects unslashed /item/<slug> → /item/<slug>/; emit the
        # slashed form up front so archive dedupe stays stable.
        assert (
            _canonicalize_product_url("https://mackin-ind.com/item/57cr-glossy-gray")
            == "https://mackin-ind.com/item/57cr-glossy-gray/"
        )

    def test_drops_query_string(self) -> None:
        assert (
            _canonicalize_product_url("https://mackin-ind.com/item/57cr-glossy-gray/?utm_source=x")
            == "https://mackin-ind.com/item/57cr-glossy-gray/"
        )

    def test_rejects_non_mackin_host(self) -> None:
        assert _canonicalize_product_url("https://example.com/item/foo/") is None


class TestBrandTokenMap:
    """Mackin's distribution book is fixed — brand detection is a token map, not free inference."""

    def test_volk_racing_is_rays(self) -> None:
        assert _brand_from_tokens("volk-racing-te37-ultra") == "RAYS"

    def test_gram_lights_57cr_is_rays(self) -> None:
        assert _brand_from_tokens("57cr-glossy-gray") == "RAYS"

    def test_advan_is_yokohama_not_rays(self) -> None:
        # Advan Racing is Yokohama's sport line. Even when "rays" appears
        # later in the slug, the Yokohama Wheel rule runs first by design.
        assert _brand_from_tokens("advan-racing-gt-beyond-rays-partner-sticker") == "Yokohama Wheel"

    def test_project_mu_match(self) -> None:
        assert _brand_from_tokens("project-mu-face-mask") == "Project Mu"

    def test_kics_maps_to_kyo_ei(self) -> None:
        assert _brand_from_tokens("kics-project-racing-lock-nut") == "KYO-EI"

    def test_generic_slug_has_no_brand(self) -> None:
        # wheel-rack, magnetic-drain-bolt, optional-decal-set all miss the
        # map on purpose — the ingest layer keeps part_manufacturer_id NULL
        # rather than inventing a sentinel "Unknown" brand.
        assert _brand_from_tokens("wheel-rack") is None
        assert _brand_from_tokens("magnetic-drain-bolt-2") is None
        assert _brand_from_tokens("optional-decal-set") is None


class TestImageDedupKey:
    """WordPress emits <base>-<W>x<H>.<ext> resize variants; dedup keys must collapse them."""

    def test_full_size_and_thumbnail_share_key(self) -> None:
        assert _image_dedup_key("https://mackin-ind.com/wp-content/uploads/2021/11/57cr-gg.jpg") == _image_dedup_key(
            "https://mackin-ind.com/wp-content/uploads/2021/11/57cr-gg-600x450.jpg"
        )

    def test_query_string_ignored(self) -> None:
        assert _image_dedup_key(
            "https://mackin-ind.com/wp-content/uploads/2021/11/57cr-gg.jpg?v=2"
        ) == _image_dedup_key("https://mackin-ind.com/wp-content/uploads/2021/11/57cr-gg-100x100.jpg")


class TestCatalogChildSitemap:
    """Yoast ships many sibling sitemaps; only item* and product carry products."""

    def test_item_sitemap_kept(self) -> None:
        assert _is_catalog_child_sitemap("https://mackin-ind.com/item-sitemap.xml")
        assert _is_catalog_child_sitemap("https://mackin-ind.com/item-sitemap2.xml")

    def test_product_sitemap_kept(self) -> None:
        assert _is_catalog_child_sitemap("https://mackin-ind.com/product-sitemap.xml")

    def test_auxiliary_sitemaps_dropped(self) -> None:
        # These point at CMS pages, dealer records, brand taxonomy, etc.
        # — not product URLs. Skipping them up front avoids a dozen wasted
        # fetches during discovery.
        for child in (
            "https://mackin-ind.com/page-sitemap.xml",
            "https://mackin-ind.com/post-sitemap.xml",
            "https://mackin-ind.com/category-sitemap.xml",
            "https://mackin-ind.com/pwb-brand-sitemap.xml",
            "https://mackin-ind.com/dealer-sitemap.xml",
            "https://mackin-ind.com/product_cat-sitemap.xml",
            "https://mackin-ind.com/product_shipping_class-sitemap.xml",
        ):
            assert not _is_catalog_child_sitemap(child)


class TestParseItemPage:
    """The /item/ (wheel catalog) path: og:title/desc/image + H1, no price, no SKU."""

    def test_full_page_parses_from_og_meta(self) -> None:
        result = MackinIndustriesAdapter().parse_product_page(_item_html(), ITEM_URL)
        assert result is not None
        # Yoast's " - Mackin Industries" suffix must not survive.
        assert result.name == "57CR Glossy Gray"
        # Brand inference via slug token map.
        assert result.part_manufacturer == "RAYS"
        # /item/ pages are a distributor spec sheet — no price, no SKU.
        assert result.price_cents is None
        assert result.part_number is None
        assert result.description and "gramLIGHTS" in result.description
        assert result.product_url == ITEM_URL

    def test_images_collected_and_deduped(self) -> None:
        result = MackinIndustriesAdapter().parse_product_page(_item_html(), ITEM_URL)
        assert result is not None
        assert result.image_urls is not None
        # og:image (57CR-gg-feature.jpg) + two lightbox-anchor originals.
        # The -60x58 / -100x100 / -250x243 resize variants must dedupe away.
        assert len(result.image_urls) == 3
        # og:image seeds the list.
        assert result.image_urls[0].endswith("57CR-gg-feature.jpg")
        # Lightbox anchors link full-size; all dedup keys are unique.
        assert len({_image_dedup_key(u) for u in result.image_urls}) == len(result.image_urls)

    def test_site_chrome_logo_excluded_from_images(self) -> None:
        # The header Mackin logo lives under wp-content/uploads/2020/07/ —
        # inside the uploads tree but retailer chrome, not product photography.
        result = MackinIndustriesAdapter().parse_product_page(_item_html(), ITEM_URL)
        assert result is not None
        assert result.image_urls is not None
        assert all("Mackin-Logo" not in u for u in result.image_urls)

    def test_non_product_url_returns_none(self) -> None:
        # Guard: archive rescrape must not run category or brand pages
        # through this adapter just because the host matches.
        result = MackinIndustriesAdapter().parse_product_page(
            _item_html(),
            "https://mackin-ind.com/brands/rays/",
        )
        assert result is None

    def test_missing_name_returns_none(self) -> None:
        html = "<html><body><p>Stub.</p></body></html>"
        assert MackinIndustriesAdapter().parse_product_page(html, ITEM_URL) is None

    def test_two_char_wheel_model_name_is_kept(self) -> None:
        # RAYS / Advan wheel-model pages use 2-char model names as the H1
        # (M8, S5, R6). A length floor would silently drop all of them.
        result = MackinIndustriesAdapter().parse_product_page(
            _item_html(og_title="M8 - Mackin Industries", h1="M8"),
            "https://mackin-ind.com/item/m8/",
        )
        assert result is not None
        assert result.name == "M8"

    def test_generic_accessory_has_no_brand(self) -> None:
        # "wheel-rack" slug misses every brand token; ingest will leave
        # part_manufacturer_id NULL. Adapter must not invent a brand.
        # Override og_description too — the default fixture's "Recent
        # gramLIGHTS..." blurb belongs to a wheel-model page; on a real
        # /item/wheel-rack page the body wouldn't lead with an umbrella-brand
        # mention, and the body-text fallback would correctly surface it.
        result = MackinIndustriesAdapter().parse_product_page(
            _item_html(
                og_title="Wheel Rack - Mackin Industries",
                og_description="Steel wheel storage rack for the garage.",
                h1="Wheel Rack",
            ),
            "https://mackin-ind.com/item/wheel-rack/",
        )
        assert result is not None
        assert result.part_manufacturer is None


class TestParseWooCommerceProductPage:
    """The /product/ path (merchandise): WooCommerce price + SKU in addition to og:*."""

    def test_price_picks_sale_ins_not_del(self) -> None:
        # <del> wraps the original; <ins> wraps the current sale price.
        # Reading the first woocommerce-Price-amount would grab the crossed-
        # out original — we must pick the <ins> child instead.
        result = MackinIndustriesAdapter().parse_product_page(_product_html(), PRODUCT_URL)
        assert result is not None
        assert result.price_cents == 1500

    def test_sku_extracted_from_product_meta(self) -> None:
        result = MackinIndustriesAdapter().parse_product_page(_product_html(), PRODUCT_URL)
        assert result is not None
        assert result.part_number == "WK-VR-LLN-12150-MB"

    def test_non_sale_single_price(self) -> None:
        # When a product isn't on sale, WooCommerce renders a single
        # .woocommerce-Price-amount with no <del>/<ins> wrapper. Still picks up.
        html = """
        <html><head>
          <meta property="og:title" content="Non Sale Item - Mackin Industries" />
          <meta property="og:description" content="Straight price." />
        </head><body>
          <article class="type-product">
            <h1 class="product_title">Non Sale Item</h1>
            <p class="price">
              <span class="woocommerce-Price-amount amount">
                <bdi><span class="woocommerce-Price-currencySymbol">$</span>25.00</bdi>
              </span>
            </p>
            <div class="product_meta"><span class="sku">ABC-123</span></div>
          </article>
        </body></html>
        """
        result = MackinIndustriesAdapter().parse_product_page(html, "https://mackin-ind.com/product/non-sale-item/")
        assert result is not None
        assert result.price_cents == 2500
        assert result.part_number == "ABC-123"

    def test_name_strips_mackin_industries_suffix(self) -> None:
        result = MackinIndustriesAdapter().parse_product_page(_product_html(), PRODUCT_URL)
        assert result is not None
        assert not result.name.endswith("Mackin Industries")
        assert result.name == "Volk Racing Locking Lugnut Set"


class TestMerchandiseRejection:
    """Mackin distributes RAYS-branded apparel and swag on the same /item/ URL
    shape as the wheel catalog. The audit (2026-05-02) found 95 such SKUs
    polluting "other" — folding chairs, polos, t-shirts, hats, lanyards,
    license-plate frames. They round-trip the URL gate so we drop them at
    parse time."""

    def test_apparel_rejected_by_slug(self) -> None:
        # Slug carries the type token even when og:title doesn't.
        html = _item_html(og_title="Some Promo Item - Mackin Industries", h1="Some Promo Item")
        url = "https://mackin-ind.com/item/rays-polo-shirt/"
        assert MackinIndustriesAdapter().parse_product_page(html, url) is None

    def test_apparel_rejected_by_title(self) -> None:
        # Slug obscures the type ("windbreaker-bk"), but og:title gives it away.
        html = _item_html(og_title="RAYS Windbreaker Jacket (BK)", h1="RAYS Windbreaker Jacket")
        url = "https://mackin-ind.com/item/windbreaker-bk/"
        assert MackinIndustriesAdapter().parse_product_page(html, url) is None

    def test_real_part_with_sticker_in_name_kept(self) -> None:
        # ``Sticker`` and ``decal`` are NOT in the merch list — the spoke
        # sticker set is a wheel decal you apply to the spokes, not swag.
        html = _item_html(
            og_title="57Xtreme Optional Spoke Sticker Set - Mackin Industries",
            h1="57Xtreme Optional Spoke Sticker Set",
        )
        url = "https://mackin-ind.com/item/57xtreme-optional-spoke-sticker-set/"
        result = MackinIndustriesAdapter().parse_product_page(html, url)
        assert result is not None
        assert "Sticker" in result.name


class TestAdapterFetcherTier:
    """Mackin sits behind WP Engine + Cloudflare WAF; plain requests 403 intermittently."""

    def test_declares_tls_tier(self) -> None:
        assert MackinIndustriesAdapter.FETCHER_TIER == "tls"
