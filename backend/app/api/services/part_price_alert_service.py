"""
Service for per-user price-drop alert subscriptions.

Module-level functions (no class) to mirror part_listing_service.py style.
T02 surface: subscribe upsert, list-mine, deactivate.
T03 surface: evaluate_alerts_for_listing — invoked at the end of
create_or_update_listing_and_price to fire emails when an observation breaches
an active alert's threshold (24h cooldown, exception-safe per-alert iteration,
SES failure leaves last_fired_at unchanged so retries are idempotent).
"""

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.part import Part as DBPart
from app.api.models.part_price_alert import PartPriceAlert as DBPartPriceAlert
from app.api.models.retailer import Retailer as DBRetailer
from app.api.models.user import User as DBUser

logger = logging.getLogger(__name__)

# Cooldown window between consecutive fires for the same alert. Prevents an alert
# from spamming the user when several observations land below threshold in rapid
# succession (e.g. a crawler revisiting a listing every few hours).
ALERT_COOLDOWN = timedelta(hours=24)


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


def get_alert_for_owner(db: Session, alert_id: UUID, user_id: UUID) -> Optional[DBPartPriceAlert]:
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


def _ensure_aware(ts: datetime) -> datetime:
    """Treat naive datetimes as UTC — observation timestamps from the
    crawler/test paths sometimes come in naive."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts


def evaluate_alerts_for_listing(
    db: Session,
    part_id: UUID,
    retailer_id: UUID,
    price_cents: int,
    observed_at: datetime,
) -> None:
    """Evaluate every active alert on `part_id` against this observation and
    fire emails for those whose threshold is breached.

    Contract:
    - Only active alerts are considered (`active=True`).
    - Threshold semantics: ``price_cents <= threshold_cents`` fires.
    - 24h cooldown: an alert that fired within ``ALERT_COOLDOWN`` of ``observed_at``
      is suppressed (logged ``verdict=suppressed_cooldown``) without touching
      ``last_fired_at`` so the user-facing window is honest.
    - Exception-safe per-alert iteration: a bad row (raises during email send,
      template build, or DB update) is logged at WARNING with ``alert_id`` and
      iteration continues. One bad alert MUST NOT poison the price-write
      transaction or block other alerts on the same part from firing.
    - SES failure (``send_price_drop_alert_email`` returns False) is treated as
      non-firing — ``last_fired_at`` stays unchanged so the next observation
      retries. Email-success path sets ``last_fired_at = observed_at`` and
      flushes (the outer transaction owns commit).
    - Logging: one ``price_alert_evaluated`` INFO log per evaluated alert with
      verdict ∈ {fired, suppressed_cooldown, skip_above_threshold}, and one
      ``price_alert_email_sent`` INFO log per attempted send (success or False).
      Email addresses and unsubscribe tokens are NEVER logged — alert_id +
      user_id (UUID) only.
    """
    # Local import — avoids a circular import with app.core.email at module
    # load (email.py is the leaf side; it does not import services). Keeping
    # the import lazy also makes monkeypatching trivial in tests:
    # `monkeypatch.setattr("app.core.email.send_price_drop_alert_email", ...)`.
    from app.core import email as email_module

    observed_at = _ensure_aware(observed_at)

    candidate_alerts = list(
        db.scalars(
            select(DBPartPriceAlert).where(
                DBPartPriceAlert.part_id == part_id,
                DBPartPriceAlert.active.is_(True),
                DBPartPriceAlert.threshold_cents >= price_cents,
            )
        ).all()
    )

    if not candidate_alerts:
        return

    # Resolve part + retailer once; both are referenced by every email body.
    part = db.scalars(select(DBPart).where(DBPart.id == part_id)).first()
    retailer = db.scalars(select(DBRetailer).where(DBRetailer.id == retailer_id)).first()
    if part is None or retailer is None:
        # Defensive — the chokepoint guarantees both exist, but evaluate should
        # never crash a price-write transaction.
        logger.warning(
            "price_alert_evaluator_missing_entity: part_id=%s retailer_id=%s " "part_present=%s retailer_present=%s",
            part_id,
            retailer_id,
            part is not None,
            retailer is not None,
        )
        return

    for alert in candidate_alerts:
        start = time.monotonic()
        try:
            if alert.last_fired_at is not None and observed_at - _ensure_aware(alert.last_fired_at) < ALERT_COOLDOWN:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                logger.info(
                    "price_alert_evaluated: alert_id=%s part_id=%s "
                    "price_cents=%d threshold_cents=%d verdict=suppressed_cooldown "
                    "elapsed_ms=%d",
                    alert.id,
                    part_id,
                    price_cents,
                    alert.threshold_cents,
                    elapsed_ms,
                )
                continue

            user = db.scalars(select(DBUser).where(DBUser.id == alert.user_id)).first()
            if user is None:
                # Alert points at a deleted user — skip and log; do not crash.
                logger.warning(
                    "price_alert_evaluator_missing_user: alert_id=%s user_id=%s",
                    alert.id,
                    alert.user_id,
                )
                continue

            success = email_module.send_price_drop_alert_email(user.email, part, retailer, price_cents, alert)
            logger.info(
                "price_alert_email_sent: alert_id=%s user_id=%s success=%s",
                alert.id,
                alert.user_id,
                bool(success),
            )

            if success:
                alert.last_fired_at = observed_at
                db.add(alert)
                db.flush()
                verdict = "fired"
            else:
                # Idempotent retry: leave last_fired_at as-is so the next
                # observation re-attempts.
                verdict = "fired"

            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "price_alert_evaluated: alert_id=%s part_id=%s "
                "price_cents=%d threshold_cents=%d verdict=%s elapsed_ms=%d",
                alert.id,
                part_id,
                price_cents,
                alert.threshold_cents,
                verdict,
                elapsed_ms,
            )
        except Exception as exc:
            # Per-alert iteration must NEVER poison the price-write transaction.
            # Log with alert_id (UUID — safe) and continue.
            logger.warning(
                "price_alert_evaluator_exception: alert_id=%s error=%s",
                getattr(alert, "id", "?"),
                exc,
            )
            continue
