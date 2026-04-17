"""Tests for brand entity endpoints."""

import os
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.brand import Brand as DBBrand
from app.api.models.user import User as DBUser
from app.core.config import settings
from tests.conftest import INVALID_UUID_STR, get_default_category_id


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def create_and_login_admin_user(
    client: TestClient, db_session: Session, username_suffix: str = "admin"
) -> tuple[dict[str, Any], str]:
    """Create an admin user and log them in. Returns (user_dict, token)."""
    username = f"brand_admin_{username_suffix}"
    email = f"brand_admin_{username_suffix}@example.com"
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
    token = token_response.json()["access_token"]
    return admin_user.__dict__, token


def create_and_login_user(
    client: TestClient, username_suffix: str, db_session: Session | None = None
) -> tuple[UUID, str]:
    """Create a user and log them in. Returns (user_id, token).
    If db_session is provided, verify email in DB so user can create global parts.
    """
    username = f"brand_user_{username_suffix}"
    email = f"brand_user_{username_suffix}@example.com"
    password = "testpassword"

    user_data = {"username": username, "email": email, "password": password}
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    user_id: UUID | None = None
    if response.status_code == 200:
        user_id = UUID(response.json()["id"])
    elif response.status_code == 400 and "already registered" in response.json().get("detail", ""):
        pass
    else:
        response.raise_for_status()

    if db_session is not None:
        user = db_session.query(DBUser).filter(DBUser.username == username).first()
        if user:
            user.email_verified = True
            db_session.commit()

    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert token_response.status_code == 200, f"Failed to login user: {token_response.text}"
    token = token_response.json()["access_token"]

    if user_id is None:
        headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get(f"{settings.API_STR}/users/me", headers=headers)
        assert me_response.status_code == 200
        user_id = UUID(me_response.json()["id"])
    return user_id, token


def create_brand_via_api(client: TestClient, token: str, name: str, description: str | None = None) -> dict[str, Any]:
    """Create a brand via API and return the response JSON."""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"name": name, "description": description, "is_active": True}
    response = client.post(f"{settings.API_STR}/brands/", json=payload, headers=headers)
    assert response.status_code == 200, f"Failed to create brand: {response.text}"
    return response.json()


class TestBrands:
    """Test cases for brand endpoints."""

    def test_get_brands_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting all active brands (public)."""
        response = client.get(f"{settings.API_STR}/brands/")
        assert response.status_code == 200
        brands: list[Any] = response.json()
        assert isinstance(brands, list)
        for b in brands:
            assert "id" in b
            assert "name" in b
            assert b.get("is_active", True) is True

    def test_get_brands_active_only_param(self, client: TestClient, db_session: Session) -> None:
        """Test get brands with active_only=false returns all brands."""
        _, token = create_and_login_user(client, "brands_all")
        create_brand_via_api(client, token, get_unique_name("inactive_brand"))

        # Create inactive brand via DB (no API for is_active=False on create)
        inactive = DBBrand(
            name=get_unique_name("inactive"),
            description="Inactive",
            is_active=False,
        )
        db_session.add(inactive)
        db_session.commit()
        db_session.refresh(inactive)

        response = client.get(f"{settings.API_STR}/brands/?active_only=false")
        assert response.status_code == 200
        brands = response.json()
        names = [b["name"] for b in brands]
        assert inactive.name in names

    def test_get_brand_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting a specific brand (public)."""
        _, token = create_and_login_user(client, "get_one")
        created = create_brand_via_api(client, token, get_unique_name("get_one"))
        brand_id = created["id"]

        response = client.get(f"{settings.API_STR}/brands/{brand_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == brand_id
        assert data["name"] == created["name"]

    def test_get_brand_not_found(self, client: TestClient) -> None:
        """Test getting a non-existent brand."""
        response = client.get(f"{settings.API_STR}/brands/{INVALID_UUID_STR}")
        assert response.status_code == 404
        msg = response.json().get("message", response.json().get("detail", ""))
        assert "brand" in msg.lower() and "not found" in msg.lower()

    def test_search_brands_success(self, client: TestClient, db_session: Session) -> None:
        """Test searching brands by name (public)."""
        _, token = create_and_login_user(client, "search")
        create_brand_via_api(client, token, get_unique_name("AcmeParts"), "Acme parts")

        response = client.get(
            f"{settings.API_STR}/brands/search",
            params={"q": "Acme", "skip": 0, "limit": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_brands_missing_q(self, client: TestClient) -> None:
        """Test search requires q parameter."""
        response = client.get(f"{settings.API_STR}/brands/search", params={"skip": 0, "limit": 10})
        assert response.status_code == 422

    def test_create_brand_success(self, client: TestClient, db_session: Session) -> None:
        """Test creating a brand as authenticated user (non-admin)."""
        _, token = create_and_login_user(client, "create")
        headers = {"Authorization": f"Bearer {token}"}

        name = get_unique_name("NewBrand")
        payload = {"name": name, "description": "A new brand", "is_active": True}

        response = client.post(f"{settings.API_STR}/brands/", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == name
        assert data["description"] == "A new brand"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_brand_duplicate_returns_existing(self, client: TestClient, db_session: Session) -> None:
        """Test creating a brand with existing name returns existing brand (case-insensitive)."""
        _, token = create_and_login_user(client, "dup")
        name = get_unique_name("DupBrand")
        first = create_brand_via_api(client, token, name)
        first_id = first["id"]

        # Create again with same name (case variation)
        second = create_brand_via_api(client, token, name.upper())
        assert second["id"] == first_id
        assert second["name"] == first["name"]

    def test_create_brand_unauthorized(self, client: TestClient) -> None:
        """Test creating a brand without auth returns 401."""
        payload = {"name": get_unique_name("NoAuth"), "is_active": True}
        response = client.post(f"{settings.API_STR}/brands/", json=payload)
        assert response.status_code == 401

    def test_update_brand_success(self, client: TestClient, db_session: Session) -> None:
        """Test updating a brand (admin only)."""
        _, user_token = create_and_login_user(client, "update_creator")
        created = create_brand_via_api(client, user_token, get_unique_name("ToUpdate"))

        _, admin_token = create_and_login_admin_user(client, db_session, "update_admin")
        headers = {"Authorization": f"Bearer {admin_token}"}

        update_data = {
            "name": get_unique_name("UpdatedName"),
            "description": "Updated description",
        }
        response = client.put(
            f"{settings.API_STR}/brands/{created['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    def test_update_brand_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Test updating a brand as non-admin returns 403."""
        _, token = create_and_login_user(client, "update_forbidden")
        created = create_brand_via_api(client, token, get_unique_name("NoUpdate"))
        headers = {"Authorization": f"Bearer {token}"}

        response = client.put(
            f"{settings.API_STR}/brands/{created['id']}",
            json={"description": "Hacked"},
            headers=headers,
        )
        assert response.status_code == 403

    def test_update_brand_not_found(self, client: TestClient, db_session: Session) -> None:
        """Test updating a non-existent brand."""
        _, token = create_and_login_admin_user(client, db_session, "update_nf")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put(
            f"{settings.API_STR}/brands/{INVALID_UUID_STR}",
            json={"description": "Missing"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_delete_brand_success(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a brand (admin only)."""
        _, user_token = create_and_login_user(client, "delete_creator")
        created = create_brand_via_api(client, user_token, get_unique_name("ToDelete"))

        _, admin_token = create_and_login_admin_user(client, db_session, "delete_admin")
        headers = {"Authorization": f"Bearer {admin_token}"}

        response = client.delete(f"{settings.API_STR}/brands/{created['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]

        get_resp = client.get(f"{settings.API_STR}/brands/{created['id']}")
        assert get_resp.status_code == 404

    def test_delete_brand_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a brand as non-admin returns 403."""
        _, token = create_and_login_user(client, "delete_forbidden")
        created = create_brand_via_api(client, token, get_unique_name("NoDelete"))
        headers = {"Authorization": f"Bearer {token}"}

        response = client.delete(f"{settings.API_STR}/brands/{created['id']}", headers=headers)
        assert response.status_code == 403

    def test_delete_brand_not_found(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a non-existent brand."""
        _, token = create_and_login_admin_user(client, db_session, "delete_nf")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.delete(f"{settings.API_STR}/brands/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 404

    def test_delete_brand_with_parts_fails(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a brand that has parts returns 409."""
        _, user_token = create_and_login_user(client, "delete_with_parts", db_session)
        created = create_brand_via_api(client, user_token, get_unique_name("BrandWithParts"))
        brand_id = created["id"]
        category_id = str(get_default_category_id(db_session))
        headers = {"Authorization": f"Bearer {user_token}"}

        part_data = {
            "name": get_unique_name("PartForBrand"),
            "description": "Part",
            "category_id": category_id,
            "brand_id": brand_id,
        }
        part_resp = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert part_resp.status_code == 200

        _, admin_token = create_and_login_admin_user(client, db_session, "delete_wp_admin")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.delete(f"{settings.API_STR}/brands/{brand_id}", headers=admin_headers)
        assert response.status_code == 409
        body = response.json()
        detail = body.get("detail", body.get("message", ""))
        assert "associated parts" in detail.lower() or "cannot delete" in detail.lower()

    def test_get_global_parts_by_brand_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting global parts by brand (public)."""
        _, token = create_and_login_user(client, "parts_by_brand", db_session)
        created = create_brand_via_api(client, token, get_unique_name("BrandForParts"))
        brand_id = created["id"]
        category_id = str(get_default_category_id(db_session))
        headers = {"Authorization": f"Bearer {token}"}

        part_data = {
            "name": get_unique_name("PartInBrand"),
            "description": "Part",
            "category_id": category_id,
            "brand_id": brand_id,
        }
        client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)

        response = client.get(f"{settings.API_STR}/brands/{brand_id}/global-parts")
        assert response.status_code == 200
        parts = response.json()
        assert isinstance(parts, list)
        assert len(parts) >= 1
        assert all(p["brand_id"] == brand_id for p in parts)

    def test_get_global_parts_by_brand_pagination(self, client: TestClient, db_session: Session) -> None:
        """Test pagination for parts by brand."""
        _, token = create_and_login_user(client, "parts_pag", db_session)
        created = create_brand_via_api(client, token, get_unique_name("BrandPag"))
        brand_id = created["id"]
        category_id = str(get_default_category_id(db_session))
        headers = {"Authorization": f"Bearer {token}"}

        for i in range(3):
            part_data = {
                "name": get_unique_name(f"PartPag_{i}"),
                "description": f"Part {i}",
                "category_id": category_id,
                "brand_id": brand_id,
            }
            client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)

        response = client.get(
            f"{settings.API_STR}/brands/{brand_id}/global-parts",
            params={"skip": 1, "limit": 2},
        )
        assert response.status_code == 200
        parts = response.json()
        assert len(parts) <= 2

    def test_get_brand_parts_count_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting parts count for a brand (public)."""
        _, token = create_and_login_user(client, "count_user", db_session)
        created = create_brand_via_api(client, token, get_unique_name("BrandCount"))
        brand_id = created["id"]
        category_id = str(get_default_category_id(db_session))
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get(f"{settings.API_STR}/brands/{brand_id}/parts-count")
        assert response.status_code == 200
        data = response.json()
        assert "parts_count" in data
        initial = data["parts_count"]
        assert isinstance(initial, int)
        assert initial >= 0

        part_data = {
            "name": get_unique_name("PartCount"),
            "description": "Part",
            "category_id": category_id,
            "brand_id": brand_id,
        }
        client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)

        response = client.get(f"{settings.API_STR}/brands/{brand_id}/parts-count")
        assert response.status_code == 200
        assert response.json()["parts_count"] == initial + 1

    def test_get_brand_parts_count_not_found(self, client: TestClient) -> None:
        """Test parts count for non-existent brand."""
        response = client.get(f"{settings.API_STR}/brands/{INVALID_UUID_STR}/parts-count")
        assert response.status_code == 404

    def test_count_brands_success(self, client: TestClient, db_session: Session) -> None:
        """Test counting brands (public)."""
        response = client.get(f"{settings.API_STR}/brands/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        initial = data["count"]
        assert isinstance(initial, int)
        assert initial >= 0

        _, token = create_and_login_user(client, "count_inc")
        create_brand_via_api(client, token, get_unique_name("CountInc"))

        response = client.get(f"{settings.API_STR}/brands/count")
        assert response.status_code == 200
        assert response.json()["count"] == initial + 1

    def test_count_brands_public(self, client: TestClient) -> None:
        """Test count works without authentication."""
        client.cookies.clear()
        response = client.get(f"{settings.API_STR}/brands/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
