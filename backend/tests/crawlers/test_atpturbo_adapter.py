"""
Tests for atpturbo.com adapter: Miva Merchant URL shape, 404 detection by
title, BFS discovery from the catalog home, and DOM parsing of Product_Code
/ title / price / image / description out of the ATP Turbo product page.
"""

from bs4 import BeautifulSoup

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http.atpturbo import (
    ATPTURBO_HOUSE_BRAND,
    ATPTurboAdapter,
    _canonical_product_url,
    _discover_via_bfs,
    _is_category_url,
    _is_not_found_page,
    _is_product_url,
    _resolve_part_manufacturer,
)

SAMPLE_URL = "https://www.atpturbo.com/mm5/merchant.mvc" "?Screen=PROD&Store_Code=tp&Product_Code=GRT-TBO-562"


def _product_html(
    *,
    title: str = "GEN2 Garrett GTX3071R Turbo - w/ Alternate Comp/Turbine Housing Choices",
    part_code: str = "GRT-TBO-562",
    price: str = "$2,363.73",
    image_src: str = "graphics/00000001/GG2T04BB1.jpg",
    description: str = (
        "<b>PRODUCT DESCRIPTION:</b> Garrett GEN2 GTX3071R dual ball bearing "
        "turbocharger. Advanced GEN2 billet compressor wheel capable of 650HP."
    ),
) -> str:
    """
    Mirrors the real Miva Merchant PDP shape: a ``<title>`` with the
    ``: atpturbo.com`` suffix, a ``<base href="/mm5/">``, the
    ``Code: <b>…</b>`` label, the ``#price-value`` span, a product image
    with ``id="ProductMainImage"``, and an inner ``div.product_display``
    carrying the description copy alongside an embedded add-to-cart form
    that must be stripped from the description payload.
    """
    return f"""
    <html>
      <head>
        <title>{title} : atpturbo.com</title>
        <base href="/mm5/">
      </head>
      <body>
        <span class="product_display">
          <div style="font-weight:bold;color:#003399;font-size:17px;">{title}</div>
          <div>
            Code: <b>{part_code}</b><br>
            Price: <b><span id="price-value">{price}</span></b><br>
            <form method="post" action="/mm5/merchant.mvc?">
              <input type="hidden" name="Action" value="ADPR">
              <input type="hidden" name="Product_Code" value="{part_code}">
              <button type="submit" class="AddCart">Add to Cart</button>
            </form>
          </div>
          <img id="ProductMainImage" src="{image_src}" alt="{title}">
          <div style="text-align:left;" class="product_display">
            {description}
          </div>
        </span>
        <!-- Related products carry their own Product_Code hidden inputs -->
        <form><input type="hidden" name="Product_Code" value="ATP-OIL-003"></form>
      </body>
    </html>
    """


class TestAdapterRegistration:
    def test_www_subdomain_routes_to_atpturbo(self) -> None:
        assert adapter_name_for_product_url(SAMPLE_URL) == "atpturbo"

    def test_bare_host_routes_to_atpturbo(self) -> None:
        assert (
            adapter_name_for_product_url(
                "https://atpturbo.com/mm5/merchant.mvc?Screen=PROD&Store_Code=tp&Product_Code=X"
            )
            == "atpturbo"
        )

    def test_unrelated_host_falls_back_to_generic(self) -> None:
        assert adapter_name_for_product_url("https://example.com/atpturbo") == "generic"


class TestIsProductUrl:
    def test_prod_screen_is_product(self) -> None:
        assert _is_product_url(SAMPLE_URL)

    def test_prod_screen_without_product_code_rejected(self) -> None:
        assert not _is_product_url("https://www.atpturbo.com/mm5/merchant.mvc?Screen=PROD&Store_Code=tp")

    def test_category_url_is_not_product(self) -> None:
        assert not _is_product_url(
            "https://www.atpturbo.com/mm5/merchant.mvc" "?Screen=CTGY&Store_Code=tp&Category_Code=TBO"
        )

    def test_cart_and_cms_screens_rejected(self) -> None:
        for url in (
            "https://www.atpturbo.com/mm5/merchant.mvc?Screen=BASK&Store_Code=tp",
            "https://www.atpturbo.com/mm5/merchant.mvc?Screen=OLST&Store_Code=tp",
            "https://www.atpturbo.com/mm5/merchant.mvc?Screen=ABOUT",
            "https://www.atpturbo.com/mm5/merchant.mvc?Screen=FAQ",
            "https://www.atpturbo.com/mm5/",
            "https://www.atpturbo.com/",
        ):
            assert not _is_product_url(url), url

    def test_wrong_host_rejected(self) -> None:
        assert not _is_product_url("https://example.com/mm5/merchant.mvc?Screen=PROD&Product_Code=X")


class TestIsCategoryUrl:
    def test_ctgy_with_code_is_category(self) -> None:
        assert _is_category_url(
            "https://www.atpturbo.com/mm5/merchant.mvc" "?Screen=CTGY&Store_Code=tp&Category_Code=TBO"
        )

    def test_ctgy_without_code_rejected(self) -> None:
        # "Go to the category landing page" links sometimes omit Category_Code;
        # discovery can't queue those.
        assert not _is_category_url("https://www.atpturbo.com/mm5/merchant.mvc?Screen=CTGY&Store_Code=tp")

    def test_product_url_is_not_category(self) -> None:
        assert not _is_category_url(SAMPLE_URL)


class TestNotFoundDetection:
    def test_not_found_title_rejected(self) -> None:
        html = "<html><head><title>atpturbo.com : Not Found</title></head><body></body></html>"
        assert _is_not_found_page(BeautifulSoup(html, "html.parser"))

    def test_real_product_title_accepted(self) -> None:
        html = "<html><head><title>GEN2 Garrett GTX3071R Turbo : atpturbo.com</title>" "</head><body></body></html>"
        assert not _is_not_found_page(BeautifulSoup(html, "html.parser"))


class TestResolvePartManufacturer:
    """Part-code prefix is authoritative; title tokens are a fallback."""

    def test_garrett_prefix(self) -> None:
        assert _resolve_part_manufacturer("GRT-TBO-562", "GEN2 GTX3071R Turbo") == "Garrett"

    def test_atp_house_prefix(self) -> None:
        assert (
            _resolve_part_manufacturer(
                "ATP-FLA-010",
                "Aluminum - Oil Drain ( return ) Flange (GT25, GT28)",
            )
            == ATPTURBO_HOUSE_BRAND
        )

    def test_precision_prefix(self) -> None:
        assert _resolve_part_manufacturer("PRE-TBO-6266", "Precision 6266 CEA Turbo") == "Precision"

    def test_borgwarner_prefix(self) -> None:
        assert _resolve_part_manufacturer("BW-TBO-EFR7163", "BorgWarner EFR 7163 Turbo") == "BorgWarner"

    def test_unknown_prefix_falls_back_to_title(self) -> None:
        # ZZZ is not in the prefix table; the title-token heuristic picks up
        # the leading brand so a new vendor doesn't orphan without attention.
        result = _resolve_part_manufacturer("ZZZ-TBO-001", "TiAL MVS 38mm Wastegate")
        assert result == "TiAL"


class TestParseProductPage:
    def test_full_page_parses(self) -> None:
        result = ATPTurboAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.name == "GEN2 Garrett GTX3071R Turbo - w/ Alternate Comp/Turbine Housing Choices"
        assert result.part_number == "GRT-TBO-562"
        assert result.part_manufacturer == "Garrett"
        assert result.price_cents == 236373
        assert result.product_url == _canonical_product_url("GRT-TBO-562")
        assert result.description is not None
        assert "dual ball bearing turbocharger" in result.description

    def test_image_resolved_against_base_href(self) -> None:
        # Miva emits a <base href="/mm5/"> and the product image uses
        # ``graphics/...`` without a leading slash — the parser must
        # resolve against ``/mm5/`` so the stored URL is absolute.
        result = ATPTurboAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        assert result.image_urls is not None
        assert result.image_urls == ["https://www.atpturbo.com/mm5/graphics/00000001/GG2T04BB1.jpg"]

    def test_description_strips_embedded_form(self) -> None:
        # The inner ``div.product_display`` on some products contains a
        # related-product quick-buy form. Those forms carry Product_Code
        # hidden inputs and button text that must not bleed into the
        # description text the catalog stores.
        html = _product_html(
            description=(
                "Fits GT28/GT30 housings. "
                '<form><input name="Product_Code" value="ATP-OIL-003">'
                "<button>Add to Cart</button></form>"
                " Aluminum construction."
            )
        )
        result = ATPTurboAdapter().parse_product_page(html, SAMPLE_URL)
        assert result is not None
        assert result.description is not None
        assert "Add to Cart" not in result.description
        assert "ATP-OIL-003" not in result.description
        assert "Aluminum construction" in result.description

    def test_category_url_returns_none(self) -> None:
        # The Chrome-extension routing sometimes hands this parser a
        # category page URL when the user right-clicks on the wrong page.
        html = _product_html()
        result = ATPTurboAdapter().parse_product_page(
            html,
            "https://www.atpturbo.com/mm5/merchant.mvc?Screen=CTGY&Category_Code=TBO",
        )
        assert result is None

    def test_not_found_returns_none(self) -> None:
        html = "<html><head><title>atpturbo.com : Not Found</title></head>" "<body><h1>Not Found</h1></body></html>"
        assert ATPTurboAdapter().parse_product_page(html, SAMPLE_URL) is None

    def test_canonical_url_strips_extra_params(self) -> None:
        # Miva sometimes appends ``&Category_Code=XXX`` to product URLs for
        # breadcrumb tracking. The stored product_url should canonicalize
        # so two variants of the same SKU collapse to one catalog row.
        decorated_url = SAMPLE_URL + "&Category_Code=GG2-3071"
        result = ATPTurboAdapter().parse_product_page(_product_html(), decorated_url)
        assert result is not None
        assert result.product_url == _canonical_product_url("GRT-TBO-562")


class TestDiscoverViaBfs:
    def test_bfs_collects_products_across_subcategories(self) -> None:
        """
        Catalog home → two top-level categories → nested subcategory +
        products. The walker must follow Category_Code links and collect
        Product_Code values from <a href> anchors anywhere in the tree.
        """
        home_html = """
        <html><body>
          <a href="/mm5/merchant.mvc?Screen=CTGY&Store_Code=tp&Category_Code=TBO">Turbos</a>
          <a href="/mm5/merchant.mvc?Screen=CTGY&Store_Code=tp&Category_Code=FLG">Flanges</a>
        </body></html>
        """
        tbo_html = """
        <html><body>
          <a href="merchant.mvc?Screen=CTGY&Store_Code=tp&Category_Code=GG2">Garrett Gen2</a>
          <a href="merchant.mvc?Screen=PROD&Store_Code=tp&Product_Code=GRT-TBO-562">GTX3071R</a>
        </body></html>
        """
        gg2_html = """
        <html><body>
          <a href="merchant.mvc?Screen=PROD&Store_Code=tp&Product_Code=GRT-TBO-765">G30-660</a>
          <a href="merchant.mvc?Screen=PROD&Store_Code=tp&Product_Code=GRT-TBO-562">GTX3071R (dup)</a>
        </body></html>
        """
        flg_html = """
        <html><body>
          <a href="merchant.mvc?Screen=PROD&Store_Code=tp&Product_Code=ATP-FLA-010">Drain Flange</a>
        </body></html>
        """
        pages = {
            "https://www.atpturbo.com/mm5/": home_html,
            "https://www.atpturbo.com/mm5/merchant.mvc?Screen=CTGY&Store_Code=tp&Category_Code=TBO": tbo_html,
            "https://www.atpturbo.com/mm5/merchant.mvc?Screen=CTGY&Store_Code=tp&Category_Code=GG2": gg2_html,
            "https://www.atpturbo.com/mm5/merchant.mvc?Screen=CTGY&Store_Code=tp&Category_Code=FLG": flg_html,
        }

        def fetch(url: str) -> str:
            return pages[url]

        urls = _discover_via_bfs(fetch)
        assert _canonical_product_url("GRT-TBO-562") in urls
        assert _canonical_product_url("GRT-TBO-765") in urls
        assert _canonical_product_url("ATP-FLA-010") in urls
        # Duplicates across subcategories must collapse.
        assert len(urls) == len(set(urls))

    def test_bfs_tolerates_fetch_failure(self) -> None:
        """A broken subcategory must not halt the walk — sibling branches
        still complete so we recover a useful discovery set."""

        def fetch(url: str) -> str:
            if "Category_Code=TBO" in url:
                raise RuntimeError("upstream 502")
            if url == "https://www.atpturbo.com/mm5/":
                return """
                <html><body>
                  <a href="/mm5/merchant.mvc?Screen=CTGY&Store_Code=tp&Category_Code=TBO">Turbos</a>
                  <a href="/mm5/merchant.mvc?Screen=CTGY&Store_Code=tp&Category_Code=FLG">Flanges</a>
                </body></html>
                """
            return (
                '<html><body><a href="merchant.mvc?Screen=PROD&Store_Code=tp'
                '&Product_Code=ATP-FLA-010">Flange</a></body></html>'
            )

        urls = _discover_via_bfs(fetch)
        assert _canonical_product_url("ATP-FLA-010") in urls

    def test_bfs_empty_when_home_fetch_fails(self) -> None:
        def fetch(url: str) -> str:
            raise RuntimeError(f"network down: {url}")

        assert _discover_via_bfs(fetch) == []
