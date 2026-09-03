"""Tests for common patterns utility functions."""

from fastapi import HTTPException

from app.api.models.build_list import BuildList
from app.api.utils.common_patterns import (
    get_entity_or_404,
    validate_pagination_params,
    verify_entity_ownership,
)
from app.db.dynamo.users import User, UserRepository


class TestCommonPatterns:
    """Test cases for common patterns utility functions."""

    def test_get_entity_or_404_success(self, db_session, test_user: User) -> None:
        """Test getting an entity that exists."""
        build_list = BuildList(
            name="Test Build List",
            description="Test",
            user_id=test_user.id,
        )
        db_session.add(build_list)
        db_session.commit()
        db_session.refresh(build_list)

        result = get_entity_or_404(db_session, BuildList, build_list.id, "build list")
        assert result.id == build_list.id

    def test_get_entity_or_404_not_found(self, db_session) -> None:
        """Test getting an entity that doesn't exist."""
        try:
            get_entity_or_404(db_session, BuildList, 99999, "build list")
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
        build_list = BuildList(
            name="Test Build List",
            description="Test",
            user_id=test_user.id,
        )
        db_session.add(build_list)
        db_session.commit()
        db_session.refresh(build_list)

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

        build_list = BuildList(
            name="Test Build List",
            description="Test",
            user_id=other_user.id,  # Owned by different user
        )
        db_session.add(build_list)
        db_session.commit()
        db_session.refresh(build_list)

        try:
            verify_entity_ownership(build_list, test_user, "build list")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 403
