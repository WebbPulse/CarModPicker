"""CRAWL-06 unit test: adapter.check_health() probe classification.

Covers:
  - HEALTH_PROBE_URL=None → opt-out (skipped_by_config, healthy=True)
  - 4xx → unhealthy, reason="http_4xx", status_code=<code>
  - Timeout → unhealthy, reason="timeout", status_code=None
"""

from typing import ClassVar, Iterator, Optional
from unittest.mock import MagicMock

from app.crawlers.adapters.base import HealthResult, RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.fetchers import FetcherError


class _SkipAdapter(RetailerCrawlerAdapter):
    """Opts out by leaving HEALTH_PROBE_URL=None."""

    ADAPTER_NAME: ClassVar[str] = "test_skip"
    HEALTH_PROBE_URL: ClassVar[Optional[str]] = None

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return None


class _ProbeAdapter(RetailerCrawlerAdapter):
    """Opts in with HEALTH_PROBE_URL set."""

    ADAPTER_NAME: ClassVar[str] = "test_probe"
    HEALTH_PROBE_URL: ClassVar[Optional[str]] = "https://host.test/robots.txt"

    def discover_product_urls(self) -> Iterator[str]:
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        return None


def test_none_probe_skips() -> None:
    """HEALTH_PROBE_URL=None → HealthResult(healthy=True, reason='skipped_by_config')."""
    adapter = _SkipAdapter()
    result = adapter.check_health()
    assert result.healthy is True
    assert result.reason == "skipped_by_config"
    assert result.status_code is None


def test_http_4xx_marks_unhealthy() -> None:
    """FetcherError with 404 status → healthy=False, reason='http_4xx', status_code=404."""
    adapter = _ProbeAdapter()
    fake_fetcher = MagicMock()
    fake_fetcher.fetch.side_effect = FetcherError("404 not found", status_code=404)
    adapter._fetcher = fake_fetcher  # inject for test

    result = adapter.check_health()

    assert result.healthy is False
    assert result.reason == "http_4xx"
    assert result.status_code == 404


def test_timeout_marks_unhealthy() -> None:
    """FetcherError classified as timeout → healthy=False, reason='timeout'."""
    import requests

    adapter = _ProbeAdapter()
    fake_fetcher = MagicMock()
    # A timeout raised by the fetcher tier; _classify_fetch_error returns "timeout"
    # for requests.exceptions.Timeout. FetcherError wrapping a timeout reports
    # status_code=None and classification=fetcher; we key on None-status bucketing.
    # Simulate a requests.Timeout leaking through fetcher as-is (HttpFetcher path):
    fake_fetcher.fetch.side_effect = requests.exceptions.Timeout("probe timeout")
    adapter._fetcher = fake_fetcher

    result = adapter.check_health()

    assert result.healthy is False
    assert result.reason == "timeout"
    assert result.status_code is None
