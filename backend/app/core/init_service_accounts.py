"""
Ensure system service accounts exist in the database on application startup.

Service accounts are machine identities (e.g. the crawler) that own content
created by automated processes. They cannot log in and are not shown as regular
users.
"""

import logging
import secrets

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


def _unusable_password_hash() -> str:
    """Return a bcrypt hash of a random secret nobody knows — prevents login."""
    random_secret = secrets.token_hex(32)
    return bcrypt.hashpw(random_secret.encode(), bcrypt.gensalt()).decode()


def init_crawler_service_account(db: Session) -> None:
    """
    Ensure the crawler service account exists. Idempotent — safe to call on every startup.

    - Creates the account if it doesn't exist.
    - If a regular user with the same username already exists, marks it as a service account.
    """
    from app.api.models.user import User

    username = settings.CRAWLER_SERVICE_ACCOUNT_USERNAME
    user = db.scalars(select(User).where(User.username == username)).first()

    if user is None:
        user = User(
            username=username,
            email=f"{username}@service.internal",
            hashed_password=_unusable_password_hash(),
            email_verified=True,
            disabled=False,
            is_service_account=True,
            is_admin=False,
            is_superuser=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Created crawler service account: username=%s id=%d", username, user.id)
    elif not user.is_service_account:
        user.is_service_account = True
        db.commit()
        logger.info("Marked existing user as service account: username=%s id=%d", username, user.id)
    else:
        logger.debug("Crawler service account already exists: username=%s id=%d", username, user.id)
