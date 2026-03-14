"""
Subscription helpers for premium tier and build list caps.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.api.models.user import User as DBUser


def is_user_premium(user: "DBUser") -> bool:
    """
    Return True if the user has an active premium subscription.

    Premium is active when:
    - subscription_tier == 'premium'
    - subscription_status == 'active'
    - subscription_expires_at is None or in the future (UTC)
    """
    if user.subscription_tier != "premium":
        return False
    if user.subscription_status != "active":
        return False
    if user.subscription_expires_at is not None and user.subscription_expires_at <= datetime.now(UTC):
        return False
    return True
