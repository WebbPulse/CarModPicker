"""
Global app settings endpoints.

Stores a single row in ``app_settings`` with runtime-mutable toggles that
apply to every user (e.g. the premium-system kill switch that disables
ads, gates, pricing, and all subscription UX). Read is public so anonymous
clients can honor the toggle; write is admin-only.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.app_settings import AppSettings as DBAppSettings
from app.api.models.user import User as DBUser
from app.api.schemas.app_settings import AppSettingsRead, AppSettingsUpdate
from app.api.utils.endpoint_decorators import standard_responses
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_or_create_settings(db: Session) -> DBAppSettings:
    """Return the singleton settings row, creating it with defaults on first access."""
    row = db.query(DBAppSettings).filter(DBAppSettings.id == 1).one_or_none()
    if row is None:
        row = DBAppSettings(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get(
    "/",
    response_model=AppSettingsRead,
    responses=standard_responses(success_description="Current global app settings"),
)
async def get_app_settings(db: Session = Depends(get_db)) -> AppSettingsRead:
    """Public: current global app settings (used by the frontend to honor toggles)."""
    row = _get_or_create_settings(db)
    return AppSettingsRead.model_validate(row)


@router.put(
    "/",
    response_model=AppSettingsRead,
    responses=standard_responses(
        success_description="App settings updated",
        forbidden=True,
    ),
)
async def update_app_settings(
    update: AppSettingsUpdate,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> AppSettingsRead:
    """Admin-only: update global app settings. Only provided fields change."""
    row = _get_or_create_settings(db)
    data = update.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    logger.info("Admin %s updated app settings: %s", current_user.id, data)
    return AppSettingsRead.model_validate(row)
