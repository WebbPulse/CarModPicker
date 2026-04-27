"""DATA-07 regression: pool_recycle tightened to 1800 (30 min); Phase 3 D-14
crawler formula literals preserved.

See .planning/phases/04-db-parts-hardening/04-CONTEXT.md D-18, D-20, D-22 for
the rationale. The pool_size envelope (25 + 75 - 20 = 80) is consumed by the
crawler ThreadPoolExecutor sizing formula; regressing it would break the
crawler subsystem.
"""

from __future__ import annotations

from app.db.session import API_CONNECTION_RESERVE, DB_MAX_OVERFLOW, DB_POOL_SIZE, engine


def test_pool_recycle_is_1800() -> None:
    """Phase 4 D-20: pool_recycle must be 1800 (30 min)."""
    # Private attribute deliberately — SQLAlchemy's QueuePool stores the
    # recycle interval on ._recycle; there is no stable public accessor.
    assert engine.pool._recycle == 1800, f"pool_recycle must be 1800 per D-20; got {engine.pool._recycle}"


def test_pool_size_envelope_preserved() -> None:
    """Phase 3 D-14 crawler worker formula depends on these literals
    (DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE = 80)."""
    assert DB_POOL_SIZE == 25, f"DB_POOL_SIZE must stay 25 per D-18/D-22; got {DB_POOL_SIZE}"
    assert DB_MAX_OVERFLOW == 75, f"DB_MAX_OVERFLOW must stay 75 per D-18; got {DB_MAX_OVERFLOW}"
    assert API_CONNECTION_RESERVE == 20, f"API_CONNECTION_RESERVE must stay 20 per D-22; got {API_CONNECTION_RESERVE}"
