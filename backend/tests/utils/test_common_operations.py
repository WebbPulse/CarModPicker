"""Tests for common operations utility functions."""

from fastapi import HTTPException

from app.api.models.build_list import BuildList
from app.api.models.user import User
from app.api.utils.common_operations import (
    delete_entity,
    validate_pagination_params,
    verify_admin_access,
    verify_entity_exists,
    verify_entity_ownership,
)


class TestCommonOperations:
    """Test cases for common operations utility functions."""

    def test_verify_entity_exists_success(self, db_session, test_user: User) -> None:
        """Test verifying an entity that exists."""
        build_list = BuildList(
            name="Test Build List",
            description="Test",
            user_id=test_user.id,
        )
        db_session.add(build_list)
        db_session.commit()
        db_session.refresh(build_list)

        result = verify_entity_exists(db_session, BuildList, build_list.id, "build list")
        assert result.id == build_list.id

    def test_verify_entity_exists_not_found(self, db_session) -> None:
        """Test verifying an entity that doesn't exist."""
        try:
            verify_entity_exists(db_session, BuildList, 99999, "build list")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 404
            assert "not found" in e.detail.lower()

    def test_verify_entity_ownership_success(self, db_session, test_user: User) -> None:
        """Test verifying ownership of an entity owned by the user."""
        build_list = BuildList(
            name="Test Build List",
            description="Test",
            user_id=test_user.id,
        )
        db_session.add(build_list)
        db_session.commit()
        db_session.refresh(build_list)

        result = verify_entity_ownership(db_session, BuildList, build_list.id, test_user, "build list")
        assert result.id == build_list.id

    def test_verify_entity_ownership_not_owner(self, db_session, test_user: User) -> None:
        """Test verifying ownership when user doesn't own the entity."""
        from app.api.dependencies.auth import get_password_hash

        other_user = User(
            username="other_user",
            email="other@example.com",
            hashed_password=get_password_hash("password"),
            email_verified=True,
            disabled=False,
        )
        db_session.add(other_user)
        db_session.commit()

        build_list = BuildList(
            name="Test Build List",
            description="Test",
            user_id=other_user.id,  # Owned by different user
        )
        db_session.add(build_list)
        db_session.commit()
        db_session.refresh(build_list)

        try:
            verify_entity_ownership(db_session, BuildList, build_list.id, test_user, "build list")
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

        build_list = BuildList(
            name="Test Build List",
            description="Test",
            user_id=test_user.id,
        )
        db_session.add(build_list)
        db_session.commit()
        db_session.refresh(build_list)

        logger = logging.getLogger(__name__)
        result = delete_entity(db_session, build_list, test_user.id, logger, "build list")

        assert "message" in result
        assert "deleted successfully" in result["message"].lower()

        # Verify entity is deleted
        deleted = db_session.query(BuildList).filter(BuildList.id == build_list.id).first()
        assert deleted is None
