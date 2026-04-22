"""CRAWL-04 unit test: pybreaker registry isolation + fail_max=3 / reset_timeout=120 semantics."""

import pybreaker
import pytest

from app.crawlers import runner
from app.crawlers.runner import get_breaker


@pytest.fixture(autouse=True)
def _clear_breakers():
    """Prevent cross-test pollution of the process-global _BREAKERS registry under pytest-xdist."""
    runner._BREAKERS.clear()
    yield
    runner._BREAKERS.clear()


def test_same_adapter_name_returns_same_breaker() -> None:
    """Registry identity: calling get_breaker twice with the same slug returns the identical object."""
    first = get_breaker("zephyr")
    second = get_breaker("zephyr")
    assert first is second
    assert isinstance(first, pybreaker.CircuitBreaker)


def test_different_adapter_names_return_different_breakers() -> None:
    """Per-adapter isolation: breakers for distinct slugs are distinct instances (D-08)."""
    alpha = get_breaker("alpha")
    beta = get_breaker("beta")
    assert alpha is not beta
    assert isinstance(alpha, pybreaker.CircuitBreaker)
    assert isinstance(beta, pybreaker.CircuitBreaker)


def test_breaker_config_matches_req() -> None:
    """Configuration from D-09: fail_max=3, reset_timeout=120."""
    breaker = get_breaker("config_probe")
    assert breaker.fail_max == 3
    assert breaker.reset_timeout == 120
