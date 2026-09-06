"""Tests for common operations utility functions."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.api.models.report import Report
from app.api.utils.common_operations import (
    delete_entity,
    validate_pagination_params,
    verify_admin_access,
    verify_entity_exists,
    verify_entity_ownership,
)
from app.db.dynamo.users import User, UserRepository


def _make_report(db_session: Session, user_id: UUID) -> Report:
    """Persist a Report as a stand-in SQL entity with a ``user_id`` owner."""
    report = Report(user_id=user_id, entity_type="part", entity_id=uuid7(), reason="spam", description="Test")
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


class TestCommonOperations:
    """Test cases for common operations utility functions."""

    def test_verify_entity_exists_success(self, db_session, test_user: User) -> None:
        """Test verifying an entity that exists."""
        build_list = _make_report(db_session, test_user.id)

        result = verify_entity_exists(db_session, Report, build_list.id, "build list")
        assert result.id == build_list.id

    def test_verify_entity_exists_not_found(self, db_session) -> None:
        """Test verifying an entity that doesn't exist."""
        try:
            verify_entity_exists(db_session, Report, uuid7(), "build list")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 404
            assert "not found" in e.detail.lower()

    def test_verify_entity_ownership_success(self, db_session, test_user: User) -> None:
        """Test verifying ownership of an entity owned by the user."""
        build_list = _make_report(db_session, test_user.id)

        result = verify_entity_ownership(db_session, Report, build_list.id, test_user, "build list")
        assert result.id == build_list.id

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
            verify_entity_ownership(db_session, Report, build_list.id, test_user, "build list")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 403

    def test_verify_admin_access_admin(self, test_user: User) -> None:
        """Test verifying admin access for admin user."""
        test_user.is_admin = True
        # Should not raise
        verify_admin_access(test_user)

    def test_verify_admin_access_superuser(self, test_user: User) -> None:
        """Test verifying admin access for superuser."""
        test_user.is_superuser = True
        # Should not raise
        verify_admin_access(test_user)

    def test_verify_admin_access_non_admin(self, test_user: User) -> None:
        """Test verifying admin access for non-admin user."""
        test_user.is_admin = False
        test_user.is_superuser = False
        try:
            verify_admin_access(test_user)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 403

    def test_validate_pagination_params_valid(self) -> None:
        """Test validating valid pagination parameters."""
        # Should not raise
        validate_pagination_params(skip=0, limit=100)

    def test_validate_pagination_params_negative_skip(self) -> None:
        """Test validating pagination with negative skip."""
        try:
            validate_pagination_params(skip=-1, limit=100)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 400

    def test_validate_pagination_params_zero_limit(self) -> None:
        """Test validating pagination with zero limit."""
        try:
            validate_pagination_params(skip=0, limit=0)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 400

    def test_validate_pagination_params_exceeds_max_limit(self) -> None:
        """Test validating pagination with limit exceeding max."""
        try:
            validate_pagination_params(skip=0, limit=2000, max_limit=1000)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 400

    def test_delete_entity_success(self, db_session, test_user: User) -> None:
        """Test deleting an entity successfully."""
        import logging

        build_list = _make_report(db_session, test_user.id)

        logger = logging.getLogger(__name__)
        result = delete_entity(db_session, build_list, test_user.id, logger, "build list")

        assert "message" in result
        assert "deleted successfully" in result["message"].lower()

        # Verify entity is deleted
        deleted = db_session.query(Report).filter(Report.id == build_list.id).first()
        assert deleted is None
