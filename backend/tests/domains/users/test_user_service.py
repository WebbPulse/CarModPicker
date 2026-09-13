"""Tests for user service."""

import os
from typing import Any

from app.api.services.user_service import UserService
from app.db.dynamo.users import User


def get_unique_username(base_name: str) -> str:
    """Generate a unique username for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestUserService:
    """Test cases for user service."""

    def test_get_by_username_found(self, test_user: User) -> None:
        """Test getting a user by username when it exists."""
        service = UserService()
        result = service.get_by_username(test_user.username)
        assert result is not None
        assert result.username == test_user.username

    def test_get_by_username_not_found(self, dynamo_tables: Any) -> None:
        """Test getting a user by username when it doesn't exist."""
        service = UserService()
        result = service.get_by_username(get_unique_username("nonexistent"))
        assert result is None

    def test_get_by_email_found(self, test_user: User) -> None:
        """Test getting a user by email when it exists."""
        service = UserService()
        result = service.get_by_email(test_user.email)
        assert result is not None
        assert result.email == test_user.email

    def test_get_by_email_not_found(self, dynamo_tables: Any) -> None:
        """Test getting a user by email when it doesn't exist."""
        service = UserService()
        result = service.get_by_email(f"{get_unique_username('nonexistent')}@example.com")
        assert result is None

    def test_get_all_users(self, test_user: User) -> None:
        """Test getting all users."""
        service = UserService()
        result = service.get_all_users()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_all_users_search(self, test_user: User) -> None:
        """Test filtering users by search term."""
        service = UserService()
        result = service.get_all_users(search=test_user.username)
        assert [u.id for u in result] == [test_user.id]

    def test_count_all(self, test_user: User) -> None:
        """Test counting all users."""
        service = UserService()
        count = service.count_all()
        assert count > 0
        assert isinstance(count, int)
