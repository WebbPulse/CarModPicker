"""DATA-06 regression: zero db.query() / session.query() / self.db.query() call sites.

Phase 4 D-09 sweep — all 301+ legacy calls in ``backend/app/`` rewritten to
``db.scalars(select(...))`` / ``db.scalar(select(func.count()).select_from(...))``.
This test is the permanent CI gate that prevents regression in application code.

Scope (Phase 4 code-review WR-01): this guard is intentionally scoped to
``backend/app/`` — the runtime/request path. It deliberately does NOT scan:

- ``backend/tests/`` — test helpers (conftest.py fixtures, test utilities) may
  continue to use the 1.x Query API for terse setup/teardown. The Query API is
  not removed in SQLAlchemy 2.x, only deprecated for new code. Rewriting these
  sites carries regression risk that outweighs the invariant value (tests
  don't go through the request path). If tests ever start asserting query-count
  contracts via ``query_counter``, those specific files should be migrated as
  needed.
- ``backend/scripts/`` — one-off maintenance/migration scripts run out-of-band
  against a direct DB connection. Scoped exempt for the same reason as tests.

Companion tests: test_pydantic_v1_regression.py (QUAL-02), test_logger_migration_regression.py (QUAL-07).
"""

from __future__ import annotations

import re
from pathlib import Path

# Scoped to ``backend/app/`` only — see module docstring (WR-01) for the rationale
# behind excluding ``tests/`` and ``scripts/``.
APP_DIR = Path(__file__).resolve().parent.parent / "app"

# Conservative pattern — matches .query( when preceded by db / session / self.db / self.session.
# Catches all SQLAlchemy Session.query invocations without false-positives against
# e.g. Pydantic __pydantic_fields__ or urllib.parse helpers (neither present in tree).
_PATTERN = re.compile(r"\b(?:db|session|self\.db|self\.session)\.query\(")

# Legitimate non-SQLAlchemy .query(...) callers go here. Empty per D-09 —
# no requests / urllib.parse usages in tree.
ALLOW_LIST: set[Path] = set()


def test_no_session_query_calls_remain() -> None:
    offenders: list[tuple[str, int, str]] = []
    for pyfile in APP_DIR.rglob("*.py"):
        if pyfile in ALLOW_LIST:
            continue
        rel = str(pyfile.relative_to(APP_DIR))
        for lineno, line in enumerate(pyfile.read_text(encoding="utf-8").splitlines(), start=1):
            # Skip comment-only lines — tolerates inline comments within code lines.
            stripped = line.split("#", 1)[0]
            if _PATTERN.search(stripped):
                offenders.append((rel, lineno, line.strip()))
    assert not offenders, (
        "session.query() / db.query() / self.db.query() calls detected — "
        "use db.scalars(select(...)) or db.scalar(select(func.count()).select_from(...)) instead.\n"
        f"Total offenders: {len(offenders)}\n"
        + "\n".join(f"  {f}:{ln} -> {code}" for f, ln, code in offenders[:20])
        + (f"\n  ... and {len(offenders) - 20} more" if len(offenders) > 20 else "")
    )
