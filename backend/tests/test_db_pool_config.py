"""DATA-07 regression: pool_recycle tightened to 1800 (30 min); Phase 3 D-14
crawler formula literals preserved.

See .planning/phases/04-db-parts-hardening/04-CONTEXT.md D-18, D-20, D-22 for
the rationale. The pool_size envelope (25 + 25 - 20 = 30) is consumed by the
crawler ThreadPoolExecutor sizing formula; regressing it would break the
crawler subsystem.

Local dev (``APP_ENVIRONMENT=development``) intentionally lifts the envelope
to saturate developer hardware during archive rescrapes; the prod envelope
asserts below run with ``APP_ENVIRONMENT=staging`` to verify the non-dev
branch.
"""

from __future__ import annotations

import importlib

import pytest

from app.db.session import engine


def test_pool_recycle_is_1800() -> None:
    """Phase 4 D-20: pool_recycle must be 1800 (30 min)."""
    # Private attribute deliberately — SQLAlchemy's QueuePool stores the
    # recycle interval on ._recycle; there is no stable public accessor.
    assert engine.pool._recycle == 1800, f"pool_recycle must be 1800 per D-20; got {engine.pool._recycle}"


def test_pool_size_envelope_preserved_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 3 D-14 crawler worker formula depends on these literals when
    ``APP_ENVIRONMENT`` is not ``development``."""
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    # get_settings() is @lru_cache'd; bust it so the reload sees the env change.
    from app.core import config as config_mod

    config_mod.get_settings.cache_clear()
    session_mod = importlib.reload(importlib.import_module("app.db.session"))
    try:
        assert session_mod.DB_POOL_SIZE == 25, f"DB_POOL_SIZE must stay 25 per D-18/D-22; got {session_mod.DB_POOL_SIZE}"
        assert session_mod.DB_MAX_OVERFLOW == 25, f"DB_MAX_OVERFLOW must stay 25 per D-18; got {session_mod.DB_MAX_OVERFLOW}"
        assert (
            session_mod.API_CONNECTION_RESERVE == 20
        ), f"API_CONNECTION_RESERVE must stay 20 per D-22; got {session_mod.API_CONNECTION_RESERVE}"
    finally:
        # Restore the original module state for downstream tests in the same worker.
        config_mod.get_settings.cache_clear()
        importlib.reload(session_mod)
