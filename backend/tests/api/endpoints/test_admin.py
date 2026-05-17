"""Tests for admin endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.part import Part as DBPart
from app.api.models.part_manufacturer import PartManufacturer as DBPartManufacturer
from app.api.models.part_price_alert import PartPriceAlert as DBPartPriceAlert
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
        response = client.post(f"{settings.API_STR}/admin/db-ops/migrations/run")
        assert response.status_code == 401

    def test_run_migrations_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Test run migrations as non-admin returns 403."""
        token = create_and_login_user(client, db_session, "run_forbidden")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(f"{settings.API_STR}/admin/db-ops/migrations/run", headers=headers)
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
            response = client.post(f"{settings.API_STR}/admin/db-ops/migrations/run", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "output" in data
        assert data.get("error") is None
        assert mock_run.call_count >= 1

    def test_get_current_migration_unauthorized(self, client: TestClient) -> None:
        """Test get current migration without auth returns 401."""
        response = client.get(f"{settings.API_STR}/admin/db-ops/migrations/current")
        assert response.status_code == 401

    def test_get_current_migration_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Test get current migration as non-admin returns 403."""
        token = create_and_login_user(client, db_session, "current_forbidden")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"{settings.API_STR}/admin/db-ops/migrations/current", headers=headers)
        assert response.status_code == 403

    def test_get_current_migration_success_admin(self, client: TestClient, db_session: Session) -> None:
        """Test get current migration as admin returns 200."""
        token = create_and_login_admin_user(client, db_session, "current_success")
        headers = {"Authorization": f"Bearer {token}"}

        mock_result = MagicMock()
        mock_result.stdout = "abc123 (head)\n"
        mock_result.check_returncode = MagicMock()

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            response = client.get(f"{settings.API_STR}/admin/db-ops/migrations/current", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "current_revision" in data
        assert "output" in data
        assert data["current_revision"] == "abc123 (head)"
        mock_run.assert_called_once()


class TestAdminDeleteAllPartManufacturers:
    """Test cases for admin delete-all-part_manufacturers endpoint."""

    def test_delete_all_part_manufacturers_unauthorized(self, client: TestClient) -> None:
        """Test delete all part_manufacturers without auth returns 401."""
        response = client.post(f"{settings.API_STR}/admin/db-ops/part-manufacturers/delete-all")
        assert response.status_code == 401

    def test_delete_all_part_manufacturers_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Test delete all part_manufacturers as non-admin returns 403."""
        token = create_and_login_user(client, db_session, "delete_part_manufacturers_forbidden")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_STR}/admin/db-ops/part-manufacturers/delete-all",
            headers=headers,
        )
        assert response.status_code == 403

    def test_delete_all_part_manufacturers_success_admin(
        self, client: TestClient, db_session: Session, test_category, test_user
    ) -> None:
        """Test delete all part_manufacturers as admin returns 200 with deleted_count."""
        part_manufacturer1 = DBPartManufacturer(
            name="part_manufacturer_delete_1", description="PartManufacturer 1", is_active=True
        )
        part_manufacturer2 = DBPartManufacturer(
            name="part_manufacturer_delete_2", description="PartManufacturer 2", is_active=True
        )
        db_session.add_all([part_manufacturer1, part_manufacturer2])
        db_session.commit()
        db_session.refresh(part_manufacturer1)
        db_session.refresh(part_manufacturer2)

        token = create_and_login_admin_user(client, db_session, "delete_part_manufacturers_success")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_STR}/admin/db-ops/part-manufacturers/delete-all",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "deleted_count" in data
        assert data["deleted_count"] == 2

        # Verify part_manufacturers are gone
        remaining = db_session.query(DBPartManufacturer).count()
        assert remaining == 0

    def test_delete_all_part_manufacturers_nullifies_part_part_manufacturer_ids(
        self, client: TestClient, db_session: Session, test_category, test_user
    ) -> None:
        """Test that deleting all part_manufacturers nullifies part_manufacturer_id on global parts."""
        part_manufacturer = DBPartManufacturer(
            name="part_manufacturer_for_part", description="PartManufacturer", is_active=True
        )
        db_session.add(part_manufacturer)
        db_session.commit()
        db_session.refresh(part_manufacturer)

        part = DBPart(
            name="Part with part_manufacturer",
            description="Test part",
            category_id=test_category.id,
            user_id=test_user.id,
            part_manufacturer_id=part_manufacturer.id,
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)
        part_id = part.id

        token = create_and_login_admin_user(client, db_session, "delete_part_manufacturers_nullify")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_STR}/admin/db-ops/part-manufacturers/delete-all",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["deleted_count"] == 1

        # Verify part still exists but part_manufacturer_id is null
        db_session.expire_all()  # Clear any cached state
        part_after = db_session.query(DBPart).filter(DBPart.id == part_id).first()
        assert part_after is not None
        assert part_after.part_manufacturer_id is None

    def test_delete_all_part_manufacturers_empty_success(self, client: TestClient, db_session: Session) -> None:
        """Test delete all part_manufacturers when no part_manufacturers exist returns 200 with deleted_count=0."""
        token = create_and_login_admin_user(client, db_session, "delete_part_manufacturers_empty")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            f"{settings.API_STR}/admin/db-ops/part-manufacturers/delete-all",
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
        ):
            assert key in data
        assert isinstance(data["build_list_phases"], int)
        assert isinstance(data["votes_by_entity_type"], dict)
        assert isinstance(data["reports_by_entity_type"], dict)
        # Crawl-bucket stats have moved to /admin/stats/crawl-bucket so this endpoint
        # is fast regardless of bucket size.
        for key in (
            "crawl_bucket_configured",
            "crawl_bucket_total",
            "crawl_bucket_by_prefix",
        ):
            assert key not in data


class TestAdminCrawlBucketSummary:
    """GET /admin/stats/crawl-bucket — on-demand S3 listing (admin only)."""

    def test_crawl_bucket_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        token = create_and_login_user(client, db_session, "crawl_bucket_forbidden")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"{settings.API_STR}/admin/stats/crawl-bucket", headers=headers)
        assert response.status_code == 403

    def test_crawl_bucket_admin_ok(self, client: TestClient, db_session: Session) -> None:
        token = create_and_login_admin_user(client, db_session, "crawl_bucket_ok")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"{settings.API_STR}/admin/stats/crawl-bucket", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "crawl_bucket_configured" in data
        assert isinstance(data["crawl_bucket_configured"], bool)
        assert "crawl_bucket_total" in data
        assert isinstance(data["crawl_bucket_total"], int)
        assert "crawl_bucket_by_prefix" in data
        assert isinstance(data["crawl_bucket_by_prefix"], dict)


class TestAdminDeleteCrawlerParts:
    """POST /admin/db-ops/parts/delete-crawler — delete only crawler-sourced parts.

    The endpoint opens its own session via ``SessionLocal()`` (it does not use
    the ``get_db`` dependency), so it bypasses the SQLite test session. We patch
    ``db_ops.SessionLocal`` to a sessionmaker bound to the same connection the
    test's ``db_session`` uses, so the endpoint sees test-created rows and the
    test sees the endpoint's deletions (all inside the rolled-back outer txn).
    """

    _URL = f"{settings.API_STR}/admin/db-ops/parts/delete-crawler"

    @staticmethod
    def _patch_session_local(monkeypatch: "pytest.MonkeyPatch", db_session: Session) -> None:
        from sqlalchemy.orm import sessionmaker

        from app.api.endpoints.admin import db_ops

        bound = sessionmaker(
            bind=db_session.connection(),
            autocommit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )
        monkeypatch.setattr(db_ops, "SessionLocal", bound)

    def test_delete_crawler_parts_unauthorized(self, client: TestClient) -> None:
        """No auth returns 401."""
        response = client.post(self._URL)
        assert response.status_code == 401

    def test_delete_crawler_parts_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Non-admin returns 403."""
        token = create_and_login_user(client, db_session, "delete_crawler_parts_forbidden")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(self._URL, headers=headers)
        assert response.status_code == 403

    def test_delete_crawler_parts_empty_success(
        self, client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No parts -> 200 with deleted_count=0."""
        token = create_and_login_admin_user(client, db_session, "delete_crawler_parts_empty")
        self._patch_session_local(monkeypatch, db_session)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(self._URL, headers=headers)
        assert response.status_code == 200
        assert response.json()["deleted_count"] == 0

    def test_delete_crawler_parts_keeps_user_and_extension_parts(
        self,
        client: TestClient,
        db_session: Session,
        test_category,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Deletes adapter-sourced parts; keeps user_created and chrome_extension parts."""
        user_part = DBPart(
            name="User part",
            category_id=test_category.id,
            user_id=test_user.id,
            source="user_created",
        )
        ext_part = DBPart(
            name="Browser companion part",
            category_id=test_category.id,
            user_id=test_user.id,
            source="chrome_extension",
        )
        crawler_part_a = DBPart(
            name="Crawler part A",
            category_id=test_category.id,
            user_id=test_user.id,
            source="a90shop",
        )
        crawler_part_b = DBPart(
            name="Crawler part B",
            category_id=test_category.id,
            user_id=test_user.id,
            source="studiorsr",
        )
        db_session.add_all([user_part, ext_part, crawler_part_a, crawler_part_b])
        db_session.commit()
        user_part_id = user_part.id
        ext_part_id = ext_part.id

        token = create_and_login_admin_user(client, db_session, "delete_crawler_parts_mix")
        self._patch_session_local(monkeypatch, db_session)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(self._URL, headers=headers)

        assert response.status_code == 200
        assert response.json()["deleted_count"] == 2

        db_session.expire_all()
        remaining = {p.id for p in db_session.query(DBPart).all()}
        assert remaining == {user_part_id, ext_part_id}

    def test_delete_crawler_parts_clears_price_alerts(
        self,
        client: TestClient,
        db_session: Session,
        test_category,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A price alert on a crawler part is removed (no FK cascade) so the delete succeeds."""
        crawler_part = DBPart(
            name="Crawler part with alert",
            category_id=test_category.id,
            user_id=test_user.id,
            source="a90shop",
        )
        db_session.add(crawler_part)
        db_session.commit()
        db_session.refresh(crawler_part)

        alert = DBPartPriceAlert(
            user_id=test_user.id,
            part_id=crawler_part.id,
            threshold_cents=12345,
        )
        db_session.add(alert)
        db_session.commit()
        alert_id = alert.id

        token = create_and_login_admin_user(client, db_session, "delete_crawler_parts_alert")
        self._patch_session_local(monkeypatch, db_session)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(self._URL, headers=headers)

        assert response.status_code == 200
        assert response.json()["deleted_count"] == 1

        db_session.expire_all()
        assert db_session.query(DBPart).count() == 0
        assert db_session.query(DBPartPriceAlert).filter(DBPartPriceAlert.id == alert_id).first() is None
