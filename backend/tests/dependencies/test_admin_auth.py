from typing import Any

import pytest
from fastapi import HTTPException, status

from app.api.dependencies.auth import get_current_admin_user, get_current_superuser
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository


class TestAdminAuthentication:
    """Test cases for admin authentication dependencies."""

    @pytest.mark.asyncio
    async def test_get_current_admin_user_with_admin_user(self, db_session: Any) -> None:
        """Test that admin user can access admin endpoints."""
        admin_user = UserRepository().create_user(
            DBUser(
                username="admin_test",
                email="admin_test@example.com",
                hashed_password="hashed_password",
                is_admin=True,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        result = await get_current_admin_user(admin_user)
        assert result == admin_user

    @pytest.mark.asyncio
    async def test_get_current_admin_user_with_superuser(self, db_session: Any) -> None:
        """Test that superuser can access admin endpoints."""
        superuser = UserRepository().create_user(
            DBUser(
                username="superuser_test",
                email="superuser_test@example.com",
                hashed_password="hashed_password",
                is_admin=False,
                is_superuser=True,
                email_verified=True,
                disabled=False,
            )
        )

        result = await get_current_admin_user(superuser)
        assert result == superuser

    @pytest.mark.asyncio
    async def test_get_current_admin_user_with_regular_user(self, db_session: Any) -> None:
        """Test that regular user cannot access admin endpoints."""
        regular_user = UserRepository().create_user(
            DBUser(
                username="regular_test",
                email="regular_test@example.com",
                hashed_password="hashed_password",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin_user(regular_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin access required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_admin_user_with_disabled_admin(self, db_session: Any) -> None:
        """Test that disabled admin user can still access admin endpoints (disabled check is in base dependency)."""
        disabled_admin = UserRepository().create_user(
            DBUser(
                username="disabled_admin_test",
                email="disabled_admin_test@example.com",
                hashed_password="hashed_password",
                is_admin=True,
                is_superuser=False,
                email_verified=True,
                disabled=True,
            )
        )

        result = await get_current_admin_user(disabled_admin)
        assert result == disabled_admin


class TestSuperuserAuthentication:
    """Test cases for superuser authentication dependencies."""

    @pytest.mark.asyncio
    async def test_get_current_superuser_with_superuser(self, db_session: Any) -> None:
        """Test that superuser can access superuser endpoints."""
        superuser = UserRepository().create_user(
            DBUser(
                username="superuser_test",
                email="superuser_test@example.com",
                hashed_password="hashed_password",
                is_admin=False,
                is_superuser=True,
                email_verified=True,
                disabled=False,
            )
        )

        result = await get_current_superuser(superuser)
        assert result == superuser

    @pytest.mark.asyncio
    async def test_get_current_superuser_with_admin_user(self, db_session: Any) -> None:
        """Test that admin user cannot access superuser endpoints."""
        admin_user = UserRepository().create_user(
            DBUser(
                username="admin_test",
                email="admin_test@example.com",
                hashed_password="hashed_password",
                is_admin=True,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_superuser(admin_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Superuser privileges required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_superuser_with_regular_user(self, db_session: Any) -> None:
        """Test that regular user cannot access superuser endpoints."""
        regular_user = UserRepository().create_user(
            DBUser(
                username="regular_test",
                email="regular_test@example.com",
                hashed_password="hashed_password",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_superuser(regular_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Superuser privileges required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_superuser_with_disabled_superuser(self, db_session: Any) -> None:
        """Test that disabled superuser can still access superuser endpoints (disabled check is in base dependency)."""
        disabled_superuser = UserRepository().create_user(
            DBUser(
                username="disabled_superuser_test",
                email="disabled_superuser_test@example.com",
                hashed_password="hashed_password",
                is_admin=False,
                is_superuser=True,
                email_verified=True,
                disabled=True,
            )
        )

        result = await get_current_superuser(disabled_superuser)
        assert result == disabled_superuser


class TestPrivilegeHierarchy:
    """Test cases for privilege hierarchy and edge cases."""

    @pytest.mark.asyncio
    async def test_user_with_both_admin_and_superuser_flags(self, db_session: Any) -> None:
        """Test user with both admin and superuser flags set."""
        dual_user = UserRepository().create_user(
            DBUser(
                username="dual_test",
                email="dual_test@example.com",
                hashed_password="hashed_password",
                is_admin=True,
                is_superuser=True,
                email_verified=True,
                disabled=False,
            )
        )

        admin_result = await get_current_admin_user(dual_user)
        assert admin_result == dual_user

        superuser_result = await get_current_superuser(dual_user)
        assert superuser_result == dual_user

    @pytest.mark.asyncio
    async def test_user_with_no_privileges(self, db_session: Any) -> None:
        """Test user with no admin or superuser privileges."""
        no_privilege_user = UserRepository().create_user(
            DBUser(
                username="no_privilege_test",
                email="no_privilege_test@example.com",
                hashed_password="hashed_password",
                is_admin=False,
                is_superuser=False,
                email_verified=True,
                disabled=False,
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin_user(no_privilege_user)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

        with pytest.raises(HTTPException) as exc_info:
            await get_current_superuser(no_privilege_user)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
