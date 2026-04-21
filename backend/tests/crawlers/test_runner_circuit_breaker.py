"""Tests for the adapter-level rate-limit circuit breaker in run_crawler.

When the per-URL retry loop exhausts against 429/502/503/504 on N consecutive
URLs, the runner should bail on the whole adapter rather than grind through
the rest of the list. These tests drive run_crawler directly with a stubbed
adapter + fetcher so we can assert the bailout flag, the count at which it
tripped, and that unrelated HTTP failures (404) do not accumulate toward the
trip.
"""

import time
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests
from sqlalchemy.orm import Session

from app.api.models.category import Category as DBCategory
from app.api.models.user import User as DBUser
from app.crawlers import runner


def _make_503_error() -> requests.exceptions.HTTPError:
    resp = requests.Response()
    resp.status_code = 503
    err = requests.exceptions.HTTPError("503 Service Unavailable")
    err.response = resp
    return err


def _make_404_error() -> requests.exceptions.HTTPError:
    resp = requests.Response()
    resp.status_code = 404
    err = requests.exceptions.HTTPError("404 Not Found")
    err.response = resp
    return err


@pytest.fixture()
def seed_user_and_category(db_session: Session) -> tuple[DBUser, DBCategory]:
    user = DBUser(
        id=uuid4(),
        username=f"svc-{uuid4().hex[:8]}",
        email=f"svc-{uuid4().hex[:8]}@example.test",
        hashed_password="x",
        email_verified=True,
        is_service_account=True,
    )
    category = DBCategory(id=uuid4(), name=f"cat-{uuid4().hex[:8]}")
    db_session.add_all([user, category])
    db_session.commit()
    return user, category


def _run_with_stubs(
    db_session: Session,
    *,
    user: DBUser,
    category: DBCategory,
    fetch_side_effects: list,
) -> dict:
    """Run run_crawler with a stubbed adapter whose fetch() raises each
    provided side effect in turn. Patches DB + setup so we can exercise
    only the URL loop."""
    num_urls = len(fetch_side_effects)
    urls = [f"https://example-circuit-breaker.test/p{i}.html" for i in range(num_urls)]

    fake_adapter = MagicMock()
    fake_adapter.FETCHER_TIER = "http"
    fake_adapter.discover_product_urls.return_value = iter(urls)
    fake_adapter.fetcher = MagicMock()
    fake_adapter.fetcher.fetch.side_effect = fetch_side_effects
    fake_adapter.parse_product_page.return_value = None

    # SessionLocal is called once and the returned object's .close() runs in
    # the finally block. We delegate every real op to the test's db_session
    # but swallow close() so the fixture can continue using it after the run.
    db_mock = MagicMock(wraps=db_session)
    db_mock.close = MagicMock()

    with (
        patch.object(runner, "SessionLocal", return_value=db_mock),
        patch.object(runner, "resolve_crawler_user", return_value=user),
        patch.object(runner, "resolve_default_category_id", return_value=category.id),
        patch.object(runner, "get_fetcher"),
        patch.object(runner, "get_adapter", return_value=fake_adapter),
        patch.object(runner, "can_fetch_url", return_value=True),
        patch.object(runner, "get_crawl_delay_sec", return_value=None),
        patch.object(runner, "apply_delay_jitter", return_value=0),
        patch.object(time, "sleep"),
    ):
        return runner.run_crawler("fake_adapter_for_test", delay_sec=0)


def test_circuit_breaker_trips_after_threshold_consecutive_503s(
    db_session: Session,
    seed_user_and_category: tuple[DBUser, DBCategory],
) -> None:
    """Five consecutive 503s should trip the breaker and break the loop."""
    user, category = seed_user_and_category
    threshold = runner.RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD
    # Queue up 20 URLs-worth of 503s; we expect to bail at `threshold`.
    side_effects = [_make_503_error() for _ in range(20)]

    result = _run_with_stubs(
        db_session,
        user=user,
        category=category,
        fetch_side_effects=side_effects,
    )

    assert result["rate_limit_bailout"] is True
    assert result["rate_limit_bailout_after"] == threshold
    assert result["total"] == 20
    assert result["ingested"] == 0
    assert result["errors"] == threshold
    # http_errors dict keyed by stringified status.
    assert result["http_errors"].get("503") == threshold


def test_404s_do_not_trip_the_circuit_breaker(
    db_session: Session,
    seed_user_and_category: tuple[DBUser, DBCategory],
) -> None:
    """Gone URLs (404) are server-alive evidence and must not accumulate."""
    user, category = seed_user_and_category
    # 20 × 404 — well over the threshold, but none should count as rate-limited.
    side_effects = [_make_404_error() for _ in range(20)]

    result = _run_with_stubs(
        db_session,
        user=user,
        category=category,
        fetch_side_effects=side_effects,
    )

    assert result["rate_limit_bailout"] is False
    assert result["total"] == 20
    # All 20 404s should have been processed as "gone" skips, not errors.
    assert result["skipped_gone"] == 20


def test_404_between_503s_resets_consecutive_counter(
    db_session: Session,
    seed_user_and_category: tuple[DBUser, DBCategory],
) -> None:
    """A healthy-looking non-rate-limit response in the middle should reset
    the streak, so we don't bail when the 503s are intermittent."""
    user, category = seed_user_and_category
    threshold = runner.RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD
    # (threshold - 1) 503s, then a 404, then (threshold - 1) 503s, then a 404.
    # Neither run of 503s reaches the threshold.
    side_effects: list = []
    for _ in range(threshold - 1):
        side_effects.append(_make_503_error())
    side_effects.append(_make_404_error())
    for _ in range(threshold - 1):
        side_effects.append(_make_503_error())
    side_effects.append(_make_404_error())

    result = _run_with_stubs(
        db_session,
        user=user,
        category=category,
        fetch_side_effects=side_effects,
    )

    assert result["rate_limit_bailout"] is False
    assert result["total"] == len(side_effects)
    assert result["errors"] == 2 * (threshold - 1)
    assert result["skipped_gone"] == 2
