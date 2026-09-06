"""Tests for common patterns utility functions."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.api.models.bug_report import BugReport as Report
from app.api.utils.common_patterns import (
    get_entity_or_404,
    validate_pagination_params,
    verify_entity_ownership,
)
from app.db.dynamo.users import User, UserRepository


def _make_report(db_session: Session, user_id: UUID) -> Report:
    """Persist a Report as a stand-in SQL entity with a ``user_id`` owner."""
    report = Report(user_id=user_id, title="Test", description="Test")
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


class TestCommonPatterns:
    """Test cases for common patterns utility functions."""

    def test_get_entity_or_404_success(self, db_session, test_user: User) -> None:
        """Test getting an entity that exists."""
        build_list = _make_report(db_session, test_user.id)

        result = get_entity_or_404(db_session, Report, build_list.id, "build list")
        assert result.id == build_list.id

    def test_get_entity_or_404_not_found(self, db_session) -> None:
        """Test getting an entity that doesn't exist."""
        try:
            get_entity_or_404(db_session, Report, uuid7(), "build list")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 404

    def test_validate_pagination_params_valid(self) -> None:
        """Test validating valid pagination parameters."""
        skip, limit = validate_pagination_params(skip=0, limit=100)
        assert skip == 0
        assert limit == 100

    def test_validate_pagination_params_negative_skip(self) -> None:
        """Test validating pagination with negative skip (should normalize to 0)."""
        skip, limit = validate_pagination_params(skip=-1, limit=100)
        assert skip == 0
        assert limit == 100

    def test_validate_pagination_params_zero_limit(self) -> None:
        """Test validating pagination with zero limit (should normalize to 1)."""
        skip, limit = validate_pagination_params(skip=0, limit=0)
        assert skip == 0
        assert limit == 1

    def test_validate_pagination_params_exceeds_max_limit(self) -> None:
        """Test validating pagination with limit exceeding max (should normalize to 1000)."""
        skip, limit = validate_pagination_params(skip=0, limit=2000)
        assert skip == 0
        assert limit == 1000

    def test_verify_entity_ownership_success(self, db_session, test_user: User) -> None:
        """Test verifying ownership of an entity owned by the user."""
        build_list = _make_report(db_session, test_user.id)

        # Should not raise
        verify_entity_ownership(build_list, test_user, "build list")

    def test_verify_entity_ownership_not_owner(self, db_session, test_user: User) -> None:
        """Test verifying ownership when user doesn't own the entity."""
        from app.api.dependencies.auth import get_password_hash

        other_user = UserRepository().create_user(
            User(
                username="other_user",
                email="other@example.com",
                hashed_password=get_password_hash("password"),
                email_verified=True,
                disabled=False,
            )
        )

        build_list = _make_report(db_session, other_user.id)

        try:
            verify_entity_ownership(build_list, test_user, "build list")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 403
