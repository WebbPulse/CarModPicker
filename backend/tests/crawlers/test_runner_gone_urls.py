"""Tests for 404/410 persistence + filtering in runner.py.

When a retailer sitemap advertises a removed product URL, the runner would
previously re-fetch and 404 on it every run. These tests verify that:

1. `_mark_url_gone` upserts a CrawledPage with parse_status='gone'.
2. An existing CrawledPage (even parsed, with a part_id) can be flipped to 'gone'.
3. The discovery filter in run_crawler unconditionally skips 'gone' URLs,
   and additionally skips 'parsed' URLs when skip_known_urls=True.
"""

from datetime import datetime, timezone
from uuid import uuid4

import requests
from sqlalchemy.orm import Session

from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.crawlers import runner
from app.crawlers.base import canonicalize_url
from app.crawlers.fetchers import FetcherError, FlareSolverrError


def test_mark_url_gone_inserts_new_row(db_session: Session) -> None:
    url = "https://example.com/products/removed-item"
    runner._mark_url_gone(db_session, url=url, source="example_adapter")
    db_session.commit()

    row = db_session.query(DBCrawledPage).filter(DBCrawledPage.url == url).one()
    assert row.parse_status == "gone"
    assert row.source == "example_adapter"
    assert row.html_s3_key is None
    assert row.html_local_path is None


def test_mark_url_gone_flips_existing_parsed_row(db_session: Session) -> None:
    """A URL that was previously parsed (product got removed) should be marked gone."""
    url = "https://example.com/products/used-to-exist"
    existing = DBCrawledPage(
        id=uuid4(),
        url=url,
        source="example_adapter",
        parse_status="parsed",
        crawled_at=datetime.now(timezone.utc),
        last_parsed_at=datetime.now(timezone.utc),
        html_sha256="a" * 64,
    )
    db_session.add(existing)
    db_session.commit()

    runner._mark_url_gone(db_session, url=url, source="example_adapter")
    db_session.commit()

    row = db_session.query(DBCrawledPage).filter(DBCrawledPage.url == url).one()
    assert row.parse_status == "gone"


def testhttp_status_from_exception_handles_all_fetcher_types() -> None:
    """404 must be extractable from all three fetcher error shapes the runner sees."""
    # HttpFetcher path: requests.HTTPError with a Response object
    resp = requests.Response()
    resp.status_code = 404
    http_err = requests.exceptions.HTTPError("404 Not Found")
    http_err.response = resp
    assert runner.http_status_from_exception(http_err) == 404

    # TlsFetcher path: FetcherError with explicit status_code
    tls_err = FetcherError("TlsFetcher got HTTP 404", status_code=404)
    assert runner.http_status_from_exception(tls_err) == 404

    # FlareSolverrFetcher path: FlareSolverrError (subclass of FetcherError)
    flare_err = FlareSolverrError("upstream 410", status_code=410)
    assert runner.http_status_from_exception(flare_err) == 410

    # Timeouts and other non-HTTP errors return None
    assert runner.http_status_from_exception(TimeoutError("slow")) is None
    assert runner.http_status_from_exception(FetcherError("request failed")) is None


def _query_filter_urls(
    db: Session,
    candidate_urls: list[str],
    *,
    skip_known_urls: bool,
) -> list[str]:
    """Replicate the discovery filter logic from run_crawler for direct testing."""
    canonical = [canonicalize_url(u) for u in candidate_urls]
    statuses_to_skip = ["gone"]
    if skip_known_urls:
        statuses_to_skip.append("parsed")
    skip_set = {
        row.url
        for row in db.query(DBCrawledPage.url)
        .filter(
            DBCrawledPage.url.in_(canonical),
            DBCrawledPage.parse_status.in_(statuses_to_skip),
        )
        .all()
    }
    return [u for u in candidate_urls if canonicalize_url(u) not in skip_set]


def test_discovery_filters_gone_unconditionally(db_session: Session) -> None:
    gone_url = "https://example.com/products/dead"
    live_url = "https://example.com/products/alive"
    parsed_url = "https://example.com/products/already-got"

    db_session.add_all(
        [
            DBCrawledPage(
                id=uuid4(),
                url=gone_url,
                source="example_adapter",
                parse_status="gone",
                crawled_at=datetime.now(timezone.utc),
            ),
            DBCrawledPage(
                id=uuid4(),
                url=parsed_url,
                source="example_adapter",
                parse_status="parsed",
                crawled_at=datetime.now(timezone.utc),
                last_parsed_at=datetime.now(timezone.utc),
            ),
        ]
    )
    db_session.commit()

    # skip_known_urls=False → gone is filtered, parsed is not
    remaining = _query_filter_urls(
        db_session,
        [gone_url, live_url, parsed_url],
        skip_known_urls=False,
    )
    assert gone_url not in remaining
    assert live_url in remaining
    assert parsed_url in remaining

    # skip_known_urls=True → both gone and parsed are filtered
    remaining = _query_filter_urls(
        db_session,
        [gone_url, live_url, parsed_url],
        skip_known_urls=True,
    )
    assert remaining == [live_url]
