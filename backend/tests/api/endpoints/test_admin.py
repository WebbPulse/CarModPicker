"""Tests for admin endpoints."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.brand import Brand as DBBrand
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.user import User as DBUser
from app.core.config import settings


def create_and_login_admin_user(client: TestClient, db_session: Session, username_suffix: str = "admin") -> str:
    """Create an admin user and log them in. Returns token."""
    username = f"admin_ep_test_{username_suffix}"
    email = f"admin_ep_test_{username_suffix}@example.com"
    password = "testpassword"

    admin_user = DBUser(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        is_admin=True,
        is_superuser=False,
        email_verified=True,
        disabled=False,
    )
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(admin_user)

    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert token_response.status_code == 200, f"Failed to login admin: {token_response.text}"
    return token_response.json()["access_token"]


def create_and_login_user(client: TestClient, db_session: Session, username_suffix: str) -> str:
    """Create a regular user and log them in. Returns token."""
    username = f"admin_ep_user_{username_suffix}"
    email = f"admin_ep_user_{username_suffix}@example.com"
    password = "testpassword"

    user_data = {"username": username, "email": email, "password": password}
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    if response.status_code != 200:
        # User might already exist
        response.raise_for_status()

    if db_session:
        user = db_session.query(DBUser).filter(DBUser.username == username).first()
        if user:
            user.email_verified = True
            db_session.commit()

    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert token_response.status_code == 200, f"Failed to login: {token_response.text}"
    return token_response.json()["access_token"]


class TestAdminMigrations:
    """Test cases for admin migration endpoints."""

    def test_run_migrations_unauthorized(self, client: TestClient) -> None:
        """Test run migrations without auth returns 401."""
        response = client.post(f"{settings.API_STR}/admin/migrations/run")
        assert response.status_code == 401

    def test_run_migrations_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Test run migrations as non-admin returns 403."""
        token = create_and_login_user(client, db_session, "run_forbidden")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(f"{settings.API_STR}/admin/migrations/run", headers=headers)
        assert response.status_code == 403

    def test_run_migrations_success_admin(self, client: TestClient, db_session: Session) -> None:
        """Test run migrations as admin returns 200 with success."""
        token = create_and_login_admin_user(client, db_session, "run_success")
        headers = {"Authorization": f"Bearer {token}"}

        mock_result = MagicMock()
        mock_result.stdout = "Running upgrade..."
        mock_result.check_returncode = MagicMock()

        mock_current = MagicMock()
        mock_current.stdout = "abc123 (head)"
        mock_current.check_returncode = MagicMock()

        with (patch("subprocess.run", side_effect=[mock_result, mock_current]) as mock_run,):
            response = client.post(f"{settings.API_STR}/admin/migrations/run", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "output" in data
        assert data.get("error") is None
        assert mock_run.call_count >= 1

    def test_get_current_migration_unauthorized(self, client: TestClient) -> None:
        """Test get current migration without auth returns 401."""
        response = client.get(f"{settings.API_STR}/admin/migrations/current")
        assert response.status_code == 401

    def test_get_current_migration_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Test get current migration as non-admin returns 403."""
        token = create_and_login_user(client, db_session, "current_forbidden")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"{settings.API_STR}/admin/migrations/current", headers=headers)
        assert response.status_code == 403

    def test_get_current_migration_success_admin(self, client: TestClient, db_session: Session) -> None:
        """Test get current migration as admin returns 200."""
        token = create_and_login_admin_user(client, db_session, "current_success")
        headers = {"Authorization": f"Bearer {token}"}

        mock_result = MagicMock()
        mock_result.stdout = "abc123 (head)\n"
        mock_result.check_returncode = MagicMock()

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            response = client.get(f"{settings.API_STR}/admin/migrations/current", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "current_revision" in data
        assert "output" in data
        assert data["current_revision"] == "abc123 (head)"
        mock_run.assert_called_once()


class TestAdminRerunInference:
    """Test cases for admin rerun-inference endpoint."""

    def test_rerun_inference_unauthorized(self, client: TestClient) -> None:
        """Test rerun inference without auth returns 401."""
        response = client.post(
            f"{settings.API_STR}/admin/global-parts/rerun-inference",
            json={"reassign_brand": True},
        )
        assert response.status_code == 401

    def test_rerun_inference_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Test rerun inference as non-admin returns 403."""
        token = create_and_login_user(client, db_session, "rerun_forbidden")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_STR}/admin/global-parts/rerun-inference",
            json={"reassign_brand": True},
            headers=headers,
        )
        assert response.status_code == 403

    def test_rerun_inference_success_admin(self, client: TestClient, db_session: Session) -> None:
        """Test rerun inference as admin returns 200 with updated_count and error_count."""
        token = create_and_login_admin_user(client, db_session, "rerun_success")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_STR}/admin/global-parts/rerun-inference",
            json={"reassign_brand": False},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "updated_count" in data
        assert "error_count" in data
        assert "errors" in data
        assert isinstance(data["updated_count"], int)
        assert isinstance(data["error_count"], int)
        assert isinstance(data["errors"], list)


class TestAdminDeleteAllBrands:
    """Test cases for admin delete-all-brands endpoint."""

    def test_delete_all_brands_unauthorized(self, client: TestClient) -> None:
        """Test delete all brands without auth returns 401."""
        response = client.post(f"{settings.API_STR}/admin/brands/delete-all")
        assert response.status_code == 401

    def test_delete_all_brands_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Test delete all brands as non-admin returns 403."""
        token = create_and_login_user(client, db_session, "delete_brands_forbidden")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_STR}/admin/brands/delete-all",
            headers=headers,
        )
        assert response.status_code == 403

    def test_delete_all_brands_success_admin(
        self, client: TestClient, db_session: Session, test_category, test_user
    ) -> None:
        """Test delete all brands as admin returns 200 with deleted_count."""
        brand1 = DBBrand(name="brand_delete_1", description="Brand 1", is_active=True)
        brand2 = DBBrand(name="brand_delete_2", description="Brand 2", is_active=True)
        db_session.add_all([brand1, brand2])
        db_session.commit()
        db_session.refresh(brand1)
        db_session.refresh(brand2)

        token = create_and_login_admin_user(client, db_session, "delete_brands_success")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_STR}/admin/brands/delete-all",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "deleted_count" in data
        assert data["deleted_count"] == 2

        # Verify brands are gone
        remaining = db_session.query(DBBrand).count()
        assert remaining == 0

    def test_delete_all_brands_nullifies_part_brand_ids(
        self, client: TestClient, db_session: Session, test_category, test_user
    ) -> None:
        """Test that deleting all brands nullifies brand_id on global parts."""
        brand = DBBrand(name="brand_for_part", description="Brand", is_active=True)
        db_session.add(brand)
        db_session.commit()
        db_session.refresh(brand)

        part = DBGlobalPart(
            name="Part with brand",
            description="Test part",
            category_id=test_category.id,
            user_id=test_user.id,
            brand_id=brand.id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)
        part_id = part.id

        token = create_and_login_admin_user(client, db_session, "delete_brands_nullify")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_STR}/admin/brands/delete-all",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["deleted_count"] == 1

        # Verify part still exists but brand_id is null
        db_session.expire_all()  # Clear any cached state
        part_after = db_session.query(DBGlobalPart).filter(DBGlobalPart.id == part_id).first()
        assert part_after is not None
        assert part_after.brand_id is None

    def test_delete_all_brands_empty_success(self, client: TestClient, db_session: Session) -> None:
        """Test delete all brands when no brands exist returns 200 with deleted_count=0."""
        token = create_and_login_admin_user(client, db_session, "delete_brands_empty")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_STR}/admin/brands/delete-all",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 0
