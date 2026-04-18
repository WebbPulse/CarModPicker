"""Tests for admin endpoints."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.brand import Brand as DBBrand
from app.api.models.part import Part as DBPart
from app.api.models.user import User as DBUser
from app.core.config import settings
from tests.conftest import INVALID_UUID_STR


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


class TestAdminRescrapeArchives:
    """Test cases for admin rescrape-archives endpoint."""

    def test_rescrape_archives_unauthorized(self, client: TestClient) -> None:
        """Test rescrape archives without auth returns 401."""
        response = client.post(
            f"{settings.API_STR}/admin/crawled-pages/rescrape-archives",
            json={"crawler_user_id": INVALID_UUID_STR, "default_category_id": INVALID_UUID_STR},
        )
        assert response.status_code == 401

    def test_rescrape_archives_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Test rescrape archives as non-admin returns 403."""
        token = create_and_login_user(client, db_session, "rescrape_forbidden")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_STR}/admin/crawled-pages/rescrape-archives",
            json={"crawler_user_id": INVALID_UUID_STR, "default_category_id": INVALID_UUID_STR},
            headers=headers,
        )
        assert response.status_code == 403

    def test_rescrape_archives_success_admin(self, client: TestClient, db_session: Session) -> None:
        """Test rescrape archives as admin returns 200 with status started."""
        from tests.conftest import get_default_category_id

        suffix = "rescrape_ok"
        token = create_and_login_admin_user(client, db_session, suffix)
        admin = db_session.query(DBUser).filter(DBUser.username == f"admin_ep_test_{suffix}").first()
        assert admin is not None
        cat_id = get_default_category_id(db_session)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_STR}/admin/crawled-pages/rescrape-archives",
            json={"crawler_user_id": str(admin.id), "default_category_id": str(cat_id)},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "started"
        assert "message" in data


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

        part = DBPart(
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
        part_after = db_session.query(DBPart).filter(DBPart.id == part_id).first()
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


class TestAdminTableCounts:
    """GET /admin/stats/table-counts — supplemental DB counts (admin only)."""

    def test_table_counts_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        token = create_and_login_user(client, db_session, "table_counts_forbidden")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"{settings.API_STR}/admin/stats/table-counts", headers=headers)
        assert response.status_code == 403

    def test_table_counts_admin_ok(self, client: TestClient, db_session: Session) -> None:
        token = create_and_login_admin_user(client, db_session, "table_counts_ok")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"{settings.API_STR}/admin/stats/table-counts", headers=headers)
        assert response.status_code == 200
        data = response.json()
        for key in (
            "build_list_phases",
            "crawled_pages",
            "part_listings",
            "part_price_histories",
            "image_source_mappings",
            "build_logs",
            "part_cars",
            "votes_by_entity_type",
            "reports_by_entity_type",
            "crawl_bucket_configured",
            "crawl_bucket_total",
            "crawl_bucket_by_prefix",
        ):
            assert key in data
        assert isinstance(data["build_list_phases"], int)
        assert isinstance(data["votes_by_entity_type"], dict)
        assert isinstance(data["reports_by_entity_type"], dict)
        assert isinstance(data["crawl_bucket_configured"], bool)
        assert isinstance(data["crawl_bucket_total"], int)
        assert isinstance(data["crawl_bucket_by_prefix"], dict)
