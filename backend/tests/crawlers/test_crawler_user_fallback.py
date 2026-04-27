"""WR-03 regression — ``_get_crawler_user`` CRAWLER_USER_ID fallback parses UUIDs.

Background: an earlier revision of ``app/crawlers/runner.py::_get_crawler_user``
cast ``os.environ['CRAWLER_USER_ID']`` through ``int(raw)`` — vestigial from
the pre-UUID schema. After ``User.id`` became UUID, that cast raised
``ValueError("invalid literal for int() with base 10")`` on every legitimate
UUID env-var value, producing a misleading error message for operators running
the crawler CLI. The ``int(raw)`` → ``UUID(raw)`` fix landed in Phase 4's
code-review cycle. This file pins the fix so any future regression to
``int(raw)`` fails CI.

Coverage:
  1. valid UUID string → user is returned
  2. invalid (non-UUID) string → ``CrawlerConfigError("must be a valid UUID")``
  3. valid UUID that does not match any user → ``CrawlerConfigError("no user found")``
  4. valid UUID of a disabled user → ``CrawlerConfigError("user is disabled")``
  5. service account present AND env var set → service account wins
     (precedence guarantee; otherwise operators could override the SA flow
     via a stray env var)
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.user import User
from app.crawlers.runner import CrawlerConfigError, _get_crawler_user


def _clear_service_accounts(db_session: Session) -> None:
    """Ensure no service-account row exists so we exercise the env-var fallback.

    The SQLite in-memory DB is per-test-transaction (conftest's db_session wraps
    a SAVEPOINT), but because the session-scoped ``engine`` fixture creates
    tables once per xdist worker, prior tests in the same worker may have
    committed a service-account row via ``init_crawler_service_account``. We
    delete defensively.
    """
    for u in db_session.scalars(select(User).where(User.is_service_account.is_(True))).all():
        db_session.delete(u)
    db_session.commit()


def _make_user(
    db_session: Session,
    username_suffix: str,
    *,
    is_service: bool = False,
    disabled: bool = False,
) -> User:
    """Build a minimal User row. Uses uuid-suffixed username/email so that
    parallel workers cannot collide on username UNIQUE across this file.
    """
    unique = f"{username_suffix}-{uuid.uuid4().hex[:8]}"
    user = User(
        username=f"crawler-fallback-{unique}",
        email=f"crawler-fallback-{unique}@test.local",
        hashed_password="x",
        email_verified=True,
        disabled=disabled,
        is_service_account=is_service,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_env_fallback_accepts_uuid_string(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """WR-03 pin — a valid UUID string in CRAWLER_USER_ID resolves to a user.

    Pre-fix: ``int(raw)`` would have raised ValueError here, masked as a
    CrawlerConfigError with a misleading "must be an integer" message.
    """
    _clear_service_accounts(db_session)
    target = _make_user(db_session, "valid")
    monkeypatch.setenv("CRAWLER_USER_ID", str(target.id))

    result = _get_crawler_user(db_session)

    assert result.id == target.id


def test_env_fallback_rejects_non_uuid(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative path — a non-UUID string raises CrawlerConfigError with the
    canonical "must be a valid UUID" message.
    """
    _clear_service_accounts(db_session)
    monkeypatch.setenv("CRAWLER_USER_ID", "not-a-uuid")

    with pytest.raises(CrawlerConfigError, match="must be a valid UUID"):
        _get_crawler_user(db_session)


def test_env_fallback_raises_when_user_missing(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative path — valid UUID format but no matching user row raises
    ``CrawlerConfigError`` with "no user found".
    """
    _clear_service_accounts(db_session)
    unknown_uuid = str(uuid.uuid4())
    monkeypatch.setenv("CRAWLER_USER_ID", unknown_uuid)

    with pytest.raises(CrawlerConfigError, match="no user found"):
        _get_crawler_user(db_session)


def test_env_fallback_raises_when_user_disabled(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative path — valid UUID resolving to a disabled user raises
    ``CrawlerConfigError`` with "user is disabled".
    """
    _clear_service_accounts(db_session)
    target = _make_user(db_session, "disabled", disabled=True)
    monkeypatch.setenv("CRAWLER_USER_ID", str(target.id))

    with pytest.raises(CrawlerConfigError, match="user is disabled"):
        _get_crawler_user(db_session)


def test_service_account_takes_precedence(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Precedence guarantee — a present service account wins over the env-var
    fallback. This protects operators from accidentally redirecting crawler
    ingestion to a stray user via a leftover ``CRAWLER_USER_ID`` env var.
    """
    _clear_service_accounts(db_session)
    sa = _make_user(db_session, "svc", is_service=True)
    other = _make_user(db_session, "other")
    monkeypatch.setenv("CRAWLER_USER_ID", str(other.id))

    result = _get_crawler_user(db_session)

    assert result.id == sa.id
    assert result.is_service_account is True
