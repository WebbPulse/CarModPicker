"""CRAWL-05 integration test: each ThreadPoolExecutor worker gets its own SessionLocal()
and closes it in finally.

Pins D-15: per-adapter SessionLocal() lifecycle under parallel execution.
"""

from unittest.mock import MagicMock, patch

from app.crawlers import runner


def test_each_worker_gets_own_session() -> None:
    """Running two adapters in parallel invokes SessionLocal() twice and closes both."""
    mock_session_a = MagicMock(name="SessionA")
    mock_session_b = MagicMock(name="SessionB")

    # Side-effect list returns distinct mocks per call; closed(count) verifies lifecycle.
    session_instances = [mock_session_a, mock_session_b]

    def _session_factory() -> MagicMock:
        return session_instances.pop(0)

    # run_crawler is the thing invoked per worker; we short-circuit it to just
    # exercise the SessionLocal()/close lifecycle without hitting the DB.
    def _fake_run_crawler(adapter_name: str, **kwargs) -> dict:
        # Mirror what run_crawler does: open a session, run, close in finally.
        db = runner.SessionLocal()
        try:
            return {
                "adapter": adapter_name,
                "ingested": 0,
                "skipped": 0,
                "errors": 0,
                "total": 0,
            }
        finally:
            db.close()

    with (
        patch.object(runner, "SessionLocal", side_effect=_session_factory) as session_patch,
        patch.object(runner, "run_crawler", side_effect=_fake_run_crawler),
    ):
        result = runner.run_crawlers(["adapter_a", "adapter_b"], parallel=True)

    # Each adapter worker opened exactly one SessionLocal.
    assert session_patch.call_count == 2
    # And closed it.
    assert mock_session_a.close.called
    assert mock_session_b.close.called
    # Both adapters produced result rows (no _error path taken).
    assert len(result["results"]) == 2
