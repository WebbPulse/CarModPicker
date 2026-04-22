"""DATA-02: self-test for the query_counter fixture.

Pins the fixture's contract so downstream regression tests (e.g.
test_build_log_n_plus_one.py) can rely on it."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.user import User as DBUser


def test_counter_records_selects(db_session: Session, query_counter) -> None:
    """N SELECTs inside the block yield counter.count == N."""
    with query_counter() as counter:
        db_session.scalars(select(DBUser)).all()
        db_session.scalars(select(DBUser)).all()
        db_session.scalars(select(DBUser)).all()
    assert counter.count == 3, f"Expected 3 SELECTs, got {counter.count}: {counter.statements}"


def test_counter_resets_between_blocks(db_session: Session, query_counter) -> None:
    """Entering the context a second time starts at 0."""
    with query_counter() as c1:
        db_session.scalars(select(DBUser)).all()
    assert c1.count == 1

    with query_counter() as c2:
        pass  # no queries
    assert c2.count == 0, f"Second block should start fresh; got {c2.count}"


def test_non_select_statements_not_counted(db_session: Session, query_counter) -> None:
    """At least one SELECT is counted; every counted statement is a SELECT.

    WARN 6 revised: the original `counter.count == 1` was too tight — SAVEPOINT
    fixtures or implicit pre-flush SELECTs can bump the count without violating
    the SELECT-only contract. We instead assert the SELECT-only invariant.
    """
    with query_counter() as counter:
        # Force some non-SELECT activity (SAVEPOINT release triggered by the db_session fixture).
        db_session.flush()
        db_session.scalars(select(DBUser)).all()
    assert counter.count >= 1, "Expected at least 1 SELECT to be counted"
    assert all("SELECT" in s.upper() for s in counter.statements), (
        f"Non-SELECT statement leaked into counter: {counter.statements}"
    )


def test_listener_removed_after_exit(db_session: Session, query_counter) -> None:
    """After exit, subsequent SELECTs do not increment the counter (Pitfall 3 defense)."""
    with query_counter() as counter:
        db_session.scalars(select(DBUser)).all()
    saved = counter.count
    # Now emit more SELECTs OUTSIDE the context — counter must not move.
    db_session.scalars(select(DBUser)).all()
    db_session.scalars(select(DBUser)).all()
    assert counter.count == saved, (
        f"Counter moved after context exit ({saved} -> {counter.count}); event.remove failed."
    )
