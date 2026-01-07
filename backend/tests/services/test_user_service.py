"""Tests for user service."""

import os

from sqlalchemy.orm import Session

from app.api.models.user import User
from app.api.services.user_service import UserService


def get_unique_username(base_name: str) -> str:
    """Generate a unique username for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestUserService:
    """Test cases for user service."""

    def test_get_by_username_found(self, db_session: Session, test_user: User) -> None:
        """Test getting a user by username when it exists."""
        service = UserService()
        result = service.get_by_username(db_session, test_user.username)
        assert result is not None
        assert result.username == test_user.username

    def test_get_by_username_not_found(self, db_session: Session) -> None:
        """Test getting a user by username when it doesn't exist."""
        service = UserService()
        result = service.get_by_username(db_session, get_unique_username("nonexistent"))
        assert result is None

    def test_get_by_email_found(self, db_session: Session, test_user: User) -> None:
        """Test getting a user by email when it exists."""
        service = UserService()
        result = service.get_by_email(db_session, test_user.email)
        assert result is not None
        assert result.email == test_user.email

    def test_get_by_email_not_found(self, db_session: Session) -> None:
        """Test getting a user by email when it doesn't exist."""
        service = UserService()
        result = service.get_by_email(db_session, f"{get_unique_username('nonexistent')}@example.com")
        assert result is None

    def test_get_all_users(self, db_session: Session, test_user: User) -> None:
        """Test getting all users with pagination."""
        service = UserService()
        result = service.get_all_users(db_session, skip=0, limit=10)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_count_all(self, db_session: Session, test_user: User) -> None:
        """Test counting all users."""
        service = UserService()
        count = service.count_all(db_session)
        assert count > 0
        assert isinstance(count, int)
