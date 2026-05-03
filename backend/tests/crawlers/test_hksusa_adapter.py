"""
Tests for hksusa.com adapter: URL guard, registration, and the RSC
streaming-payload parsing path (no JSON-LD, no useful og:* beyond title/image,
so fields come from code-anchored regexes on the escaped-JSON blob Next.js
emits inside ``self.__next_f.push(...)``).
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.hksusa import (
    HKSUSAAdapter,
    _is_product_url,
    _product_code_from_url,
    _unescape_rsc_string,
)

SAMPLE_CODE = "11003-AN020"
SAMPLE_URL = f"https://hksusa.com/product/{SAMPLE_CODE}"


def _product_html(
    *,
    code: str = SAMPLE_CODE,
    name: str = "SPECIAL FULL TURBINE KIT GT5565_BB R35",
    remarks: str = (
        "BOX#1 LWH: 700 X 280 X 290 (19.2kg), " "Racing use only / Primary catalyst installation not possible."
    ),
    msrp: int = 20800,
    og_image: str = "https://cheerful-bouquet-91c8f27a22.media.strapiapp.com/11003_AN_020_6_cf28dc1b3a.JPG",
    include_sibling_product: bool = True,
) -> str:
    r"""
    Shape a minimal HKS USA product page. The real site is Next.js 13 App
    Router, and all CMS data rides inside ``self.__next_f.push([1,"..."])``
    payloads where each inner double-quote is escaped as ``\"``. We only need
    to reproduce that escape shape for the regexes to fire.

    When ``include_sibling_product`` is True, embed a second product record
    (the ``featured_cars_products`` / related-products slot) with a different
    code and different ``name`` so the code-anchoring in the regexes is
    actually exercised — not just a degenerate "only one name in the blob"
    happy path.
    """
    # Escape inner double-quotes to match the RSC-in-JS-string shape.
    # Python raw string would double-count the backslashes, so build the
    # escaped literal by replacing " with \" in the non-escaped shape.
    current_record = (
        '\\"id\\":6486,\\"attributes\\":{'
        f'\\"name\\":\\"{name}\\",\\"code\\":\\"{code}\\",'
        f'\\"remarks\\":\\"{remarks}\\",\\"discontinued\\":false'
        "}"
    )
    sibling = ""
    if include_sibling_product:
        sibling = (
            '\\"id\\":7000,\\"attributes\\":{'
            '\\"name\\":\\"UNRELATED SIBLING KIT\\",\\"code\\":\\"99999-ZZ999\\",'
            '\\"remarks\\":\\"do not pick this up\\",\\"discontinued\\":false'
            "},"
        )
    product_unit = (
        '{\\"__component\\":\\"product-unit.product-unit-us\\",'
        f'\\"msrp\\":{msrp},\\"length\\":700,\\"height\\":290,'
        '\\"n_of_box\\":3,\\"last_msrp\\":null,\\"total_wt\\":57.6,'
        '\\"width\\":280}'
    )
    rsc_payload = f'{sibling}{current_record},\\"product_unit\\":[{product_unit}]'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charSet="utf-8"/>
  <title>{name} | HKS High Performance Auto Parts</title>
  <link rel="canonical" href="{SAMPLE_URL}"/>
  <meta property="og:title" content="{name} | HKS High Performance Auto Parts"/>
  <meta property="og:site_name" content="HKS High Performance Auto Parts"/>
  <meta property="og:image" content="{og_image}"/>
</head>
<body>
  <div id="__next"></div>
  <script>self.__next_f.push([1,"c:[{rsc_payload}]"])</script>
</body>
</html>
"""


class TestAdapterRegistration:
    """Host-based routing so the extension scrape endpoint lands on this adapter."""

    def test_bare_host_routes_to_hksusa(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "hksusa"

    def test_www_host_routes_to_hksusa(self) -> None:
        assert adapter_name_for_product_url(f"https://www.hksusa.com/product/{SAMPLE_CODE}") == "hksusa"

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/product/11003-AN020") == "generic"


class TestIsProductUrl:
    """Guard used by sitemap discovery so category / CMS links aren't yielded as products."""

    def test_product_path_accepted(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_product_path_with_trailing_letter_accepted(self) -> None:
        # Real sample: codes occasionally carry a trailing letter (condition / variant).
        assert _is_product_url("https://hksusa.com/product/80300-AA005C")

    def test_category_path_rejected(self) -> None:
        assert not _is_product_url("https://hksusa.com/category/38")

    def test_productlist_path_rejected(self) -> None:
        # `productlist` is a category landing, not a product page — the regex
        # must anchor on `/product/<code>` (singular) exactly.
        assert not _is_product_url("https://hksusa.com/productlist/38")

    def test_bare_product_root_rejected(self) -> None:
        assert not _is_product_url("https://hksusa.com/product")

    def test_offsite_rejected(self) -> None:
        assert not _is_product_url("https://example.com/product/11003-AN020")


class TestProductCodeFromUrl:
    """The URL's code segment is the canonical part number; no DOM cross-check exists."""

    def test_extracts_code(self) -> None:
        assert _product_code_from_url(SAMPLE_URL) == SAMPLE_CODE

    def test_non_product_url_returns_none(self) -> None:
        assert _product_code_from_url("https://hksusa.com/category/38") is None


class TestUnescapeRscString:
    """JSON-inside-JS-string escape decoding for RSC payload values."""

    def test_quote_unescape(self) -> None:
        assert _unescape_rsc_string(r"a \"quoted\" word") == 'a "quoted" word'

    def test_newline_collapses_to_space(self) -> None:
        # Remarks occasionally wraps to \n; normalize to space so we don't ship
        # literal backslash-n into the catalog description.
        assert _unescape_rsc_string(r"line1\nline2") == "line1 line2"

    def test_escaped_backslash(self) -> None:
        assert _unescape_rsc_string(r"path\\sep") == r"path\sep"

    def test_unicode_escape_decoded(self) -> None:
        # Strapi serializes ``&`` as ``&`` when emitting prose into the
        # RSC stream. The decoder has to turn that back into ``&`` so the
        # description doesn't ship as ``A & B`` to end users.
        assert _unescape_rsc_string(r"Racing Suction & Cold Air Intake Box") == (
            "Racing Suction & Cold Air Intake Box"
        )

    def test_unicode_escape_curly_apostrophe(self) -> None:
        # The other common production case: ``'`` → ``’``.
        assert _unescape_rsc_string(r"world’s best") == "world’s best"


class TestParseProductPage:
    """End-to-end parsing against a shaped RSC-streaming product page."""

    def test_full_page_parses(self) -> None:
        result = HKSUSAAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "SPECIAL FULL TURBINE KIT GT5565_BB R35"
        assert result.part_manufacturer == "HKS"
        assert result.part_number == SAMPLE_CODE
        # msrp 20800 → $20,800 → 2,080,000 cents. Whole-dollar → cents is the
        # HKS-specific conversion, and this asserts we didn't accidentally
        # double-convert or treat it as cents already.
        assert result.price_cents == 2_080_000
        assert result.description is not None
        assert "BOX#1" in result.description
        assert "Racing use only" in result.description
        assert result.image_urls is not None
        assert result.image_urls[0].startswith("https://cheerful-bouquet-")
        assert result.product_url == SAMPLE_URL

    def test_sibling_product_record_does_not_leak(self) -> None:
        # The RSC blob carries a second (unrelated) product record; the
        # code-anchored regexes must ignore its name + remarks so we don't
        # ingest "UNRELATED SIBLING KIT" as the current product.
        result = HKSUSAAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert "SIBLING" not in result.name
        assert result.description is None or "do not pick this up" not in result.description

    def test_missing_rsc_name_falls_back_to_og_title(self) -> None:
        # Hypothetical: CMS field-layout change drops the (name, code) pairing.
        # og:title fallback should recover the display name minus the site
        # suffix so discovery still produces a usable row.
        html = _product_html(include_sibling_product=False)
        html = html.replace(
            f'\\"name\\":\\"SPECIAL FULL TURBINE KIT GT5565_BB R35\\",\\"code\\":\\"{SAMPLE_CODE}\\"', ""
        )
        result = HKSUSAAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.name == "SPECIAL FULL TURBINE KIT GT5565_BB R35"

    def test_missing_msrp_returns_none_price(self) -> None:
        html = _product_html().replace('\\"msrp\\":20800,', '\\"msrp\\":0,')
        result = HKSUSAAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.price_cents is None

    def test_msrp_in_whole_dollars_not_cents(self) -> None:
        # A cheap part ($1000 MSRP) proves the whole-dollars → cents
        # conversion. If we'd accidentally treated msrp as cents this would
        # show up as $10 and this assertion catches it.
        html = _product_html(msrp=1000)
        result = HKSUSAAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.price_cents == 100_000

    def test_non_product_url_returns_none(self) -> None:
        # Category pages render through the same app shell; guard against the
        # runner feeding us a category URL it scraped out of the sitemap.
        assert HKSUSAAdapter().parse_product_page(_product_html(), "https://hksusa.com/category/38") is None

    def test_remarks_with_unicode_escape_recovered(self) -> None:
        # Regression: when remarks contained any JSON-Unicode escape (``\uNNNN``,
        # commonly ``&`` for ``&``), the previous body class ``[^"\\]``
        # tripped on the leading ``\`` of the escape and the surrounding
        # ``...","discontinued":...`` anchors backtracked to no match — so the
        # description landed as NULL on every row with an ``&`` in it.
        # Verify the decoded string reaches the payload AND the literal ``&``
        # comes through (not the escape sequence).
        remarks = r"Racing Suction (70020-AF108)  & Cold Air Intake Box (70026-AF005)"
        result = HKSUSAAdapter().parse_product_page(
            _product_html(remarks=remarks),
            SAMPLE_URL,
        )
        assert result is not None
        assert result.description is not None
        assert "Racing Suction" in result.description
        assert "Cold Air Intake Box" in result.description
        assert "&" in result.description
        assert "\\u0026" not in result.description


class TestFetcherTier:
    """Sanity-check the declared tier: plain HTTP (Vercel origin, no Cloudflare)."""

    def test_http_tier(self) -> None:
        assert HKSUSAAdapter.FETCHER_TIER == "http"
