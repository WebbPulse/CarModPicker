"""WR-04 regression tests — ``init_crawler_service_account`` cold-start log
formatting must use ``%s`` for the UUID ``id`` field.

Background: an earlier revision of ``app/core/init_service_accounts.py`` passed
``user.id`` (a UUID) through ``%d`` formatters at two log sites. On the very
first cold start (before the service-account row exists), this raised
``TypeError: %d format: a number is required, not UUID`` and crashed the app's
``lifespan`` hook, preventing the server from coming up on fresh
environments. The ``%d`` → ``%s`` fix landed in Phase 4's code-review cycle,
but no regression test pinned the fix in place. This file closes that hole.

Each test calls ``init_crawler_service_account(db_session)`` on an
in-memory SQLite DB. ``%d`` + UUID would raise ``TypeError`` at the log-record
``getMessage()`` render site; ``%s`` + UUID renders the canonical UUID string
and the tests pass. See Test 4 for the direct TypeError guard via
``record.getMessage()``.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.user import User
from app.core.config import settings
from app.core.init_service_accounts import init_crawler_service_account


def test_create_fresh_service_account_logs_with_s_format(db_session: Session, caplog) -> None:
    """WR-04 pin — fresh-DB path renders ``id=%s`` without TypeError.

    Pre-fix, this call would raise ``TypeError`` at the first
    ``logger.info("... id=%d", user.id)`` because ``user.id`` is a UUID.
    """
    caplog.set_level(logging.INFO, logger="app.core.init_service_accounts")

    # Fresh DB: no user with this username yet. db_session's outer transaction
    # rolls back between tests, so no cross-test pollution.
    assert (
        db_session.scalars(select(User).where(User.username == settings.CRAWLER_SERVICE_ACCOUNT_USERNAME)).first()
        is None
    )

    # Must not raise — ``%d`` + UUID would have raised ``TypeError`` here.
    init_crawler_service_account(db_session)

    user = db_session.scalars(select(User).where(User.username == settings.CRAWLER_SERVICE_ACCOUNT_USERNAME)).one()
    assert user.is_service_account is True
    assert user.email_verified is True
    assert user.disabled is False

    # Direct WR-04 pin: the "Created crawler service account" log line must
    # have rendered. ``getMessage()`` performs the ``%s`` substitution — if the
    # format string ever regresses to ``%d``, this call would raise TypeError.
    create_logs = [r for r in caplog.records if "Created crawler service account" in r.getMessage()]
    assert len(create_logs) == 1
    assert f"id={user.id}" in create_logs[0].getMessage()
    assert f"username={settings.CRAWLER_SERVICE_ACCOUNT_USERNAME}" in create_logs[0].getMessage()


def test_existing_non_service_user_is_adopted(db_session: Session, caplog) -> None:
    """Adoption path — a pre-existing username-match user is flipped to a
    service account. The "Marked existing user" log line must also render
    without TypeError (same ``%s`` fix, second log site at line 57).
    """
    caplog.set_level(logging.INFO, logger="app.core.init_service_accounts")

    existing = User(
        username=settings.CRAWLER_SERVICE_ACCOUNT_USERNAME,
        email=f"{settings.CRAWLER_SERVICE_ACCOUNT_USERNAME}@preexist.local",
        hashed_password="x",
        email_verified=True,
        disabled=False,
        is_service_account=False,
    )
    db_session.add(existing)
    db_session.commit()
    original_id = existing.id

    init_crawler_service_account(db_session)

    users = db_session.scalars(select(User).where(User.username == settings.CRAWLER_SERVICE_ACCOUNT_USERNAME)).all()
    assert len(users) == 1
    assert users[0].is_service_account is True
    # Sanity: the same row was flipped, not replaced.
    assert users[0].id == original_id

    adopt_logs = [r for r in caplog.records if "Marked existing user as service account" in r.getMessage()]
    assert len(adopt_logs) == 1
    assert f"id={users[0].id}" in adopt_logs[0].getMessage()


def test_already_service_account_is_idempotent(db_session: Session, caplog) -> None:
    """Idempotent path — second call on an existing service account is a no-op.
    The DEBUG-level log at line 59 also uses ``%s`` and must render without
    TypeError.
    """
    caplog.set_level(logging.DEBUG, logger="app.core.init_service_accounts")

    init_crawler_service_account(db_session)
    init_crawler_service_account(db_session)  # second call: no-op path

    users = db_session.scalars(select(User).where(User.username == settings.CRAWLER_SERVICE_ACCOUNT_USERNAME)).all()
    assert len(users) == 1
    assert users[0].is_service_account is True

    # The no-op path emits a DEBUG "already exists" log on the second call.
    already_logs = [r for r in caplog.records if "Crawler service account already exists" in r.getMessage()]
    assert len(already_logs) >= 1
    assert f"id={users[0].id}" in already_logs[0].getMessage()


def test_log_formatting_accepts_uuid_id_field(db_session: Session, caplog) -> None:
    """Explicit TypeError guard — render EVERY captured log record's message.

    ``record.getMessage()`` is where ``%``-style formatters execute. ``%d`` with
    a UUID would raise ``TypeError`` at this call site. This test catches a
    regression to ``%d`` even if the record was emitted but never read.
    """
    caplog.set_level(logging.DEBUG, logger="app.core.init_service_accounts")
    init_crawler_service_account(db_session)

    # Filter to only our logger's records so we don't accidentally probe
    # unrelated log lines emitted elsewhere in the stack.
    our_records = [r for r in caplog.records if r.name == "app.core.init_service_accounts"]
    assert our_records, "Expected at least one log record from init_service_accounts"

    for record in our_records:
        rendered = record.getMessage()  # raises TypeError if %d + UUID
        assert "id=" in rendered
        assert "username=" in rendered
