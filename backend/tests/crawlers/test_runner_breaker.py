"""CRAWL-04 integration test: runner wires pybreaker around adapter.fetcher.fetch.

Replaces test_runner_circuit_breaker.py (custom counter test, DELETED in Task 2).
Covers:
  - Pre-opened breaker causes immediate bailout (rate_limit_bailout_after == 0)
  - Three consecutive FetcherErrors trip the breaker (fail_max=3)
  - Single terminal 429 pre-trips breaker via breaker.open() (D-11)
"""

import time
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.api.models.category import Category as DBCategory
from app.api.models.user import User as DBUser
from app.crawlers import runner
from app.crawlers.fetchers import FetcherError
from app.crawlers.runner import get_breaker


@pytest.fixture(autouse=True)
def _clear_breakers():
    """Prevent cross-test pollution of the process-global _BREAKERS registry under pytest-xdist."""
    runner._BREAKERS.clear()
    yield
    runner._BREAKERS.clear()


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
    adapter_name: str,
    user: DBUser,
    category: DBCategory,
    fetch_side_effects: list,
    num_urls: int | None = None,
) -> dict:
    """Run run_crawler with a stubbed adapter whose fetch() raises each provided
    side effect in turn. Patches DB + setup so we can exercise only the URL loop.

    When ``fetch_side_effects`` has fewer entries than needed, the stub still
    supplies ``num_urls`` URLs; MagicMock will reuse side_effect as an iterator
    and raise StopIteration once exhausted — caller should size appropriately.
    """
    if num_urls is None:
        num_urls = len(fetch_side_effects)
    urls = [f"https://example-breaker.test/p{i}.html" for i in range(num_urls)]

    fake_adapter = MagicMock()
    fake_adapter.FETCHER_TIER = "http"
    fake_adapter.ADAPTER_NAME = adapter_name
    fake_adapter.HEALTH_PROBE_URL = None  # opt out of the new health probe
    fake_adapter.discover_product_urls.return_value = iter(urls)
    fake_adapter.fetcher = MagicMock()
    fake_adapter.fetcher.fetch.side_effect = fetch_side_effects
    fake_adapter.parse_product_page.return_value = None
    # check_health returns healthy so the runner proceeds to the URL loop.
    from app.crawlers.adapters.base import HealthResult
    fake_adapter.check_health.return_value = HealthResult(healthy=True, reason="skipped_by_config", status_code=None)

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
        return runner.run_crawler(adapter_name, delay_sec=0)


def test_breaker_open_causes_immediate_bailout(
    db_session: Session,
    seed_user_and_category: tuple[DBUser, DBCategory],
) -> None:
    """If get_breaker("x").open() is called BEFORE run_crawler, the very first
    breaker.call() raises CircuitBreakerError and the runner bails at i=0."""
    user, category = seed_user_and_category
    adapter_name = "adapter_for_open_test"
    # Pre-trip the breaker for this adapter.
    get_breaker(adapter_name).open()
    # Feed 3 bogus success side-effects; none should actually run.
    side_effects = [MagicMock(return_value="<html></html>")] * 3

    result = _run_with_stubs(
        db_session,
        adapter_name=adapter_name,
        user=user,
        category=category,
        fetch_side_effects=side_effects,
    )

    assert result["rate_limit_bailout"] is True
    # First URL trips the breaker immediately (i starts at 1 inside the loop).
    assert result["rate_limit_bailout_after"] in (0, 1)
    assert result["ingested"] == 0


def test_three_consecutive_errors_trip_breaker(
    db_session: Session,
    seed_user_and_category: tuple[DBUser, DBCategory],
) -> None:
    """Three consecutive FetcherErrors cause the 4th breaker.call() to raise
    CircuitBreakerError; runner records rate_limit_bailout=True."""
    user, category = seed_user_and_category
    adapter_name = "adapter_for_three_consec"
    # 5 generic errors (status=500). fail_max=3 means the 4th call should trip.
    side_effects = [FetcherError("500 err", status_code=500) for _ in range(5)]

    result = _run_with_stubs(
        db_session,
        adapter_name=adapter_name,
        user=user,
        category=category,
        fetch_side_effects=side_effects,
    )

    assert result["rate_limit_bailout"] is True
    # 3 exceptions pass through the breaker; the 4th raises CircuitBreakerError
    # which triggers the bailout at i=4.
    assert result["rate_limit_bailout_after"] in (3, 4)


def test_terminal_429_pretrip(
    db_session: Session,
    seed_user_and_category: tuple[DBUser, DBCategory],
) -> None:
    """A single terminal 429 response invokes breaker.open(); the next URL's
    breaker.call() raises CircuitBreakerError and the runner bails (D-11)."""
    user, category = seed_user_and_category
    adapter_name = "adapter_for_429_pretrip"
    # First call: 429 (terminal rate-limit). Runner catches it, classifies, and
    # calls breaker.open(). Next iteration tries breaker.call() → CircuitBreakerError.
    side_effects = [FetcherError("429 rate-limited", status_code=429)] + [
        MagicMock(return_value="<html></html>") for _ in range(3)
    ]

    result = _run_with_stubs(
        db_session,
        adapter_name=adapter_name,
        user=user,
        category=category,
        fetch_side_effects=side_effects,
    )

    assert result["rate_limit_bailout"] is True
    # Trip happens on iteration 1 (429 opens breaker) or 2 (next .call raises).
    assert result["rate_limit_bailout_after"] in (1, 2)
