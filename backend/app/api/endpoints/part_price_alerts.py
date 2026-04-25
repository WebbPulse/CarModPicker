"""
Per-user price-drop alert endpoints.

Hand-rolled router (NOT BaseEndpointRouter) because the surface is intentionally
narrower than CRUD: scoped to current_user, no admin or list-all paths. The
separate evaluator + signed-JWT unsubscribe endpoint land in T03.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.models.part import Part as DBPart
from app.api.models.user import User as DBUser
from app.api.schemas.part_price_alert import (
    PartPriceAlertCreate,
    PartPriceAlertRead,
    PartPriceAlertUpdate,
)
from app.api.services import part_price_alert_service
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=PartPriceAlertRead,
    status_code=status.HTTP_201_CREATED,
    responses=standard_responses(
        success_description="Alert subscription created (or updated if one already existed)",
        unauthorized=True,
        not_found=True,
        validation_error=True,
    ),
)
async def subscribe_to_part_price_alert(
    payload: PartPriceAlertCreate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> PartPriceAlertRead:
    """Subscribe the current user to a price-drop alert on a part.

    Idempotent on (user_id, part_id) — re-subscribing updates the threshold and
    reactivates a previously-soft-deleted alert instead of creating a duplicate.
    """
    part = db.scalars(select(DBPart).where(DBPart.id == payload.part_id)).first()
    if part is None:
        ResponsePatterns.raise_not_found("Part", payload.part_id)

    alert = part_price_alert_service.create_or_update_alert(
        db=db,
        user_id=current_user.id,
        part_id=payload.part_id,
        threshold_cents=payload.threshold_cents,
    )
    db.commit()
    db.refresh(alert)
    logger.info(
        "part_price_alert_subscribed: alert_id=%s user_id=%s part_id=%s threshold_cents=%d",
        alert.id,
        current_user.id,
        alert.part_id,
        alert.threshold_cents,
    )
    return PartPriceAlertRead.model_validate(alert)


@router.get(
    "/me",
    response_model=list[PartPriceAlertRead],
    responses=standard_responses(
        success_description="Active price-drop alerts for the current user",
        unauthorized=True,
    ),
)
async def list_my_active_alerts(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> list[PartPriceAlertRead]:
    """List the current user's active alerts (active=True only)."""
    alerts = part_price_alert_service.list_active_alerts_for_user(db, current_user.id)
    return [PartPriceAlertRead.model_validate(a) for a in alerts]


@router.patch(
    "/{alert_id}",
    response_model=PartPriceAlertRead,
    responses=standard_responses(
        success_description="Alert updated",
        unauthorized=True,
        not_found=True,
        validation_error=True,
    ),
)
async def update_my_alert(
    alert_id: UUID,
    payload: PartPriceAlertUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> PartPriceAlertRead:
    """Update threshold and/or active flag on the user's own alert.

    Returns 404 (not 403) for alerts owned by another user, to avoid leaking
    existence via endpoint behavior.
    """
    alert = part_price_alert_service.get_alert_for_owner(db, alert_id, current_user.id)
    if alert is None:
        ResponsePatterns.raise_not_found("Price alert", alert_id)

    if payload.threshold_cents is not None:
        alert.threshold_cents = payload.threshold_cents
    if payload.active is not None:
        alert.active = payload.active

    db.add(alert)
    db.commit()
    db.refresh(alert)
    return PartPriceAlertRead.model_validate(alert)


@router.delete(
    "/{alert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=standard_responses(
        success_description="Alert deactivated",
        unauthorized=True,
        not_found=True,
    ),
)
async def delete_my_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> None:
    """Soft-delete the user's own alert by setting active=False.

    Idempotent at the user-experience level: a second DELETE on the same id
    returns 404 because the row is no longer ownable-and-active. (T03 will
    treat already-deleted rows the same way the unsubscribe-via-token path
    does — currently 404 is the simplest contract for this surface.)
    """
    deactivated = part_price_alert_service.deactivate_alert(db, alert_id, current_user.id)
    if not deactivated:
        ResponsePatterns.raise_not_found("Price alert", alert_id)
    db.commit()
    return None
