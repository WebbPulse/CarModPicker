"""
Tests for forgeline.com adapter: URL shape gate, host routing, DOM-only
parse paths (wheel "From $X" + accessory flat $X + zero-priced finish),
image filtering against the category-banner pattern, and FETCHER_TIER.

Forgeline is a custom CMS — no JSON-LD ``Product`` block — so every test
exercises the og:* meta + ``h1.product_title`` / ``h1.total_price`` DOM
selectors the adapter relies on. Cloudflare TLS-fingerprint posture (the
reason for ``FETCHER_TIER = "tls"``) is asserted as a class invariant.
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier1_tls.forgeline import (
    ForgelineAdapter,
    _image_dedup_key,
    _is_product_url,
)

WHEEL_URL = "https://www.forgeline.com/al304/p108"
ACCESSORY_URL = "https://www.forgeline.com/3-ear-billet-push-in-cap/p374"
FINISH_URL = "https://www.forgeline.com/anthracite/p282"


def _wheel_html(
    *,
    og_title: str = "AL304 | Three Piece Forged Wheel",
    og_description: str = "The uniquely-styled AL304 represents an exciting evolution in Forgeline wheel design.",
    og_image: str = "https://www.forgeline.com/product_images/forgeline/AL304-PrlGry-medium_image-365x365.png",
    h1_model: str = "AL304",
    price_text: str = "From $1830.00",
) -> str:
    """
    Wheel-template page. Forgeline embeds the per-finish base price as
    ``From $X`` inside ``h1.total_price`` and surrounds it with a "View
    other series" rail of category banners (``-title-`` filenames) that
    must NOT appear in the parsed gallery.
    """
    return f"""
    <html><head>
      <meta property="og:title" content="{og_title}" />
      <meta property="og:description" content="{og_description}" />
      <meta property="og:image" content="{og_image}" />
    </head><body>
      <!-- Category-banner rail: must be filtered out of gallery. -->
      <img src="https://www.forgeline.com/product_images/forgeline/monoblock-title-1869-v2.webp" />
      <img src="https://www.forgeline.com/product_images/forgeline/al-title-1876-v3.webp" />
      <h1 class="product_title tabtile-font">{h1_model}</h1>
      <div class="product-price">
        <h1 class="total_price">
          <span class="prefix-text">From </span>
          <span class="price-value">{price_text.replace("From ", "")}</span>
        </h1>
      </div>
      <!-- Real product gallery: keep these. -->
      <img src="https://www.forgeline.com/product_images/forgeline/AL304PNGCL-large-108--v.webp" />
      <img src="https://www.forgeline.com/product_images/forgeline/AL304-Tinted-Gold-medium_image-365x365.png" />
      <!-- Same shot at a different size: must dedupe to one. -->
      <img src="https://www.forgeline.com/product_images/forgeline/AL304PNGCL.webp" />
    </body></html>
    """


def _accessory_html() -> str:
    """
    Accessory page. The ``h1.product_title`` runs the model name straight
    into ``Part # XXX`` with no separator — the inline regex must extract
    the SKU even when it's glued to the heading text. Price markup uses
    the ``total_price total_price1`` flat form (no "From " prefix).
    """
    return """
    <html><head>
      <meta property="og:title" content="3-Ear Billet Push In Cap" />
      <meta property="og:description" content="Forged accessory for centerlock-style wheels." />
      <meta property="og:image" content="https://www.forgeline.com/product_images/forgeline/3ear-medium-3443-v1.jpg" />
    </head><body>
      <h1 class="product_title tabtile-font">3-EAR BILLET PUSH IN CAPPart # CAP3EAR-POL-ENG-OPTION</h1>
      <div class="product-price">
        <h1 class="total_price total_price1">$200.00</h1>
      </div>
      <img src="https://www.forgeline.com/product_images/forgeline/3ear-large-3443-v1.jpg" />
    </body></html>
    """


def _finish_html() -> str:
    """
    Finish-color configurator page. These render at $0.00 because the
    finish cost is bundled into the wheel's price. The adapter must
    surface that as ``price_cents=0`` (truthful), not None — ingest can
    decide whether to record $0 entries.
    """
    return """
    <html><head>
      <meta property="og:title" content="Anthracite" />
      <meta property="og:description" content="Anthracite finish option." />
      <meta property="og:image" content="https://www.forgeline.com/product_images/forgeline/FO120DeepTGMCloseup-medium-282--v.jpg" />
    </head><body>
      <h1 class="product_title tabtile-font">Anthracite</h1>
      <div class="product-price">
        <h1 class="total_price total_price1">$0.00</h1>
      </div>
    </body></html>
    """


class TestProductUrlShape:
    """URL gate: ``/<slug>/p<id>`` is product-shaped; ``/<slug>/c<id>`` is a category."""

    def test_wheel_url_is_product(self) -> None:
        assert _is_product_url(WHEEL_URL)

    def test_accessory_url_is_product(self) -> None:
        assert _is_product_url(ACCESSORY_URL)

    def test_trailing_slash_accepted(self) -> None:
        # Sitemap emits both forms across entries; the gate must accept
        # both so archive dedupe doesn't fragment.
        assert _is_product_url("https://www.forgeline.com/al304/p108/")

    def test_bare_host_accepted(self) -> None:
        # forgeline.com (without www.) serves identical content. The
        # extension capture path may submit either; both must route here.
        assert _is_product_url("https://forgeline.com/al304/p108")

    def test_category_url_rejected(self) -> None:
        # /c<id> is a category landing page — must not enter parse pipeline.
        assert not _is_product_url("https://www.forgeline.com/al-series/c1876")

    def test_blog_url_rejected(self) -> None:
        assert not _is_product_url("https://www.forgeline.com/blog/some-post")

    def test_other_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/al304/p108")


class TestHostRouting:
    """``adapter_name_for_product_url`` must route both forgeline hosts to ``forgeline``."""

    def test_www_host_routes(self) -> None:
        assert adapter_name_for_product_url(WHEEL_URL) == "forgeline"

    def test_bare_host_routes(self) -> None:
        assert adapter_name_for_product_url("https://forgeline.com/al304/p108") == "forgeline"


class TestParseWheelPage:
    """The wheel-template path: og:title name, ``From $X`` price, model code as part_number."""

    def test_full_wheel_parse(self) -> None:
        result = ForgelineAdapter().parse_product_page(_wheel_html(), WHEEL_URL)
        assert result is not None
        # og:title preserves the full "MODEL | Description" form.
        assert result.name == "AL304 | Three Piece Forged Wheel"
        # Manufacturer is hard-coded — Forgeline is a direct site.
        assert result.part_manufacturer == "Forgeline"
        # h1.product_title ("AL304") matches the model-code regex and
        # becomes the part_number when no inline "Part #" token is present.
        assert result.part_number == "AL304"
        # "From $1830.00" → 183000 cents. parse_price_cents strips the prefix.
        assert result.price_cents == 183000
        assert result.description and "AL304" in result.description
        assert result.product_url == WHEEL_URL

    def test_category_banner_images_filtered(self) -> None:
        # ``-title-`` filename infix is the category-banner pattern. Real
        # product photos use ``-large-...`` / ``-medium_image-WxH`` / no
        # suffix and must survive the filter.
        result = ForgelineAdapter().parse_product_page(_wheel_html(), WHEEL_URL)
        assert result is not None
        assert result.image_urls is not None
        assert all("-title-" not in u for u in result.image_urls)

    def test_image_size_variants_dedupe(self) -> None:
        # AL304PNGCL.webp and AL304PNGCL-large-108--v.webp are the same
        # source photo at different sizes — dedup key must collapse them.
        result = ForgelineAdapter().parse_product_page(_wheel_html(), WHEEL_URL)
        assert result is not None
        assert result.image_urls is not None
        assert len({_image_dedup_key(u) for u in result.image_urls}) == len(result.image_urls)

    def test_og_image_seeds_gallery(self) -> None:
        result = ForgelineAdapter().parse_product_page(_wheel_html(), WHEEL_URL)
        assert result is not None
        assert result.image_urls is not None
        assert result.image_urls[0].endswith("AL304-PrlGry-medium_image-365x365.png")


class TestParseAccessoryPage:
    """Accessory path: explicit ``Part # XXX`` token wins over h1 model-code fallback."""

    def test_inline_part_number_extracted(self) -> None:
        # The H1 is "3-EAR BILLET PUSH IN CAPPart # CAP3EAR-POL-ENG-OPTION"
        # with no separator. The Part # regex must still extract it.
        result = ForgelineAdapter().parse_product_page(_accessory_html(), ACCESSORY_URL)
        assert result is not None
        assert result.part_number == "CAP3EAR-POL-ENG-OPTION"

    def test_flat_price_parsed(self) -> None:
        # Accessories use ``$X`` (no "From " prefix). Same h1.total_price
        # selector, no JSON-LD price hint to lean on.
        result = ForgelineAdapter().parse_product_page(_accessory_html(), ACCESSORY_URL)
        assert result is not None
        assert result.price_cents == 20000


class TestParseFinishPage:
    """Configurator finish pages: $0.00 is a real, intentional value — surface it, don't drop it."""

    def test_zero_price_surfaced_not_swallowed(self) -> None:
        # Anthracite is a finish option that costs $0 standalone (the cost
        # is bundled into the wheel). Returning None here would drop a
        # real catalog entry; ingest decides whether $0 enters price_history.
        result = ForgelineAdapter().parse_product_page(_finish_html(), FINISH_URL)
        assert result is not None
        assert result.price_cents == 0
        assert result.name == "Anthracite"


class TestParseGuards:
    """Defensive checks — bad input shouldn't crash or pollute the catalog."""

    def test_non_product_url_returns_none(self) -> None:
        # Archive rescrape must not run a category page through this adapter
        # just because the host matches.
        result = ForgelineAdapter().parse_product_page(_wheel_html(), "https://www.forgeline.com/al-series/c1876")
        assert result is None

    def test_missing_name_returns_none(self) -> None:
        html = "<html><body><p>Stub.</p></body></html>"
        assert ForgelineAdapter().parse_product_page(html, WHEEL_URL) is None


class TestAdapterFetcherTier:
    """Cloudflare 403s plain HTTP at the TLS handshake; ``tls`` tier is required."""

    def test_declares_tls_tier(self) -> None:
        assert ForgelineAdapter.FETCHER_TIER == "tls"
