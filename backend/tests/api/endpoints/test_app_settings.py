"""Tests for global app settings endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from tests.api.endpoints.test_admin import create_and_login_admin_user, create_and_login_user


class TestAppSettings:
    """GET is public; PUT is admin-only. Row is lazily created with defaults on first read."""

    def test_get_public_returns_defaults(self, client: TestClient) -> None:
        response = client.get(f"{settings.API_STR}/app-settings/")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ads_disabled_global"] is False
        assert "updated_at" in body

    def test_put_unauthorized(self, client: TestClient) -> None:
        response = client.put(
            f"{settings.API_STR}/app-settings/",
            json={"ads_disabled_global": True},
        )
        assert response.status_code == 401

    def test_put_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        token = create_and_login_user(client, db_session, "app_settings_forbidden")
        response = client.put(
            f"{settings.API_STR}/app-settings/",
            headers={"Authorization": f"Bearer {token}"},
            json={"ads_disabled_global": True},
        )
        assert response.status_code == 403

    def test_put_admin_toggles_ads(self, client: TestClient, db_session: Session) -> None:
        token = create_and_login_admin_user(client, db_session, "app_settings_toggle")
        headers = {"Authorization": f"Bearer {token}"}

        # Flip on
        response = client.put(
            f"{settings.API_STR}/app-settings/",
            headers=headers,
            json={"ads_disabled_global": True},
        )
        assert response.status_code == 200, response.text
        assert response.json()["ads_disabled_global"] is True

        # Public read reflects update
        response = client.get(f"{settings.API_STR}/app-settings/")
        assert response.status_code == 200
        assert response.json()["ads_disabled_global"] is True

        # Flip off
        response = client.put(
            f"{settings.API_STR}/app-settings/",
            headers=headers,
            json={"ads_disabled_global": False},
        )
        assert response.status_code == 200
        assert response.json()["ads_disabled_global"] is False
