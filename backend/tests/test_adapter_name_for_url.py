"""Tests for mapping product URLs to crawler adapter names."""

from app.crawlers.adapters import adapter_name_for_product_url


def test_a90shop_hosts() -> None:
    assert adapter_name_for_product_url("https://www.a90shop.com/product-page/foo") == "a90shop"
    assert adapter_name_for_product_url("https://a90shop.com/product-page/foo") == "a90shop"


def test_studiorsr_hosts() -> None:
    assert adapter_name_for_product_url("https://studiorsr.com/products/bar") == "studiorsr"
    assert adapter_name_for_product_url("https://www.studiorsr.com/products/bar") == "studiorsr"


def test_unknown_host() -> None:
    assert adapter_name_for_product_url("https://example.com/p/1") is None
