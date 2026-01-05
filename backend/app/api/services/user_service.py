"""
User service that extends the base CRUD service.
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.api.models.user import User as DBUser
from app.api.schemas.user import UserCreate, UserRead, UserUpdate
from app.api.services.base_crud_service import BaseCRUDService
from app.core.logging import get_logger

logger = get_logger()


class UserService(BaseCRUDService[DBUser, UserCreate, UserRead, UserUpdate]):
    """User service that extends the base CRUD service."""

    def __init__(self) -> None:
        super().__init__(
            model=DBUser,
            entity_name="user",
            subscription_check_method=None,  # Users don't have subscription limits
        )

    def get_by_username(
        self,
        db: Session,
        username: str,
        logger: Optional[logging.Logger] = None,
    ) -> Optional[DBUser]:
        """Get user by username."""
        log = logger if logger is not None else get_logger()
        user = db.query(DBUser).filter(DBUser.username == username).first()
        if user:
            log.info(f"Retrieved user by username: {username}")
        else:
            log.info(f"No user found with username: {username}")
        return user

    def get_by_email(
        self,
        db: Session,
        email: str,
        logger: Optional[logging.Logger] = None,
    ) -> Optional[DBUser]:
        """Get user by email."""
        log = logger if logger is not None else get_logger()
        user = db.query(DBUser).filter(DBUser.email == email).first()
        if user:
            log.info(f"Retrieved user by email: {email}")
        else:
            log.info(f"No user found with email: {email}")
        return user

    def get_all_users(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[DBUser]:
        """Get all users with pagination (admin only)."""
        log = logger if logger is not None else get_logger()
        users = db.query(DBUser).offset(skip).limit(limit).all()
        log.info(f"Retrieved {len(users)} users")
        return users

    def count_all(
        self,
        db: Session,
        logger: Optional[logging.Logger] = None,
    ) -> int:
        """Get total count of users."""
        log = logger if logger is not None else get_logger()
        count = db.query(DBUser).count()
        log.info(f"Total user count: {count}")
        return count
