"""
Tests for the Tier-2 audit Item #4 image-URL fixes:

  * per-adapter junk-image deny lists added to apr / bcracing / cobbtuning /
    forgeline / hksusa / studiorsr
  * the cross-adapter ``filter_payload_image_urls`` post-extraction filter
    in ``crawlers/base.py``
  * the data-cleanup migration's ``_clean_url_list`` helper

Each adapter test asserts (a) that the documented junk URL is removed from
the parsed payload's ``image_urls`` and (b) that a co-occurring real product
photo survives. Inline HTML fixtures only — no MinIO / archive fetch.
"""

import importlib.util
import json
from pathlib import Path
from typing import List

# --- studiorsr -------------------------------------------------------------

_STUDIORSR_HTML = """
<html><head>
  <meta property="og:title" content="StudioRSR Carbon Front Splitter" />
  <meta property="og:image" content="https://studiorsr.com/cdn/shop/products/splitter-hero.jpg?v=1" />
  <script type="application/ld+json">
  {
    "@context": "https://schema.org/",
    "@type": "Product",
    "name": "StudioRSR Carbon Front Splitter",
    "sku": "SRSR-SPL-001",
    "brand": {"@type":"Brand","name":"StudioRSR"},
    "image": ["https://studiorsr.com/cdn/shop/products/splitter-hero.jpg?v=1"],
    "offers": {
      "@type":"Offer",
      "price":"599.00",
      "priceCurrency":"USD",
      "availability":"https://schema.org/InStock"
    }
  }
  </script>
</head><body>
  <!-- Lazy-loader leaves src as the spinner; data-src is the real photo. -->
  <img src="https://studiorsr.com/cdn/shop/t/12/assets/loading.svg"
       data-src="https://studiorsr.com/cdn/shop/products/splitter-detail.jpg?v=2" />
  <!-- Theme chrome / brand logo: deny. -->
  <img src="https://studiorsr.com/cdn/shop/t/12/assets/studiorsr_dark.svg" />
  <!-- Off-host: drop. -->
  <img src="https://example.com/banner.jpg" />
  <!-- Bare .svg under products/: still deny .svg. -->
  <img data-src="https://studiorsr.com/cdn/shop/products/badge.svg" />
</body></html>
"""


def test_studiorsr_drops_spinner_and_theme_chrome() -> None:
    from app.crawlers.adapters.tier0_http.studiorsr import StudioRSRAdapter

    result = StudioRSRAdapter().parse_product_page(
        _STUDIORSR_HTML,
        "https://studiorsr.com/products/carbon-front-splitter",
    )
    assert result is not None
    assert result.image_urls is not None
    # The real product photo URL survives.
    assert any("splitter-hero" in u or "splitter-detail" in u for u in result.image_urls)
    # The deny-listed URLs are gone.
    assert all("loading.svg" not in u for u in result.image_urls)
    assert all("studiorsr_dark" not in u for u in result.image_urls)
    assert all("/cdn/shop/t/" not in u for u in result.image_urls)
    assert all("example.com" not in u for u in result.image_urls)
    assert all(not u.lower().endswith(".svg") for u in result.image_urls)
    # Force https.
    assert all(u.startswith("https://") for u in result.image_urls)


# --- cobbtuning ------------------------------------------------------------


def _cobb_html_non_ap3() -> str:
    """Non-AccessPort product page where the page leaks the AP3 beauty shot."""
    return """
    <html><head>
      <meta property="og:title" content="COBB Tuning Stage 1 Power Package" />
      <meta property="og:image" content="https://www.cobbtuning.com/media/catalog/product/s/t/stg1-real.jpg" />
      <script type="application/ld+json">
      {
        "@context":"https://schema.org/",
        "@type":"Product",
        "name":"COBB Tuning Stage 1 Power Package",
        "sku":"7F1100",
        "brand":{"@type":"Brand","name":"COBB Tuning"},
        "image":[
          "https://www.cobbtuning.com/media/catalog/product/s/t/stg1-real.jpg",
          "https://www.cobbtuning.com/media/catalog/product/a/p/accessport_v3_subaru.jpg"
        ],
        "offers":{
          "@type":"Offer",
          "price":"749.00",
          "priceCurrency":"USD",
          "availability":"https://schema.org/InStock"
        }
      }
      </script>
    </head><body>
      <img src="https://www.cobbtuning.com/media/catalog/product/s/t/stg1-real.jpg">
      <img src="https://www.cobbtuning.com/media/catalog/product/a/p/accessport_v3_main.jpg">
    </body></html>
    """


def _cobb_html_ap3() -> str:
    """AccessPort product page where the beauty shot IS the product photo."""
    return """
    <html><head>
      <meta property="og:title" content="COBB Accessport V3 — Subaru WRX/STI" />
      <meta property="og:image" content="https://www.cobbtuning.com/media/catalog/product/a/p/accessport_v3_subaru.jpg" />
      <script type="application/ld+json">
      {
        "@context":"https://schema.org/",
        "@type":"Product",
        "name":"COBB Accessport V3 — Subaru WRX/STI",
        "sku":"AP3-SUB-004",
        "brand":{"@type":"Brand","name":"COBB Tuning"},
        "image":[
          "https://www.cobbtuning.com/media/catalog/product/a/p/accessport_v3_subaru.jpg",
          "https://www.cobbtuning.com/media/catalog/product/a/p/accessport_v3_main.jpg"
        ],
        "offers":{
          "@type":"Offer",
          "price":"775.00",
          "priceCurrency":"USD",
          "availability":"https://schema.org/InStock"
        }
      }
      </script>
    </head><body>
      <img src="https://www.cobbtuning.com/media/catalog/product/a/p/accessport_v3_subaru.jpg">
    </body></html>
    """


def test_cobb_drops_accessport_marketing_images_on_non_ap3_skus() -> None:
    from app.crawlers.adapters.tier1_tls.cobbtuning import CobbTuningAdapter

    result = CobbTuningAdapter().parse_product_page(
        _cobb_html_non_ap3(),
        "https://www.cobbtuning.com/products/stage-1-power-package-subaru",
    )
    assert result is not None
    assert result.image_urls is not None
    # Real product photo survives.
    assert any("stg1-real" in u for u in result.image_urls)
    # Generic AccessPort beauty shots are denied.
    assert all("accessport_v3_subaru" not in u for u in result.image_urls)
    assert all("accessport_v3_main" not in u for u in result.image_urls)


def test_cobb_keeps_accessport_marketing_image_on_ap3_skus() -> None:
    from app.crawlers.adapters.tier1_tls.cobbtuning import CobbTuningAdapter

    result = CobbTuningAdapter().parse_product_page(
        _cobb_html_ap3(),
        "https://www.cobbtuning.com/products/accessport/accessport-for-subaru-wrx-sti-2015-2021",
    )
    assert result is not None
    assert result.image_urls is not None
    # AP3 SKU → keep the AccessPort beauty shot (it IS the product photo).
    assert any("accessport_v3" in u for u in result.image_urls)


# --- forgeline -------------------------------------------------------------


def test_forgeline_drops_marketing_template_renders() -> None:
    from app.crawlers.adapters.tier1_tls.forgeline import ForgelineAdapter

    html = """
    <html><head>
      <meta property="og:title" content="AL304 | Three Piece Forged Wheel" />
      <meta property="og:description" content="The AL304 wheel" />
      <meta property="og:image" content="https://www.forgeline.com/product_images/forgeline/AL304-PrlGry-medium_image-365x365.png" />
    </head><body>
      <h1 class="product_title" title="AL304 Three Piece Forged Wheel">AL304</h1>
      <h1 class="total_price">From $1830.00</h1>
      <img src="https://www.forgeline.com/product_images/forgeline/AL304-PrlGry-medium_image-365x365.png" />
      <img src="https://www.forgeline.com/product_images/forgeline/forgelinevehicletailoredimage-1234.jpg" />
      <img src="https://www.forgeline.com/product_images/forgeline/forgelinecustomfinishingimage-5678.jpg" />
    </body></html>
    """
    result = ForgelineAdapter().parse_product_page(html, "https://www.forgeline.com/al304/p108")
    assert result is not None
    assert result.image_urls is not None
    assert all("forgelinevehicletailoredimage" not in u for u in result.image_urls)
    assert all("forgelinecustomfinishingimage" not in u for u in result.image_urls)
    # Real product photo survives.
    assert any("AL304-PrlGry" in u for u in result.image_urls)


# --- hksusa ----------------------------------------------------------------


def test_hksusa_returns_none_when_og_image_is_brand_logo() -> None:
    from bs4 import BeautifulSoup

    from app.crawlers.adapters.tier0_http.hksusa import _extract_hero_image

    soup = BeautifulSoup(
        '<html><head><meta property="og:image" content="https://hksusa.com/_next/static/hks_logo.png"></head><body></body></html>',
        "html.parser",
    )
    assert _extract_hero_image(soup) is None

    soup2 = BeautifulSoup(
        '<html><head><meta property="og:image" content="https://hksusa.com/static/hksusa_logo.svg"></head><body></body></html>',
        "html.parser",
    )
    assert _extract_hero_image(soup2) is None


def test_hksusa_keeps_real_product_image() -> None:
    from bs4 import BeautifulSoup

    from app.crawlers.adapters.tier0_http.hksusa import _extract_hero_image

    soup = BeautifulSoup(
        '<html><head><meta property="og:image" content="https://cheerful-bouquet-91c8f27a22.media.strapiapp.com/11003_AN_020_6.JPG"></head><body></body></html>',
        "html.parser",
    )
    result = _extract_hero_image(soup)
    assert result is not None
    assert "11003_AN_020_6" in result


# --- apr -------------------------------------------------------------------


def test_apr_drops_generic_ecu_box_image() -> None:
    from app.crawlers.adapters.tier1_tls.apr import APRAdapter

    payload = {
        "name": "APR ECU Upgrade — Stage 1",
        "partnumber": "ECU0001",
        "mfg_partnumber": "",
        "brand": "APR",
        "description": "Stage 1 ECU upgrade.",
        "shortdescription": "Stage 1",
        "upc": "",
        "price": 599.0,
        "pricing": [{"type": "web", "price": 599.0, "startdate": None, "enddate": None}],
        "images": [
            {"type": "default", "filename": "apr-ecu-box.png", "alt": None},
            {"type": "additional", "filename": "real-ecu-photo-abc123.jpg", "alt": None},
        ],
    }
    blob = json.dumps(payload)
    html = (
        f'<html><head><title>APR ECU Stage 1</title></head><body><div class="mainarea">'
        f'<script type="application/json" id="product_data">{blob}</script>'
        f"<h1>APR ECU Upgrade — Stage 1</h1></div></body></html>"
    )
    result = APRAdapter().parse_product_page(
        html,
        "https://www.goapr.com/products/engine/ecu_upgrades/parts/ECU0001",
    )
    assert result is not None
    assert result.image_urls is not None
    assert all("apr-ecu-box.png" not in u for u in result.image_urls)
    assert any("real-ecu-photo" in u for u in result.image_urls)


# --- bcracing --------------------------------------------------------------


def test_bcracing_drops_catalog_hero_placeholders() -> None:
    from app.crawlers.adapters.tier0_http.bcracing import BCRacingAdapter

    html = """
    <html><head>
      <meta property="og:title" content="BC Racing BR Series Coilovers — Honda Civic">
      <meta property="og:description" content="BR series coilovers">
      <meta property="og:image" content="https://shop.bcracing-na.com/cdn/shop/files/BR_Series_Coilover.jpg?v=1">
      <meta property="og:price:amount" content="1095.00">
      <script type="application/ld+json">
      {
        "@context":"https://schema.org/",
        "@type":"Product",
        "name":"BC Racing BR Series Coilovers — Honda Civic",
        "brand":{"@type":"Brand","name":"BC Racing"},
        "sku":"H-13-BR",
        "image":[
          "https://shop.bcracing-na.com/cdn/shop/files/BR_Series_Coilover.jpg?v=1",
          "https://shop.bcracing-na.com/cdn/shop/files/Rear_Height_Adjuster.jpg?v=2"
        ],
        "offers":{"@type":"Offer","price":"1095.00","priceCurrency":"USD","availability":"https://schema.org/InStock"}
      }
      </script>
    </head><body></body></html>
    """
    result = BCRacingAdapter().parse_product_page(
        html,
        "https://shop.bcracing-na.com/products/br-series-coilovers-honda-civic",
    )
    assert result is not None
    # Both hero placeholders are denied → image_urls collapses to None
    # (don't emit an empty array — see filter docstring).
    assert result.image_urls is None or all(
        "BR_Series_Coilover" not in u and "Rear_Height_Adjuster" not in u for u in result.image_urls
    )


# --- cross-cutting filter in crawlers/base.py ------------------------------


def test_filter_payload_image_urls_drops_data_uris_and_blanks() -> None:
    from app.crawlers.base import filter_payload_image_urls

    out = filter_payload_image_urls(
        [
            "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=",
            "  ",
            "https://cdn.example.com/real.jpg",
            "",
        ],
        part_name="Honda Catback Exhaust",
    )
    assert out == ["https://cdn.example.com/real.jpg"]


def test_filter_payload_image_urls_rewrites_http_to_https() -> None:
    from app.crawlers.base import filter_payload_image_urls

    out = filter_payload_image_urls(["http://cdn.example.com/photo.jpg"], part_name="Brake Kit")
    assert out == ["https://cdn.example.com/photo.jpg"]


def test_filter_payload_image_urls_drops_svg_unless_decal_sticker_logo() -> None:
    from app.crawlers.base import filter_payload_image_urls

    # SVG dropped for a generic part name.
    assert filter_payload_image_urls(["https://cdn.example.com/icon.svg"], part_name="Catback Exhaust") is None
    # SVG kept when the part name advertises a decal/sticker/logo.
    out = filter_payload_image_urls(["https://cdn.example.com/team-decal.svg"], part_name="Window Decal Sheet")
    assert out == ["https://cdn.example.com/team-decal.svg"]


def test_filter_payload_image_urls_collapses_empty_to_none() -> None:
    from app.crawlers.base import filter_payload_image_urls

    assert filter_payload_image_urls(None) is None
    assert filter_payload_image_urls([]) is None
    assert filter_payload_image_urls(["data:image/png;base64,xx"]) is None


def test_filter_payload_image_urls_is_idempotent() -> None:
    from app.crawlers.base import filter_payload_image_urls

    raw = [
        "http://cdn.example.com/a.jpg",
        "data:image/svg+xml;base64,xx",
        "https://cdn.example.com/b.jpg",
    ]
    once = filter_payload_image_urls(raw, part_name="Coilover Kit")
    twice = filter_payload_image_urls(once, part_name="Coilover Kit")
    assert (
        once
        == twice
        == [
            "https://cdn.example.com/a.jpg",
            "https://cdn.example.com/b.jpg",
        ]
    )


# --- migration helper ------------------------------------------------------

# Load the migration module directly. Alembic versions aren't a normal
# package and importing by module path keeps this self-contained — we don't
# need to spin up the env / DB to test the helper.

_MIGRATION_PATH = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "ea29b2450841_strip_junk_image_urls.py"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("ea29b2450841_strip_junk_image_urls", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_clean_url_list_strips_known_patterns() -> None:
    mod = _load_migration_module()
    junk_inputs: List[str] = [
        # studiorsr
        "https://studiorsr.com/cdn/shop/t/123/assets/loading.svg",
        "https://studiorsr.com/cdn/shop/products/badge.svg",
        "https://studiorsr.com/cdn/shop/t/123/assets/studiorsr_dark.png",
        # cobbtuning
        "https://www.cobbtuning.com/media/catalog/product/a/p/accessport_v3_subaru.jpg",
        "https://www.cobbtuning.com/media/catalog/product/a/p/accessport_v3_main.jpg",
        # forgeline
        "https://www.forgeline.com/product_images/forgeline/forgelinevehicletailoredimage-1.jpg",
        "https://www.forgeline.com/product_images/forgeline/forgelinecustomfinishingimage-2.jpg",
        # hksusa
        "https://hksusa.com/_next/static/hks_logo.png",
        "https://hksusa.com/_next/static/hksusa_logo.svg",
        # apr
        "https://images.goapr.com/apr-ecu-box.png",
        # bcracing
        "https://shop.bcracing-na.com/cdn/shop/files/BR_Series_Coilover.jpg?v=1",
        "https://shop.bcracing-na.com/cdn/shop/files/Rear_Height_Adjuster.jpg?v=2",
        # cross-cutting
        "data:image/png;base64,xxxx",
        "",
        "   ",
    ]
    assert mod._clean_url_list(junk_inputs) is None


def test_migration_clean_url_list_keeps_real_photos_and_https_rewrite() -> None:
    mod = _load_migration_module()
    raw = [
        "http://cdn.example.com/real-photo.jpg",
        "https://cdn.example.com/another.jpg",
        "https://hksusa.com/_next/static/hks_logo.png",  # junk
    ]
    out = mod._clean_url_list(raw)
    assert out == [
        "https://cdn.example.com/real-photo.jpg",
        "https://cdn.example.com/another.jpg",
    ]


def test_migration_clean_url_list_is_idempotent() -> None:
    mod = _load_migration_module()
    raw = [
        "http://cdn.example.com/a.jpg",
        "https://cdn.example.com/b.jpg",
        "https://images.goapr.com/apr-ecu-box.png",
    ]
    once = mod._clean_url_list(raw)
    twice = mod._clean_url_list(once)
    assert (
        once
        == twice
        == [
            "https://cdn.example.com/a.jpg",
            "https://cdn.example.com/b.jpg",
        ]
    )


def test_migration_clean_url_list_returns_none_for_empty_input() -> None:
    mod = _load_migration_module()
    assert mod._clean_url_list(None) is None
    assert mod._clean_url_list([]) is None


def test_migration_junk_re_matches_documented_patterns() -> None:
    """Smoke check that every documented pattern actually matches its URL."""
    mod = _load_migration_module()
    cases = {
        "/cdn/shop/t/<theme>/assets/": "https://studiorsr.com/cdn/shop/t/abc/assets/x.png",
        "loading.svg": "https://studiorsr.com/cdn/shop/t/abc/assets/loading.svg",
        "studiorsr_dark": "https://studiorsr.com/x/studiorsr_dark.png",
        "accessport_v3_extra": "https://www.cobbtuning.com/x/accessport_v3_extra.jpg",
        "accessport_v3_main": "https://www.cobbtuning.com/x/accessport_v3_main.jpg",
        "accessport_v3_subaru": "https://www.cobbtuning.com/x/accessport_v3_subaru.jpg",
        "accessport_v3_ford": "https://www.cobbtuning.com/x/accessport_v3_ford.jpg",
        "accessport_v3_bmw": "https://www.cobbtuning.com/x/accessport_v3_bmw.jpg",
        "accessport_v3_volkswagen": "https://www.cobbtuning.com/x/accessport_v3_volkswagen.jpg",
        "accessport_v3_mazda": "https://www.cobbtuning.com/x/accessport_v3_mazda.jpg",
        "forgelinevehicletailoredimage": "https://www.forgeline.com/x/forgelinevehicletailoredimage.jpg",
        "forgelinecustomfinishingimage": "https://www.forgeline.com/x/forgelinecustomfinishingimage.jpg",
        "hks_logo": "https://hksusa.com/x/hks_logo.png",
        "hksusa_logo": "https://hksusa.com/x/hksusa_logo.svg",
        "apr-ecu-box.png": "https://images.goapr.com/apr-ecu-box.png",
        "BR_Series_Coilover.jpg": "https://shop.bcracing-na.com/x/BR_Series_Coilover.jpg",
        "Rear_Height_Adjuster.jpg": "https://shop.bcracing-na.com/x/Rear_Height_Adjuster.jpg",
    }
    for label, url in cases.items():
        assert mod._is_junk_url(url), f"expected {label!r} pattern to match: {url}"
