"""Smoke tests for the crawler conftest helpers shipped in M002/S01/T04."""

import pytest

from app.crawlers.base import ScrapedPayload
from tests.crawlers.conftest import load_fixture_html


def test_factory_default(make_scraped_payload):
    p = make_scraped_payload()
    assert isinstance(p, ScrapedPayload)
    assert p.name == "Test Part"
    assert p.product_url == "https://example.com/p"


def test_factory_overrides(make_scraped_payload):
    p = make_scraped_payload(name="Coilover Kit", price_cents=12345)
    assert p.name == "Coilover Kit"
    assert p.price_cents == 12345


def test_load_fixture_html_existing():
    html = load_fixture_html("amsperformance")
    assert len(html) > 1000


def test_load_fixture_html_missing_raises():
    with pytest.raises(FileNotFoundError) as excinfo:
        load_fixture_html("nonexistent_adapter")
    assert "Fixture not found" in str(excinfo.value)
