"""Unit tests for URL-level parallel dispatch in ``run_rescrape_all_archived_pages``.

The per-page work (``rescrape_crawled_page_from_archive``) is exercised separately in
``tests/test_crawled_page_storage.py`` via the ``/re-parse`` endpoint. Here we stub
that function and the session factory so we can verify *the dispatcher* — outcome
aggregation, worker-count selection, stop-event handling — without standing up S3,
adapters, or the ingest pipeline.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.crawlers import archive_rescrape


def _mk_row(url: str = "https://x.example/p/1", source: str = "a90shop") -> SimpleNamespace:
    """Mimic the named-tuple row returned by ``db.query(id, url, source)``."""
    return SimpleNamespace(id=uuid4(), url=url, source=source)


def _stub_session_factory() -> MagicMock:
    """Return a MagicMock session that answers ``.get()`` (any entity) with a MagicMock."""
    session = MagicMock()
    # Workers call .get(DBCrawledPage, page_id) and .get(DBUser, user_id).
    session.get.return_value = MagicMock()
    return session


def _outer_db_with_rows(rows: list[SimpleNamespace]) -> MagicMock:
    """A mock outer Session whose query().filter().order_by().all() returns ``rows``."""
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.all.return_value = rows
    outer = MagicMock()
    outer.query.return_value = q
    return outer


class TestComputeRescrapeWorkers:
    def test_respects_db_pool_budget(self) -> None:
        """Worker count caps at the DB pool budget even for huge page counts."""
        # Budget = DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE
        # With current defaults: 25 + 75 - 20 = 80.
        with patch.dict("os.environ", {}, clear=False):
            if "CRAWLER_RESCRAPE_MAX_WORKERS" in __import__("os").environ:
                del __import__("os").environ["CRAWLER_RESCRAPE_MAX_WORKERS"]
            workers = archive_rescrape._compute_rescrape_workers(10_000)
        expected = (
            archive_rescrape.DB_POOL_SIZE + archive_rescrape.DB_MAX_OVERFLOW - archive_rescrape.API_CONNECTION_RESERVE
        )
        assert workers == expected

    def test_env_override_applies_when_lower(self) -> None:
        """CRAWLER_RESCRAPE_MAX_WORKERS is an operator cap, never a floor."""
        with patch.dict("os.environ", {"CRAWLER_RESCRAPE_MAX_WORKERS": "4"}):
            assert archive_rescrape._compute_rescrape_workers(1_000) == 4

    def test_env_override_ignored_when_higher_than_budget(self) -> None:
        """A huge override never exceeds the DB-pool-derived budget."""
        with patch.dict("os.environ", {"CRAWLER_RESCRAPE_MAX_WORKERS": "9999"}):
            budget = (
                archive_rescrape.DB_POOL_SIZE
                + archive_rescrape.DB_MAX_OVERFLOW
                - archive_rescrape.API_CONNECTION_RESERVE
            )
            assert archive_rescrape._compute_rescrape_workers(1_000) == budget

    def test_caps_at_num_pages(self) -> None:
        """Two pages never spin up more than two workers, even with a generous budget."""
        with patch.dict("os.environ", {}, clear=False):
            if "CRAWLER_RESCRAPE_MAX_WORKERS" in __import__("os").environ:
                del __import__("os").environ["CRAWLER_RESCRAPE_MAX_WORKERS"]
            assert archive_rescrape._compute_rescrape_workers(2) == 2

    def test_garbage_env_is_ignored(self) -> None:
        """A non-integer override falls back to the budget instead of tanking the job."""
        with patch.dict("os.environ", {"CRAWLER_RESCRAPE_MAX_WORKERS": "not-a-number"}):
            workers = archive_rescrape._compute_rescrape_workers(50)
            assert workers == 50  # min(50, budget=80)


class TestParallelDispatch:
    def test_all_outcomes_aggregated(self) -> None:
        """10 pages: stub returns 6 parsed_ok + 3 parse_failed + 1 ingest_failed."""
        rows = [_mk_row(url=f"https://x.example/p/{i}") for i in range(10)]

        lock = threading.Lock()
        counter = {"n": 0}

        def fake_rescrape(*args: Any, **kwargs: Any) -> tuple[str, Any, Any]:
            del args, kwargs  # signature-matching stub
            with lock:
                counter["n"] += 1
                n = counter["n"]
            if n <= 6:
                return ("parsed_ok", uuid4(), None)
            if n <= 9:
                return ("parse_failed", None, "parser drift")
            return ("ingest_failed", None, "DB constraint")

        with (
            patch.object(archive_rescrape, "SessionLocal", side_effect=_stub_session_factory),
            patch.object(archive_rescrape, "rescrape_crawled_page_from_archive", side_effect=fake_rescrape),
        ):
            result = archive_rescrape.run_rescrape_all_archived_pages(
                _outer_db_with_rows(rows),
                crawler_user=MagicMock(id=uuid4()),
                default_category_id=uuid4(),
                log=MagicMock(),
            )

        assert result["parsed_ok"] == 6
        assert result["parse_failed"] == 3
        assert result["ingest_failed"] == 1
        assert result["failures_total"] == 4
        assert len(result["failures"]) == 4
        assert result["failures_truncated"] is False

    def test_runs_in_parallel(self) -> None:
        """With 8 workers and 8 pages that each sleep 100ms, wall time must be well under 8 * 100ms."""
        rows = [_mk_row(url=f"https://x.example/p/{i}") for i in range(8)]

        def slow_rescrape(*args: Any, **kwargs: Any) -> tuple[str, Any, Any]:
            del args, kwargs  # signature-matching stub
            time.sleep(0.1)
            return ("parsed_ok", uuid4(), None)

        with (
            patch.dict("os.environ", {"CRAWLER_RESCRAPE_MAX_WORKERS": "8"}),
            patch.object(archive_rescrape, "SessionLocal", side_effect=_stub_session_factory),
            patch.object(archive_rescrape, "rescrape_crawled_page_from_archive", side_effect=slow_rescrape),
        ):
            start = time.monotonic()
            result = archive_rescrape.run_rescrape_all_archived_pages(
                _outer_db_with_rows(rows),
                crawler_user=MagicMock(id=uuid4()),
                default_category_id=uuid4(),
                log=MagicMock(),
            )
            elapsed = time.monotonic() - start

        assert result["parsed_ok"] == 8
        # Sequential would take 8 * 0.1s = 0.8s. Parallel with 8 workers should
        # finish close to 0.1s; give it a generous 0.5s cap to avoid CI flakes.
        assert elapsed < 0.5, f"expected parallel execution, took {elapsed:.2f}s (sequential baseline 0.8s)"

    def test_stop_event_short_circuits_pending_workers(self) -> None:
        """Setting stop_event before dispatch skips all work; counts stay zero."""
        rows = [_mk_row(url=f"https://x.example/p/{i}") for i in range(50)]
        stop_event = threading.Event()
        stop_event.set()

        rescrape_mock = MagicMock()

        with (
            patch.object(archive_rescrape, "SessionLocal", side_effect=_stub_session_factory),
            patch.object(archive_rescrape, "rescrape_crawled_page_from_archive", rescrape_mock),
        ):
            result = archive_rescrape.run_rescrape_all_archived_pages(
                _outer_db_with_rows(rows),
                crawler_user=MagicMock(id=uuid4()),
                default_category_id=uuid4(),
                log=MagicMock(),
                stop_event=stop_event,
            )

        # Every worker short-circuited on entry → nothing recorded.
        assert result["parsed_ok"] == 0
        assert result["parse_failed"] == 0
        assert result["ingest_failed"] == 0
        assert result["failures_total"] == 0
        # And the per-page function was never invoked.
        rescrape_mock.assert_not_called()

    def test_empty_page_set_returns_zero_counts(self) -> None:
        """No pages to process → return empty counts without spinning up the pool."""
        with patch.object(archive_rescrape, "rescrape_crawled_page_from_archive") as rescrape_mock:
            result = archive_rescrape.run_rescrape_all_archived_pages(
                _outer_db_with_rows([]),
                crawler_user=MagicMock(id=uuid4()),
                default_category_id=uuid4(),
                log=MagicMock(),
            )

        assert result["parsed_ok"] == 0
        assert result["failures_total"] == 0
        assert result["failures_truncated"] is False
        rescrape_mock.assert_not_called()

    def test_return_shape_matches_email_renderer_contract(self) -> None:
        """Keys consumed by _render_archive_rescrape_result_html must all be present."""
        rows = [_mk_row()]

        with (
            patch.object(archive_rescrape, "SessionLocal", side_effect=_stub_session_factory),
            patch.object(
                archive_rescrape,
                "rescrape_crawled_page_from_archive",
                return_value=("parsed_ok", uuid4(), None),
            ),
        ):
            result = archive_rescrape.run_rescrape_all_archived_pages(
                _outer_db_with_rows(rows),
                crawler_user=MagicMock(id=uuid4()),
                default_category_id=uuid4(),
                log=MagicMock(),
            )

        for key in (
            "parsed_ok",
            "parse_failed",
            "ingest_failed",
            "skipped_no_adapter",
            "skipped_no_html",
            "failures",
            "failures_total",
            "failures_truncated",
        ):
            assert key in result, f"missing key {key!r} — would break email report renderer"

    def test_worker_exception_is_captured_not_fatal(self) -> None:
        """If the stub raises, run_rescrape should catch it and record ingest_failed."""
        rows = [_mk_row(url=f"https://x.example/p/{i}") for i in range(3)]

        def explode(*args: Any, **kwargs: Any) -> tuple[str, Any, Any]:
            del args, kwargs  # signature-matching stub
            raise RuntimeError("synthetic worker crash")

        with (
            patch.object(archive_rescrape, "SessionLocal", side_effect=_stub_session_factory),
            patch.object(archive_rescrape, "rescrape_crawled_page_from_archive", side_effect=explode),
        ):
            result = archive_rescrape.run_rescrape_all_archived_pages(
                _outer_db_with_rows(rows),
                crawler_user=MagicMock(id=uuid4()),
                default_category_id=uuid4(),
                log=MagicMock(),
            )

        assert result["parsed_ok"] == 0
        assert result["ingest_failed"] == 3
        assert result["failures_total"] == 3
        assert all("synthetic worker crash" in (f["error"] or "") for f in result["failures"])
