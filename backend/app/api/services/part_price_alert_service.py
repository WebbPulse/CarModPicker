"""
Service for per-user price-drop alert subscriptions.

Module-level functions (no class) to mirror part_listing_service.py style.
T02 surface: subscribe upsert, list-mine, deactivate. T03 will extend with
the evaluation entry point invoked by create_or_update_listing_and_price.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.part_price_alert import PartPriceAlert as DBPartPriceAlert


def create_or_update_alert(
    db: Session,
    user_id: UUID,
    part_id: UUID,
    threshold_cents: int,
) -> DBPartPriceAlert:
    """Subscribe-or-update upsert keyed on (user_id, part_id).

    Behavior:
    - existing row, active=True  → update threshold_cents
    - existing row, active=False → reactivate (active=True) + update threshold_cents
    - no existing row            → insert a new active alert

    Idempotent for callers: re-subscribing the same user+part never raises a
    UNIQUE-violation; the row is mutated in-place.
    """
    existing: Optional[DBPartPriceAlert] = db.scalars(
        select(DBPartPriceAlert).where(
            DBPartPriceAlert.user_id == user_id,
            DBPartPriceAlert.part_id == part_id,
        )
    ).first()

    if existing is not None:
        existing.threshold_cents = threshold_cents
        if not existing.active:
            existing.active = True
        db.add(existing)
        db.flush()
        db.refresh(existing)
        return existing

    alert = DBPartPriceAlert(
        user_id=user_id,
        part_id=part_id,
        threshold_cents=threshold_cents,
        active=True,
    )
    db.add(alert)
    db.flush()
    db.refresh(alert)
    return alert


def list_active_alerts_for_user(db: Session, user_id: UUID) -> list[DBPartPriceAlert]:
    """Return every active alert (active=True) belonging to the user, newest-first."""
    return list(
        db.scalars(
            select(DBPartPriceAlert)
            .where(
                DBPartPriceAlert.user_id == user_id,
                DBPartPriceAlert.active.is_(True),
            )
            .order_by(DBPartPriceAlert.created_at.desc())
        ).all()
    )


def get_alert_for_owner(
    db: Session, alert_id: UUID, user_id: UUID
) -> Optional[DBPartPriceAlert]:
    """Return the alert if it exists AND belongs to user_id; None otherwise.

    Used by PATCH/DELETE endpoints to enforce per-user ownership without
    leaking existence (404 on both not-found and wrong-owner).
    """
    return db.scalars(
        select(DBPartPriceAlert).where(
            DBPartPriceAlert.id == alert_id,
            DBPartPriceAlert.user_id == user_id,
        )
    ).first()


def deactivate_alert(db: Session, alert_id: UUID, user_id: UUID) -> bool:
    """Soft-delete: set active=False on the alert if it belongs to user_id and is active.

    Returns True if a row was found-active-and-owned and deactivated; False if the
    alert doesn't exist, belongs to another user, or is already inactive. Endpoints
    map False → 404 (uniform 'not currently active for this user' meaning).
    """
    alert = db.scalars(
        select(DBPartPriceAlert).where(
            DBPartPriceAlert.id == alert_id,
            DBPartPriceAlert.user_id == user_id,
            DBPartPriceAlert.active.is_(True),
        )
    ).first()
    if alert is None:
        return False
    alert.active = False
    db.add(alert)
    db.flush()
    return True
