"""
Subscription helpers for premium tier and build list caps.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.app_settings import AppSettings as DBAppSettings
from app.db.dynamo.users import User as DBUser


def is_premium_system_disabled(db: Session) -> bool:
    """Return True when the admin kill switch has disconnected the premium system."""
    row = db.scalars(select(DBAppSettings).where(DBAppSettings.id == 1)).one_or_none()
    return bool(row and row.premium_disabled)


def is_user_premium(user: DBUser, db: Session | None = None) -> bool:
    """
    Return True if the user has an active premium subscription, OR if the
    admin kill switch has disabled the premium system entirely (in which
    case every user is treated as premium so feature gates are bypassed).

    Premium is active when:
    - subscription_tier == 'premium'
    - subscription_status == 'active'
    - subscription_expires_at is None or in the future (UTC)
    """
    if db is not None and is_premium_system_disabled(db):
        return True
    if user.subscription_tier != "premium":
        return False
    if user.subscription_status != "active":
        return False
    if user.subscription_expires_at is not None and user.subscription_expires_at <= datetime.now(UTC):
        return False
    return True
