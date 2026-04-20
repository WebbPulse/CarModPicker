"""Tests for functionwerk.com adapter: Shopify page with no JSON-LD Product block."""

from app.crawlers.adapters.tier0_http.functionwerk import (
    FUNCTIONWERK_BRAND,
    FunctionwerkAdapter,
    _canonical_image_url,
    _extract_sku,
)

SAMPLE_URL = "https://functionwerk.com/products/2021-acura-tlx-v6-3-0t-type-s-titanium-sport-exhaust"


def _minimal_page(
    *,
    title: str = "Sport Exhaust (Titanium) for 2021-25 Acura TLX V6 (3.0T) Type S",
    og_desc: str = (
        "Description A premium Titanium Sport Exhaust now available for your 2021-2025 Acura "
        "TLX V6 3.0T Type S (S-Tech)! Features a complete Brush finish."
    ),
    dom_desc: str = (
        "Description A premium Titanium Sport Exhaust now available for your 2021-2025 "
        "Acura TLX V6 3.0T Type S (S-Tech)! Features a complete Brush finish with a quad "
        "tip exit, contouring and sitting flush with the rear bumper for an OEM+ execution!"
    ),
    price: str = "4,750.00",
    sku: str = "FW-AE-02-C",
    gallery_img: str = (
        "//functionwerk.com/cdn/shop/files/" "FunctionWerk-SportExhaust_Fullexhaust.jpg?v=1705333114&width=1780"
    ),
    # Banner image that appears outside the MediaGallery container (promo
    # carousel / hero) — must NOT appear in the parsed image_urls.
    banner_img: str = "//functionwerk.com/cdn/shop/files/Brake_Kit.webp?v=1759140708&width=1780",
    # Return-policy `.rte` block lives inside a collapsible tab and must NOT
    # win over the real `.truncate-text` product description.
    returns_policy: str = (
        "Normal purchases have a 14-day return window, effective as of shipping delivery date. "
        "All returns must be returned in the same condition they were shipped in and are subject "
        "to a 30% restocking fee."
    ),
) -> str:
    return f"""
    <html><head>
      <title>{title}</title>
      <meta name="description" content="{og_desc}">
      <meta property="og:title" content="{title}">
      <meta property="og:description" content="{og_desc}">
      <meta property="og:image:secure_url" content="https:{gallery_img.split('?')[0]}?v=1705333114">
      <meta property="og:price:amount" content="{price}">
      <meta property="og:price:currency" content="USD">
      <script>
        var meta = {{"product":{{"id":1,"vendor":"Function Werk","variants":[{{"id":2,"price":475000,"sku":"{sku}"}}]}}}};
      </script>
    </head><body>
      <!-- Promo/hero carousel: image is outside the MediaGallery container. -->
      <section class="hero-banner">
        <img src="{banner_img}" alt="Brake kit promo">
      </section>

      <h1>{title}</h1>

      <!-- Main product media gallery (Shopify theme id prefix). -->
      <div id="MediaGallery__template--abc__main" class="media-gallery__wrapper">
        <img src="{gallery_img}" alt="{title}">
      </div>

      <!-- Real product description wrapper. -->
      <div class="truncate-text">
        <div class="rte">
          <p><strong>Description</strong></p>
          <p>{dom_desc}</p>
        </div>
      </div>

      <!-- Returns policy in a collapsible tab — must not be used as description. -->
      <div class="collapsible-tab__content">
        <div class="rte">
          <p>{returns_policy}</p>
        </div>
      </div>
    </body></html>
    """


class TestExtractSku:
    """SKU is embedded in the ShopifyAnalytics meta JSON blob, not JSON-LD."""

    def test_finds_sku_from_shopify_meta(self) -> None:
        assert _extract_sku(_minimal_page()) == "FW-AE-02-C"

    def test_returns_none_when_missing(self) -> None:
        assert _extract_sku("<html><body>no sku here</body></html>") is None


class TestCanonicalImageUrl:
    """Shopify CDN URLs come in many shapes (protocol-relative, with ?width=N, http)."""

    def test_upgrades_protocol_relative_to_https(self) -> None:
        result = _canonical_image_url("//functionwerk.com/cdn/shop/files/a.jpg?v=123&width=750")
        assert result == "https://functionwerk.com/cdn/shop/files/a.jpg?v=123"

    def test_upgrades_http_to_https(self) -> None:
        result = _canonical_image_url("http://functionwerk.com/cdn/shop/files/a.jpg?v=123")
        assert result == "https://functionwerk.com/cdn/shop/files/a.jpg?v=123"

    def test_strips_responsive_width_param(self) -> None:
        # Dedup across srcset entries: ...width=450 and ...width=1780 should collapse.
        a = _canonical_image_url("//cdn.shopify.com/x/a.jpg?v=1&width=450")
        b = _canonical_image_url("//cdn.shopify.com/x/a.jpg?v=1&width=1780")
        assert a == b

    def test_drops_site_logo(self) -> None:
        assert _canonical_image_url("//functionwerk.com/cdn/shop/files/Function_Werk_Logo_I_Black.png") is None


class TestParseProductPage:
    """End-to-end: HTML → ScrapedPayload."""

    def test_full_payload(self) -> None:
        result = FunctionwerkAdapter().parse_product_page(_minimal_page(), SAMPLE_URL)
        assert result is not None
        assert result.name.startswith("Sport Exhaust (Titanium)")
        assert result.part_manufacturer == FUNCTIONWERK_BRAND
        assert result.part_number == "FW-AE-02-C"
        assert result.price_cents == 475000  # 4,750.00 USD → cents
        assert result.product_url == SAMPLE_URL
        assert result.description is not None
        assert "Titanium Sport Exhaust" in result.description

    def test_description_prefers_product_copy_over_returns_policy(self) -> None:
        # The `.rte` inside `.collapsible-tab__content` (return policy) is longer
        # than the product description, so a naive "pick longest .rte" heuristic
        # would pick the wrong block. We scope to `.truncate-text` first.
        long_policy = "Normal purchases have a 14-day return window. " * 30
        short_desc = "A premium Titanium Sport Exhaust for your Acura TLX."
        html = _minimal_page(dom_desc=short_desc, returns_policy=long_policy)
        result = FunctionwerkAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.description is not None
        assert "14-day return" not in result.description
        assert "Titanium Sport Exhaust" in result.description

    def test_gallery_excludes_hero_banner(self) -> None:
        result = FunctionwerkAdapter().parse_product_page(_minimal_page(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        joined = " ".join(result.image_urls)
        # Hero/banner is outside MediaGallery__ — must not leak in.
        assert "Brake_Kit.webp" not in joined
        # Real product image should be present.
        assert any("FunctionWerk-SportExhaust_Fullexhaust" in u for u in result.image_urls)

    def test_missing_name_returns_none(self) -> None:
        html = "<html><head></head><body><p>Out of stock.</p></body></html>"
        assert FunctionwerkAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_falls_back_to_og_description_when_dom_missing(self) -> None:
        html = """
        <html><head>
          <meta property="og:title" content="Function Werk Test Product">
          <meta property="og:description" content="Long enough OG description for a test case.">
        </head><body><h1>Function Werk Test Product</h1></body></html>
        """
        result = FunctionwerkAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.description == "Long enough OG description for a test case."
        assert result.part_manufacturer == FUNCTIONWERK_BRAND
