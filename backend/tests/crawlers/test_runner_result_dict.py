"""CRAWL-07 unit test: runner result dict includes parse_failures, sample_failure_urls[:5], elapsed_seconds.

These tests assert the schema delta introduced by Plan 03-03 on top of the Plan 03-02
result dict (parse_failures + sample_failure_urls + elapsed_seconds keys, per D-22/D-23
and RESEARCH Open Q #4). They cover only the successful (all-URLs-processed) code path;
the breaker-bail and health-skip paths are exercised elsewhere.

Parse-miss scenario: adapter.fetcher.fetch succeeds on every URL (returns "<html>"),
but adapter.parse_product_page returns None — the runner counts each as a
"skipped_not_product" and records it in parse_miss_urls, which in turn feed
parse_failures / sample_failure_urls.
"""

import time
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.api.models.category import Category as DBCategory
from app.api.models.user import User as DBUser
from app.crawlers import runner


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


def _run_with_parse_misses(
    db_session: Session,
    *,
    adapter_name: str,
    user: DBUser,
    category: DBCategory,
    num_urls: int,
) -> tuple[dict, list[str]]:
    """Run run_crawler with a stubbed adapter that succeeds fetching ``num_urls``
    URLs but returns ``None`` from ``parse_product_page`` for every one of them.

    Returns (result_dict, list_of_urls_in_encounter_order).
    """
    urls = [f"https://example-parse-miss.test/p{i}.html" for i in range(num_urls)]

    fake_adapter = MagicMock()
    fake_adapter.FETCHER_TIER = "http"
    fake_adapter.ADAPTER_NAME = adapter_name
    fake_adapter.HEALTH_PROBE_URL = None
    fake_adapter.discover_product_urls.return_value = iter(urls)
    fake_adapter.fetcher = MagicMock()
    # Every fetch succeeds and returns HTML.
    fake_adapter.fetcher.fetch.return_value = "<html></html>"
    # Every parse returns None → skipped_not_product.
    fake_adapter.parse_product_page.return_value = None
    # Opt-out health probe.
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
        return runner.run_crawler(adapter_name, delay_sec=0), urls


def test_result_dict_includes_parse_failures(
    db_session: Session,
    seed_user_and_category: tuple[DBUser, DBCategory],
) -> None:
    """parse_failures equals the count of parse-miss URLs (7) — alias for skipped_not_product."""
    user, category = seed_user_and_category
    result, _urls = _run_with_parse_misses(
        db_session,
        adapter_name="adapter_parse_failures",
        user=user,
        category=category,
        num_urls=7,
    )
    assert result["skipped_not_product"] == 7
    assert result["parse_failures"] == 7


def test_sample_failure_urls_first_five_urls_only(
    db_session: Session,
    seed_user_and_category: tuple[DBUser, DBCategory],
) -> None:
    """sample_failure_urls is exactly 5 strings (not dicts) when 7 misses occur."""
    user, category = seed_user_and_category
    result, _urls = _run_with_parse_misses(
        db_session,
        adapter_name="adapter_sample_five",
        user=user,
        category=category,
        num_urls=7,
    )
    samples = result["sample_failure_urls"]
    assert len(samples) == 5
    for entry in samples:
        assert isinstance(entry, str), f"expected str, got {type(entry).__name__}: {entry!r}"


def test_sample_failure_urls_preserves_order(
    db_session: Session,
    seed_user_and_category: tuple[DBUser, DBCategory],
) -> None:
    """sample_failure_urls holds the FIRST 5 encountered URLs (not evenly sampled / not sorted)."""
    user, category = seed_user_and_category
    result, urls = _run_with_parse_misses(
        db_session,
        adapter_name="adapter_sample_order",
        user=user,
        category=category,
        num_urls=7,
    )
    assert result["sample_failure_urls"] == urls[:5]


def test_elapsed_seconds_non_negative(
    db_session: Session,
    seed_user_and_category: tuple[DBUser, DBCategory],
) -> None:
    """elapsed_seconds is a non-negative float recording URL-loop wall time."""
    user, category = seed_user_and_category
    result, _urls = _run_with_parse_misses(
        db_session,
        adapter_name="adapter_elapsed",
        user=user,
        category=category,
        num_urls=3,
    )
    assert "elapsed_seconds" in result
    assert isinstance(result["elapsed_seconds"], float)
    assert result["elapsed_seconds"] >= 0.0
