"""Tests for common patterns utility functions."""

import logging

import pytest
from fastapi import HTTPException
from uuid6 import uuid7

from app.api.utils.common_patterns import (
    create_paginated_response,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
    verify_user_access_or_admin,
)
from app.db.dynamo.users import User


def _user(*, is_admin: bool = False, is_superuser: bool = False) -> User:
    """Build a user with the given admin and superuser flags."""
    return User(
        username=f"u{uuid7().hex[:10]}",
        email=f"{uuid7().hex[:10]}@example.com",
        email_verified=True,
        disabled=False,
        is_admin=is_admin,
        is_superuser=is_superuser,
    )


class TestValidatePaginationParams:
    """Covers clamping of the pagination parameters."""

    def test_valid(self) -> None:
        """In range values pass through unchanged."""
        skip, limit = validate_pagination_params(0, 100)
        assert skip == 0
        assert limit == 100

    def test_negative_skip(self) -> None:
        """A negative skip is clamped to zero."""
        skip, limit = validate_pagination_params(-1, 100)
        assert skip == 0
        assert limit == 100

    def test_zero_limit(self) -> None:
        """A zero limit is raised to one."""
        skip, limit = validate_pagination_params(0, 0)
        assert skip == 0
        assert limit == 1

    def test_exceeds_max_limit(self) -> None:
        """A limit above the maximum is clamped to it."""
        skip, limit = validate_pagination_params(0, 2000)
        assert skip == 0
        assert limit == 1000


class TestVerifyUserAccessOrAdmin:
    """Covers the owner, admin and stranger paths of the access check."""

    def test_owner_allowed(self) -> None:
        """The owner passes their own access check."""
        user = _user()
        verify_user_access_or_admin(user, user.id, "edit profile")

    @pytest.mark.parametrize("kwargs", [{"is_admin": True}, {"is_superuser": True}])
    def test_admin_or_superuser_allowed(self, kwargs: dict[str, bool]) -> None:
        """An admin or superuser passes the check for another user's resource."""
        verify_user_access_or_admin(_user(**kwargs), uuid7(), "edit profile")

    def test_other_user_forbidden(self, caplog: pytest.LogCaptureFixture) -> None:
        """An unrelated user gets a 403 naming the action, and the denial is logged."""
        user = _user()
        with caplog.at_level(logging.WARNING):
            with pytest.raises(HTTPException) as excinfo:
                verify_user_access_or_admin(user, uuid7(), "edit profile", logger=logging.getLogger("test"))
        assert excinfo.value.status_code == 403
        assert "edit profile" in str(excinfo.value.detail)
        assert any("Access denied" in rec.getMessage() for rec in caplog.records)


class TestResponseHelpers:
    """Covers the shared dependency bundle and the paginated envelope."""

    def test_public_endpoint_dependencies_expose_logger(self) -> None:
        """The public endpoint dependency bundle carries a logger."""
        deps = get_standard_public_endpoint_dependencies()
        assert isinstance(deps["logger"], logging.Logger)

    def test_create_paginated_response_envelope(self) -> None:
        """The envelope reports success, the message and the derived page numbers."""
        result = create_paginated_response([{"id": 1}, {"id": 2}], total=5, skip=2, limit=2, message="ok")
        assert result["success"] is True
        assert result["message"] == "ok"
        assert result["pagination"]["current_page"] == 2
        assert result["pagination"]["total_pages"] == 3
        assert result["pagination"]["has_next"] is True
        assert result["pagination"]["has_previous"] is True
