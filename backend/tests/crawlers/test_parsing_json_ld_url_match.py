"""Tests for the URL-aware Product picker in ``extract_json_ld_product``.

Some Wix/CMS pages ship a JSON-LD ``Product`` block whose declared URL points
at a *different* product than the page the user is viewing. Trusting the
first Product blindly (the previous behavior) let that stray block overwrite
the scrape with the wrong part's name/description. These tests pin the
"prefer URL-matching Product, else accept URL-less Product, else None" rule.
"""

from app.crawlers.parsing import extract_json_ld_product


def _wrap(json_ld: str) -> str:
    return f'<html><head><script type="application/ld+json">{json_ld}</script></head></html>'


def test_single_product_with_matching_offer_url_is_returned() -> None:
    html = _wrap("""
        {"@context":"https://schema.org","@type":"Product",
         "name":"Widebody Kit",
         "offers":{"@type":"Offer","url":"https://shop.example/product/widebody"}}
        """)
    item = extract_json_ld_product(html, product_url="https://shop.example/product/widebody")
    assert item is not None
    assert item["name"] == "Widebody Kit"


def test_single_product_with_mismatched_offer_url_is_rejected() -> None:
    # This is the a90shop regression: the page is /product-page/widebody-kit,
    # the JSON-LD Product is for /product-page/swan-neck-wing. Accepting it
    # would replace the form with the wrong product's data.
    html = _wrap("""
        {"@context":"https://schema.org","@type":"Product",
         "name":"Swan Neck Wing",
         "offers":{"@type":"Offer","url":"https://shop.example/product/swan-neck-wing"}}
        """)
    item = extract_json_ld_product(html, product_url="https://shop.example/product/widebody-kit")
    assert item is None


def test_product_without_declared_urls_is_accepted_as_fallback() -> None:
    # Some sites omit url/@id on Product altogether. In that case we can't
    # verify alignment — trust it like the legacy behavior so those stores
    # keep working.
    html = _wrap("""
        {"@context":"https://schema.org","@type":"Product",
         "name":"Generic Part",
         "offers":{"@type":"Offer","price":"10"}}
        """)
    item = extract_json_ld_product(html, product_url="https://shop.example/product/anything")
    assert item is not None
    assert item["name"] == "Generic Part"


def test_prefers_url_matching_product_when_multiple_present() -> None:
    # Two Product blocks in one script. Picker must prefer the one whose url
    # matches the page over the one that comes first.
    html = _wrap("""
        [
          {"@context":"https://schema.org","@type":"Product","name":"Other Product",
           "url":"https://shop.example/product/other"},
          {"@context":"https://schema.org","@type":"Product","name":"Page Product",
           "url":"https://shop.example/product/this-one"}
        ]
        """)
    item = extract_json_ld_product(html, product_url="https://shop.example/product/this-one")
    assert item is not None
    assert item["name"] == "Page Product"


def test_url_comparison_tolerates_scheme_host_case_and_trailing_slash() -> None:
    # Scheme and host are case-insensitive per RFC 3986; path is
    # case-sensitive. Trailing slash is a common cosmetic difference. Match
    # on those so JSON-LD with ``HTTPS://Shop.Example/product/widebody/``
    # still aligns with a page url of ``https://shop.example/product/widebody``.
    html = _wrap("""
        {"@context":"https://schema.org","@type":"Product","name":"Kit",
         "url":"HTTPS://Shop.Example/product/widebody/"}
        """)
    item = extract_json_ld_product(html, product_url="https://shop.example/product/widebody")
    assert item is not None
    assert item["name"] == "Kit"


def test_url_comparison_collapses_http_and_https() -> None:
    # vividracing.com (and other legacy storefronts) emit JSON-LD with
    # ``url`` set to ``http://...`` even though the canonical page is served
    # over https. A strict scheme match would reject every Product on those
    # sites, the adapter would fall through to the DOM/og fallback, and
    # chassis tokens from the title (IS300, AE86, JZA80) would land in
    # part_number via the title-shape heuristic.
    html = _wrap("""
        {"@context":"https://schema.org","@type":"Product","name":"Cusco Sway Bar",
         "url":"http://www.vividracing.com/cusco-sway-bar-p-1825.html",
         "sku":"195 311 B"}
        """)
    item = extract_json_ld_product(
        html, product_url="https://www.vividracing.com/cusco-sway-bar-p-1825.html"
    )
    assert item is not None
    assert item["sku"] == "195 311 B"


def test_product_url_omitted_preserves_legacy_behavior() -> None:
    # No product_url passed → first Product wins, regardless of any declared
    # JSON-LD url. Keeps existing non-Chrome-extension callers that never
    # supplied a page URL working unchanged.
    html = _wrap("""
        [
          {"@context":"https://schema.org","@type":"Product","name":"First",
           "url":"https://shop.example/a"},
          {"@context":"https://schema.org","@type":"Product","name":"Second",
           "url":"https://shop.example/b"}
        ]
        """)
    item = extract_json_ld_product(html)
    assert item is not None
    assert item["name"] == "First"


def test_graph_shape_is_walked_for_products() -> None:
    html = _wrap("""
        {"@context":"https://schema.org","@graph":[
           {"@type":"BreadcrumbList"},
           {"@type":"Product","name":"From Graph",
            "url":"https://shop.example/product/target"}
        ]}
        """)
    item = extract_json_ld_product(html, product_url="https://shop.example/product/target")
    assert item is not None
    assert item["name"] == "From Graph"
