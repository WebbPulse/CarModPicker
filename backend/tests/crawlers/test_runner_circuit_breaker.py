"""DEPRECATED — replaced by test_runner_breaker.py + test_circuit_breaker.py in Phase 03 Plan 02.

The old ``RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD`` counter block was deleted
from ``app.crawlers.runner`` per CRAWL-04 / D-07 "delete before add". The
behaviors it characterized are now covered by ``test_runner_breaker.py``
(integration) and ``test_circuit_breaker.py`` (unit).

This file is intentionally empty — the plan specified a ``git rm`` but
the execution sandbox blocked the filesystem deletion, so the file is
preserved as a stub rather than an orphan with broken imports.
"""

# IN-09: mark the entire module as skipped so ``pytest`` reports a single
# deprecation marker (instead of silently "0 tests collected") and future
# readers running ``pytest tests/crawlers/test_runner_circuit_breaker.py``
# directly see an explanation pointing to the replacement modules.
import pytest

pytestmark = pytest.mark.skip(
    reason="Deprecated — see test_runner_breaker.py + test_circuit_breaker.py"
)
