"""CRAWL-05 unit test: _compute_adapter_workers worker-budget formula + env override.

Pinned invariants (DISC-03):
  - Env var is CRAWLER_MAX_ADAPTER_WORKERS (NOT CRAWLER_MAX_WORKERS).
  - Default budget = DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE.
  - Invalid env values are ignored (warning logged, no exception).
"""

import pytest

from app.crawlers.runner import _compute_adapter_workers
from app.db.session import API_CONNECTION_RESERVE, DB_MAX_OVERFLOW, DB_POOL_SIZE

_BUDGET = DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE


def test_default_is_min_of_budget_and_num_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without env override: min(num_adapters, budget)."""
    monkeypatch.delenv("CRAWLER_MAX_ADAPTER_WORKERS", raising=False)
    # Small num_adapters capped by itself.
    assert _compute_adapter_workers(3) == 3
    # Large num_adapters capped by budget.
    assert _compute_adapter_workers(200) == _BUDGET


def test_env_override_caps_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    """CRAWLER_MAX_ADAPTER_WORKERS=5 caps to 5 regardless of budget."""
    monkeypatch.setenv("CRAWLER_MAX_ADAPTER_WORKERS", "5")
    assert _compute_adapter_workers(200) == 5


def test_invalid_env_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-integer CRAWLER_MAX_ADAPTER_WORKERS is ignored, falls back to default budget formula."""
    monkeypatch.setenv("CRAWLER_MAX_ADAPTER_WORKERS", "not-an-int")
    # num_adapters=3 → min(3, budget) = 3
    assert _compute_adapter_workers(3) == 3
