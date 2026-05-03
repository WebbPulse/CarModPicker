"""Tests for part_manufacturer entity endpoints."""

import os
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.part_manufacturer import PartManufacturer as DBPartManufacturer
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
    username = f"part_manufacturer_admin_{username_suffix}"
    email = f"part_manufacturer_admin_{username_suffix}@example.com"
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
    username = f"part_manufacturer_user_{username_suffix}"
    email = f"part_manufacturer_user_{username_suffix}@example.com"
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


def create_part_manufacturer_via_api(
    client: TestClient, token: str, name: str, description: str | None = None
) -> dict[str, Any]:
    """Create a part_manufacturer via API and return the response JSON."""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"name": name, "description": description, "is_active": True}
    response = client.post(f"{settings.API_STR}/part-manufacturers/", json=payload, headers=headers)
    assert response.status_code == 200, f"Failed to create part_manufacturer: {response.text}"
    return response.json()


class TestPartManufacturers:
    """Test cases for part_manufacturer endpoints."""

    def test_get_part_manufacturers_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting all active part_manufacturers (public)."""
        response = client.get(f"{settings.API_STR}/part-manufacturers/")
        assert response.status_code == 200
        part_manufacturers: list[Any] = response.json()
        assert isinstance(part_manufacturers, list)
        for b in part_manufacturers:
            assert "id" in b
            assert "name" in b
            assert b.get("is_active", True) is True

    def test_get_part_manufacturers_active_only_param(self, client: TestClient, db_session: Session) -> None:
        """Test get part_manufacturers with active_only=false returns all curated part_manufacturers."""
        _, token = create_and_login_user(client, "part_manufacturers_all")
        create_part_manufacturer_via_api(client, token, get_unique_name("inactive_part_manufacturer"))

        # Create inactive curated mfr via DB. The list endpoint defaults to
        # curated-only (UGC entries are excluded from catalog browse), so the
        # row must be flagged is_curated=True to appear here.
        inactive = DBPartManufacturer(
            name=get_unique_name("inactive"),
            description="Inactive",
            is_active=False,
            is_curated=True,
        )
        db_session.add(inactive)
        db_session.commit()
        db_session.refresh(inactive)

        response = client.get(f"{settings.API_STR}/part-manufacturers/?active_only=false")
        assert response.status_code == 200
        part_manufacturers = response.json()
        names = [b["name"] for b in part_manufacturers]
        assert inactive.name in names

    def test_get_part_manufacturer_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting a specific part_manufacturer (public)."""
        _, token = create_and_login_user(client, "get_one")
        created = create_part_manufacturer_via_api(client, token, get_unique_name("get_one"))
        part_manufacturer_id = created["id"]

        response = client.get(f"{settings.API_STR}/part-manufacturers/{part_manufacturer_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == part_manufacturer_id
        assert data["name"] == created["name"]

    def test_get_part_manufacturer_not_found(self, client: TestClient) -> None:
        """Test getting a non-existent part_manufacturer."""
        response = client.get(f"{settings.API_STR}/part-manufacturers/{INVALID_UUID_STR}")
        assert response.status_code == 404
        msg = response.json().get("message", response.json().get("detail", ""))
        assert "part manufacturer" in msg.lower() and "not found" in msg.lower()

    def test_search_part_manufacturers_success(self, client: TestClient, db_session: Session) -> None:
        """Test searching part_manufacturers by name (public)."""
        _, token = create_and_login_user(client, "search")
        create_part_manufacturer_via_api(client, token, get_unique_name("AcmeParts"), "Acme parts")

        response = client.get(
            f"{settings.API_STR}/part-manufacturers/search",
            params={"q": "Acme", "skip": 0, "limit": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_part_manufacturers_missing_q(self, client: TestClient) -> None:
        """Test search requires q parameter."""
        response = client.get(f"{settings.API_STR}/part-manufacturers/search", params={"skip": 0, "limit": 10})
        assert response.status_code == 422

    def test_create_part_manufacturer_success(self, client: TestClient, db_session: Session) -> None:
        """Test creating a part_manufacturer as authenticated user (non-admin)."""
        _, token = create_and_login_user(client, "create")
        headers = {"Authorization": f"Bearer {token}"}

        name = get_unique_name("NewPartManufacturer")
        payload = {"name": name, "description": "A new part_manufacturer", "is_active": True}

        response = client.post(f"{settings.API_STR}/part-manufacturers/", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == name
        assert data["description"] == "A new part_manufacturer"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_part_manufacturer_duplicate_returns_existing(self, client: TestClient, db_session: Session) -> None:
        """Test creating a part_manufacturer with existing name returns existing part_manufacturer (case-insensitive)."""
        _, token = create_and_login_user(client, "dup")
        name = get_unique_name("DupPartManufacturer")
        first = create_part_manufacturer_via_api(client, token, name)
        first_id = first["id"]

        # Create again with same name (case variation)
        second = create_part_manufacturer_via_api(client, token, name.upper())
        assert second["id"] == first_id
        assert second["name"] == first["name"]

    def test_create_part_manufacturer_unauthorized(self, client: TestClient) -> None:
        """Test creating a part_manufacturer without auth returns 401."""
        payload = {"name": get_unique_name("NoAuth"), "is_active": True}
        response = client.post(f"{settings.API_STR}/part-manufacturers/", json=payload)
        assert response.status_code == 401

    def test_update_part_manufacturer_success(self, client: TestClient, db_session: Session) -> None:
        """Test updating a part_manufacturer (admin only)."""
        _, user_token = create_and_login_user(client, "update_creator")
        created = create_part_manufacturer_via_api(client, user_token, get_unique_name("ToUpdate"))

        _, admin_token = create_and_login_admin_user(client, db_session, "update_admin")
        headers = {"Authorization": f"Bearer {admin_token}"}

        update_data = {
            "name": get_unique_name("UpdatedName"),
            "description": "Updated description",
        }
        response = client.put(
            f"{settings.API_STR}/part-manufacturers/{created['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    def test_update_part_manufacturer_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Non-admin who is NOT the creator can't update a UGC manufacturer."""
        _, creator_token = create_and_login_user(client, "update_forbidden_creator")
        created = create_part_manufacturer_via_api(client, creator_token, get_unique_name("NoUpdate"))

        _, other_token = create_and_login_user(client, "update_forbidden_other")
        headers = {"Authorization": f"Bearer {other_token}"}

        response = client.put(
            f"{settings.API_STR}/part-manufacturers/{created['id']}",
            json={"description": "Hacked"},
            headers=headers,
        )
        assert response.status_code == 403

    def test_update_part_manufacturer_curated_forbidden_non_admin(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Non-admin can't edit curated (catalog) manufacturers — those are admin-only."""
        curated = DBPartManufacturer(
            name=get_unique_name("CuratedNoEdit"),
            description="Curated",
            is_active=True,
            is_curated=True,
        )
        db_session.add(curated)
        db_session.commit()
        db_session.refresh(curated)

        _, token = create_and_login_user(client, "update_curated_forbidden")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put(
            f"{settings.API_STR}/part-manufacturers/{curated.id}",
            json={"description": "Hacked"},
            headers=headers,
        )
        assert response.status_code == 403

    def test_update_part_manufacturer_not_found(self, client: TestClient, db_session: Session) -> None:
        """Test updating a non-existent part_manufacturer."""
        _, token = create_and_login_admin_user(client, db_session, "update_nf")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.put(
            f"{settings.API_STR}/part-manufacturers/{INVALID_UUID_STR}",
            json={"description": "Missing"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_delete_part_manufacturer_success(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a part_manufacturer (admin only)."""
        _, user_token = create_and_login_user(client, "delete_creator")
        created = create_part_manufacturer_via_api(client, user_token, get_unique_name("ToDelete"))

        _, admin_token = create_and_login_admin_user(client, db_session, "delete_admin")
        headers = {"Authorization": f"Bearer {admin_token}"}

        response = client.delete(f"{settings.API_STR}/part-manufacturers/{created['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]

        get_resp = client.get(f"{settings.API_STR}/part-manufacturers/{created['id']}")
        assert get_resp.status_code == 404

    def test_delete_part_manufacturer_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Non-admin who is NOT the creator can't delete a UGC manufacturer."""
        _, creator_token = create_and_login_user(client, "delete_forbidden_creator")
        created = create_part_manufacturer_via_api(client, creator_token, get_unique_name("NoDelete"))

        _, other_token = create_and_login_user(client, "delete_forbidden_other")
        headers = {"Authorization": f"Bearer {other_token}"}

        response = client.delete(f"{settings.API_STR}/part-manufacturers/{created['id']}", headers=headers)
        assert response.status_code == 403

    def test_delete_part_manufacturer_not_found(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a non-existent part_manufacturer."""
        _, token = create_and_login_admin_user(client, db_session, "delete_nf")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.delete(f"{settings.API_STR}/part-manufacturers/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 404

    def test_delete_part_manufacturer_with_parts_fails(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a part_manufacturer that has parts returns 409."""
        _, user_token = create_and_login_user(client, "delete_with_parts", db_session)
        created = create_part_manufacturer_via_api(client, user_token, get_unique_name("PartManufacturerWithParts"))
        part_manufacturer_id = created["id"]
        category_id = str(get_default_category_id(db_session))
        headers = {"Authorization": f"Bearer {user_token}"}

        part_data = {
            "name": get_unique_name("PartForPartManufacturer"),
            "description": "Part",
            "category_id": category_id,
            "part_manufacturer_id": part_manufacturer_id,
        }
        part_resp = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert part_resp.status_code == 200

        _, admin_token = create_and_login_admin_user(client, db_session, "delete_wp_admin")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.delete(f"{settings.API_STR}/part-manufacturers/{part_manufacturer_id}", headers=admin_headers)
        assert response.status_code == 409
        body = response.json()
        detail = body.get("detail", body.get("message", ""))
        assert "associated parts" in detail.lower() or "cannot delete" in detail.lower()

    def test_get_parts_by_part_manufacturer_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting global parts by part_manufacturer (public)."""
        _, token = create_and_login_user(client, "parts_by_part_manufacturer", db_session)
        created = create_part_manufacturer_via_api(client, token, get_unique_name("PartManufacturerForParts"))
        part_manufacturer_id = created["id"]
        category_id = str(get_default_category_id(db_session))
        headers = {"Authorization": f"Bearer {token}"}

        part_data = {
            "name": get_unique_name("PartInPartManufacturer"),
            "description": "Part",
            "category_id": category_id,
            "part_manufacturer_id": part_manufacturer_id,
        }
        client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)

        response = client.get(f"{settings.API_STR}/part-manufacturers/{part_manufacturer_id}/parts")
        assert response.status_code == 200
        parts = response.json()
        assert isinstance(parts, list)
        assert len(parts) >= 1
        assert all(p["part_manufacturer_id"] == part_manufacturer_id for p in parts)

    def test_get_parts_by_part_manufacturer_pagination(self, client: TestClient, db_session: Session) -> None:
        """Test pagination for parts by part_manufacturer."""
        _, token = create_and_login_user(client, "parts_pag", db_session)
        created = create_part_manufacturer_via_api(client, token, get_unique_name("PartManufacturerPag"))
        part_manufacturer_id = created["id"]
        category_id = str(get_default_category_id(db_session))
        headers = {"Authorization": f"Bearer {token}"}

        for i in range(3):
            part_data = {
                "name": get_unique_name(f"PartPag_{i}"),
                "description": f"Part {i}",
                "category_id": category_id,
                "part_manufacturer_id": part_manufacturer_id,
            }
            client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)

        response = client.get(
            f"{settings.API_STR}/part-manufacturers/{part_manufacturer_id}/parts",
            params={"skip": 1, "limit": 2},
        )
        assert response.status_code == 200
        parts = response.json()
        assert len(parts) <= 2

    def test_get_part_manufacturer_parts_count_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting parts count for a part_manufacturer (public)."""
        _, token = create_and_login_user(client, "count_user", db_session)
        created = create_part_manufacturer_via_api(client, token, get_unique_name("PartManufacturerCount"))
        part_manufacturer_id = created["id"]
        category_id = str(get_default_category_id(db_session))
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get(f"{settings.API_STR}/part-manufacturers/{part_manufacturer_id}/parts-count")
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
            "part_manufacturer_id": part_manufacturer_id,
        }
        client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)

        response = client.get(f"{settings.API_STR}/part-manufacturers/{part_manufacturer_id}/parts-count")
        assert response.status_code == 200
        assert response.json()["parts_count"] == initial + 1

    def test_get_part_manufacturer_parts_count_not_found(self, client: TestClient) -> None:
        """Test parts count for non-existent part_manufacturer."""
        response = client.get(f"{settings.API_STR}/part-manufacturers/{INVALID_UUID_STR}/parts-count")
        assert response.status_code == 404

    def test_count_part_manufacturers_success(self, client: TestClient, db_session: Session) -> None:
        """Test counting part_manufacturers (public)."""
        response = client.get(f"{settings.API_STR}/part-manufacturers/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        initial = data["count"]
        assert isinstance(initial, int)
        assert initial >= 0

        _, token = create_and_login_user(client, "count_inc")
        create_part_manufacturer_via_api(client, token, get_unique_name("CountInc"))

        response = client.get(f"{settings.API_STR}/part-manufacturers/count")
        assert response.status_code == 200
        assert response.json()["count"] == initial + 1

    def test_count_part_manufacturers_public(self, client: TestClient) -> None:
        """Test count works without authentication."""
        client.cookies.clear()
        response = client.get(f"{settings.API_STR}/part-manufacturers/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)

    # --- UGC vs curated boundary -----------------------------------------

    def test_create_pm_as_user_marks_ugc(self, client: TestClient, db_session: Session) -> None:
        """Regular user POST creates a UGC row owned by them."""
        user_id, token = create_and_login_user(client, "ugc_create")
        created = create_part_manufacturer_via_api(client, token, get_unique_name("MyOwnBrand"))
        assert created["is_curated"] is False
        assert created["created_by_user_id"] == str(user_id)

    def test_create_pm_as_user_dedups_into_curated(
        self, client: TestClient, db_session: Session
    ) -> None:
        """User typing a curated brand name auto-links to the curated row (no UGC dup)."""
        curated_name = get_unique_name("HKS")
        curated = DBPartManufacturer(
            name=curated_name,
            is_active=True,
            is_curated=True,
        )
        db_session.add(curated)
        db_session.commit()
        db_session.refresh(curated)

        _, token = create_and_login_user(client, "dedup_into_curated")
        # Use a case variant to also confirm case-insensitive match.
        result = create_part_manufacturer_via_api(client, token, curated_name.lower())
        assert result["id"] == str(curated.id)
        assert result["is_curated"] is True
        assert result["created_by_user_id"] is None

    def test_two_users_can_each_have_ugc_with_same_name(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Two users independently create a UGC with the same name -> two distinct rows."""
        name = get_unique_name("BarCo")
        user_a_id, token_a = create_and_login_user(client, "ugc_same_name_a")
        user_b_id, token_b = create_and_login_user(client, "ugc_same_name_b")

        a = create_part_manufacturer_via_api(client, token_a, name)
        b = create_part_manufacturer_via_api(client, token_b, name)
        assert a["id"] != b["id"]
        assert a["is_curated"] is False and b["is_curated"] is False
        assert a["created_by_user_id"] == str(user_a_id)
        assert b["created_by_user_id"] == str(user_b_id)

    def test_create_pm_as_user_dedups_into_own_ugc(
        self, client: TestClient, db_session: Session
    ) -> None:
        """A user POSTing the same name twice gets the same UGC row back."""
        _, token = create_and_login_user(client, "ugc_dedup_self")
        name = get_unique_name("FooCo")
        first = create_part_manufacturer_via_api(client, token, name)
        second = create_part_manufacturer_via_api(client, token, name)
        assert first["id"] == second["id"]

    def test_list_excludes_ugc_by_default(self, client: TestClient, db_session: Session) -> None:
        """Default list endpoint excludes UGC manufacturers (catalog browse stays clean)."""
        _, token = create_and_login_user(client, "list_excludes_ugc")
        ugc_name = get_unique_name("UgcOnly")
        ugc = create_part_manufacturer_via_api(client, token, ugc_name)
        assert ugc["is_curated"] is False

        response = client.get(f"{settings.API_STR}/part-manufacturers/")
        assert response.status_code == 200
        names = [b["name"] for b in response.json()]
        assert ugc_name not in names

    def test_list_admin_can_opt_in_to_ugc(self, client: TestClient, db_session: Session) -> None:
        """Admin can pass include_ugc=true to see UGC entries; regular user cannot."""
        _, user_token = create_and_login_user(client, "list_optin_ugc_user")
        ugc_name = get_unique_name("UgcOptIn")
        create_part_manufacturer_via_api(client, user_token, ugc_name)

        # Regular user with include_ugc=true: still excluded.
        regular_resp = client.get(
            f"{settings.API_STR}/part-manufacturers/",
            params={"include_ugc": "true"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert regular_resp.status_code == 200
        assert ugc_name not in [b["name"] for b in regular_resp.json()]

        # Admin with include_ugc=true: included.
        _, admin_token = create_and_login_admin_user(client, db_session, "list_optin_ugc_admin")
        admin_resp = client.get(
            f"{settings.API_STR}/part-manufacturers/",
            params={"include_ugc": "true"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert admin_resp.status_code == 200
        assert ugc_name in [b["name"] for b in admin_resp.json()]

    def test_search_excludes_ugc_by_default(self, client: TestClient, db_session: Session) -> None:
        """Search endpoint also defaults to curated-only."""
        _, token = create_and_login_user(client, "search_excludes_ugc")
        ugc_name = get_unique_name("UgcSearchable")
        create_part_manufacturer_via_api(client, token, ugc_name)

        response = client.get(
            f"{settings.API_STR}/part-manufacturers/search",
            params={"q": ugc_name},
        )
        assert response.status_code == 200
        assert all(b["name"] != ugc_name for b in response.json())

    def test_get_ugc_pm_still_returns_200(self, client: TestClient, db_session: Session) -> None:
        """No read boundary: a UGC row is fetchable by id by anyone."""
        _, creator_token = create_and_login_user(client, "ugc_readable_creator")
        created = create_part_manufacturer_via_api(client, creator_token, get_unique_name("UgcReadable"))

        # Anonymous fetch still works.
        client.cookies.clear()
        response = client.get(f"{settings.API_STR}/part-manufacturers/{created['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]
        assert data["is_curated"] is False

    def test_get_ugc_pm_parts_returns_only_owner_parts(
        self, client: TestClient, db_session: Session
    ) -> None:
        """GET /{id}/parts on a UGC mfr returns only the creator's parts."""
        creator_id, creator_token = create_and_login_user(client, "ugc_parts_creator", db_session)
        ugc = create_part_manufacturer_via_api(client, creator_token, get_unique_name("UgcParts"))
        category_id = str(get_default_category_id(db_session))

        # Creator adds a part.
        part_resp = client.post(
            f"{settings.API_STR}/parts/",
            json={
                "name": get_unique_name("OwnerPart"),
                "category_id": category_id,
                "part_manufacturer_id": ugc["id"],
            },
            headers={"Authorization": f"Bearer {creator_token}"},
        )
        assert part_resp.status_code == 200

        response = client.get(f"{settings.API_STR}/part-manufacturers/{ugc['id']}/parts")
        assert response.status_code == 200
        parts = response.json()
        assert all(p["user_id"] == str(creator_id) for p in parts)

    def test_creator_can_update_own_ugc(self, client: TestClient, db_session: Session) -> None:
        """A UGC row's creator can update name/description on their own row."""
        _, token = create_and_login_user(client, "ugc_creator_can_update")
        created = create_part_manufacturer_via_api(client, token, get_unique_name("MyEditable"))
        new_name = get_unique_name("MyEditableRenamed")

        response = client.put(
            f"{settings.API_STR}/part-manufacturers/{created['id']}",
            json={"name": new_name, "description": "Renamed by owner"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == new_name
        assert body["description"] == "Renamed by owner"
        assert body["is_curated"] is False

    def test_creator_cannot_promote_own_ugc(self, client: TestClient, db_session: Session) -> None:
        """A non-admin creator passing is_curated=true is silently ignored — no self-promotion."""
        _, token = create_and_login_user(client, "ugc_no_self_promote")
        created = create_part_manufacturer_via_api(client, token, get_unique_name("NoPromote"))

        response = client.put(
            f"{settings.API_STR}/part-manufacturers/{created['id']}",
            json={"is_curated": True, "description": "trying to promote"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["is_curated"] is False

    def test_counts_by_source(self, client: TestClient, db_session: Session) -> None:
        """The counts/by-source endpoint splits curated vs UGC."""
        before = client.get(f"{settings.API_STR}/part-manufacturers/counts/by-source").json()

        _, token = create_and_login_user(client, "counts_split_ugc")
        create_part_manufacturer_via_api(client, token, get_unique_name("UgcForCount"))

        after = client.get(f"{settings.API_STR}/part-manufacturers/counts/by-source").json()
        assert after["ugc"] == before["ugc"] + 1
        assert after["curated"] == before["curated"]
        assert after["total"] == before["total"] + 1
