"""Model + Pydantic-schema unit tests for PartPriceAlert (M002 / S07 / T01).

The model is per-user-per-part subscription to a price threshold. Schema-level
constraints under test:
  - threshold_cents must be >= 0 (Pydantic Field(ge=0))
  - (user_id, part_id) is UNIQUE — re-subscribing must fail at the DB layer when
    a row already exists for that pair
  - default values: active=True, last_fired_at=None, created_at/updated_at populated
  - Pydantic Read schema round-trips an ORM instance via from_attributes=True

NOTE: SQLite (the test backend) does NOT enforce CHECK constraints by default
without `PRAGMA foreign_keys = ON` and table-level enforcement. The CHECK is
exercised by Pydantic at the API boundary (ge=0). This test file focuses on
the Python-level behaviors that survive the SQLite test substrate.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.models.category import Category
from app.api.models.part import Part
from app.api.models.part_price_alert import PartPriceAlert
from app.api.models.user import User
from app.api.schemas.part_price_alert import (
    PartPriceAlertCreate,
    PartPriceAlertRead,
    PartPriceAlertUpdate,
)
from tests.conftest import get_default_category_id


def _make_part(db: Session, user: User, name: str = "Test Part") -> Part:
    category_id = get_default_category_id(db)
    part = Part(
        name=name,
        category_id=category_id,
        user_id=user.id,
        is_universal=True,
    )
    db.add(part)
    db.commit()
    db.refresh(part)
    return part


# ---------------------------------------------------------------------------
# ORM-level tests
# ---------------------------------------------------------------------------


def test_part_price_alert_defaults_active_and_no_last_fired(
    db_session: Session, test_user: User
) -> None:
    """A freshly created alert defaults to active=True with last_fired_at=None
    and populated timestamps."""
    part = _make_part(db_session, test_user)

    alert = PartPriceAlert(
        user_id=test_user.id,
        part_id=part.id,
        threshold_cents=10_000,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    assert isinstance(alert.id, uuid.UUID)
    assert alert.active is True
    assert alert.last_fired_at is None
    assert alert.threshold_cents == 10_000
    assert alert.created_at is not None
    assert alert.updated_at is not None


def test_part_price_alert_unique_user_part(
    db_session: Session, test_user: User
) -> None:
    """A second alert for the same (user_id, part_id) pair must fail with
    IntegrityError — re-subscribing is supposed to update, not insert."""
    part = _make_part(db_session, test_user)

    first = PartPriceAlert(
        user_id=test_user.id,
        part_id=part.id,
        threshold_cents=5_000,
    )
    db_session.add(first)
    db_session.commit()

    duplicate = PartPriceAlert(
        user_id=test_user.id,
        part_id=part.id,
        threshold_cents=4_000,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_part_price_alert_same_user_different_parts_allowed(
    db_session: Session, test_user: User
) -> None:
    """The unique constraint is on (user_id, part_id) — same user can have
    alerts on multiple distinct parts."""
    part_a = _make_part(db_session, test_user, name="Part A")
    part_b = _make_part(db_session, test_user, name="Part B")

    alert_a = PartPriceAlert(user_id=test_user.id, part_id=part_a.id, threshold_cents=1)
    alert_b = PartPriceAlert(user_id=test_user.id, part_id=part_b.id, threshold_cents=2)
    db_session.add_all([alert_a, alert_b])
    db_session.commit()

    assert alert_a.id != alert_b.id


def test_part_price_alert_different_users_same_part_allowed(
    db_session: Session, test_user: User
) -> None:
    """The unique constraint is on (user_id, part_id) — two different users
    can each subscribe to the same part."""
    other = User(
        username="other_alert_user",
        email="other_alert_user@example.com",
        hashed_password="x",
        email_verified=True,
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    part = _make_part(db_session, test_user)

    alert_a = PartPriceAlert(user_id=test_user.id, part_id=part.id, threshold_cents=100)
    alert_b = PartPriceAlert(user_id=other.id, part_id=part.id, threshold_cents=200)
    db_session.add_all([alert_a, alert_b])
    db_session.commit()

    assert alert_a.id != alert_b.id


def test_part_price_alert_last_fired_at_writable(
    db_session: Session, test_user: User
) -> None:
    """last_fired_at can be set explicitly (mirrors the cooldown bookkeeping
    the evaluator service does in T03)."""
    part = _make_part(db_session, test_user)
    fired = datetime.now(UTC) - timedelta(hours=2)

    alert = PartPriceAlert(
        user_id=test_user.id,
        part_id=part.id,
        threshold_cents=1_000,
        last_fired_at=fired,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    assert alert.last_fired_at is not None


# ---------------------------------------------------------------------------
# Pydantic-schema tests
# ---------------------------------------------------------------------------


def test_create_schema_rejects_negative_threshold() -> None:
    """Field(ge=0) on threshold_cents — negative values fail before any DB write."""
    part_id: UUID = uuid.uuid4()
    with pytest.raises(ValidationError):
        PartPriceAlertCreate(part_id=part_id, threshold_cents=-1)


def test_create_schema_accepts_zero_threshold() -> None:
    """Threshold of exactly 0 cents is allowed — semantically 'notify on any price'."""
    part_id: UUID = uuid.uuid4()
    payload = PartPriceAlertCreate(part_id=part_id, threshold_cents=0)
    assert payload.threshold_cents == 0
    assert payload.part_id == part_id


def test_update_schema_partial_fields() -> None:
    """PartPriceAlertUpdate must allow either threshold_cents OR active to be
    omitted — both are Optional."""
    upd_threshold = PartPriceAlertUpdate(threshold_cents=200)
    assert upd_threshold.threshold_cents == 200
    assert upd_threshold.active is None

    upd_active = PartPriceAlertUpdate(active=False)
    assert upd_active.threshold_cents is None
    assert upd_active.active is False

    upd_empty = PartPriceAlertUpdate()
    assert upd_empty.threshold_cents is None
    assert upd_empty.active is None


def test_update_schema_rejects_negative_threshold() -> None:
    """The update schema must apply the same ge=0 invariant to threshold_cents."""
    with pytest.raises(ValidationError):
        PartPriceAlertUpdate(threshold_cents=-5)


def test_read_schema_round_trips_orm_instance(
    db_session: Session, test_user: User
) -> None:
    """PartPriceAlertRead must serialize an ORM instance correctly via
    from_attributes=True — proves the field set matches the model."""
    part = _make_part(db_session, test_user)
    alert = PartPriceAlert(
        user_id=test_user.id,
        part_id=part.id,
        threshold_cents=12_345,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    read = PartPriceAlertRead.model_validate(alert)
    assert read.id == alert.id
    assert read.user_id == test_user.id
    assert read.part_id == part.id
    assert read.threshold_cents == 12_345
    assert read.active is True
    assert read.last_fired_at is None
    assert read.created_at is not None
    assert read.updated_at is not None
