"""Tests for retailer entity endpoints."""

import os
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.brand import Brand as DBBrand
from app.api.models.part_listing import PartListing
from app.api.models.retailer import Retailer as DBRetailer
from app.api.models.user import User as DBUser
from app.core.config import settings
from tests.conftest import get_default_category_id


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def create_and_login_admin_user(
    client: TestClient, db_session: Session, username_suffix: str = "admin"
) -> tuple[dict[str, Any], str]:
    """Create an admin user and log them in. Returns (user_dict, token)."""
    username = f"retailer_admin_{username_suffix}"
    email = f"retailer_admin_{username_suffix}@example.com"
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
) -> tuple[int, str]:
    """Create a user and log them in. Returns (user_id, token)."""
    username = f"retailer_user_{username_suffix}"
    email = f"retailer_user_{username_suffix}@example.com"
    password = "testpassword"

    user_data = {"username": username, "email": email, "password": password}
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    user_id = -1
    if response.status_code == 200:
        user_id = response.json()["id"]
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

    if user_id == -1:
        headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get(f"{settings.API_STR}/users/me", headers=headers)
        assert me_response.status_code == 200
        user_id = me_response.json()["id"]
    return user_id, token


def create_retailer_via_api(
    client: TestClient, token: str, name: str, domain: str | None = None, base_url: str | None = None
) -> dict[str, Any]:
    """Create a retailer via API (admin) and return the response JSON."""
    headers = {"Authorization": f"Bearer {token}"}
    payload: dict[str, Any] = {"name": name, "is_active": True}
    if domain is not None:
        payload["domain"] = domain
    if base_url is not None:
        payload["base_url"] = base_url
    response = client.post(f"{settings.API_STR}/retailers/", json=payload, headers=headers)
    assert response.status_code == 200, f"Failed to create retailer: {response.text}"
    return response.json()


class TestRetailers:
    """Test cases for retailer endpoints."""

    def test_get_retailers_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting all retailers (public, default active_only=True)."""
        response = client.get(f"{settings.API_STR}/retailers/")
        assert response.status_code == 200
        retailers: list[Any] = response.json()
        assert isinstance(retailers, list)
        for r in retailers:
            assert "id" in r
            assert "name" in r
            assert r.get("is_active", True) is True

    def test_get_retailers_active_only_param(self, client: TestClient, db_session: Session) -> None:
        """Test get retailers with active_only=false returns all retailers."""
        _, admin_token = create_and_login_admin_user(client, db_session, "list_all")
        create_retailer_via_api(client, admin_token, get_unique_name("active_ret"))

        inactive = DBRetailer(
            name=get_unique_name("inactive_ret"),
            domain=get_unique_name("inactive.com"),
            is_active=False,
        )
        db_session.add(inactive)
        db_session.commit()
        db_session.refresh(inactive)

        response = client.get(f"{settings.API_STR}/retailers/?active_only=false")
        assert response.status_code == 200
        retailers = response.json()
        names = [r["name"] for r in retailers]
        assert inactive.name in names

    def test_get_retailer_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting a specific retailer (public)."""
        _, admin_token = create_and_login_admin_user(client, db_session, "get_one")
        created = create_retailer_via_api(
            client, admin_token, get_unique_name("get_one"), domain=get_unique_name("getone.com")
        )
        retailer_id = created["id"]

        response = client.get(f"{settings.API_STR}/retailers/{retailer_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == retailer_id
        assert data["name"] == created["name"]

    def test_get_retailer_not_found(self, client: TestClient) -> None:
        """Test getting a non-existent retailer."""
        response = client.get(f"{settings.API_STR}/retailers/99999")
        assert response.status_code == 404
        msg = response.json().get("message", response.json().get("detail", ""))
        assert "retailer" in msg.lower() and "not found" in msg.lower()

    def test_post_get_or_create_success_new(self, client: TestClient, db_session: Session) -> None:
        """Test get-or-create creates new retailer when domain does not exist (authenticated)."""
        _, token = create_and_login_user(client, "getorcreate", db_session)
        headers = {"Authorization": f"Bearer {token}"}

        domain = get_unique_name("newshop.com")
        payload = {"domain": domain, "name": "New Shop"}

        response = client.post(f"{settings.API_STR}/retailers/get-or-create", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == domain
        assert data["name"] == "New Shop"
        assert "id" in data

    def test_post_get_or_create_success_existing(self, client: TestClient, db_session: Session) -> None:
        """Test get-or-create returns existing retailer when domain exists."""
        _, token = create_and_login_user(client, "getorcreate_existing", db_session)
        headers = {"Authorization": f"Bearer {token}"}

        domain = get_unique_name("existingshop.com")
        payload = {"domain": domain, "name": "Existing Shop"}

        first = client.post(f"{settings.API_STR}/retailers/get-or-create", json=payload, headers=headers)
        assert first.status_code == 200
        first_data = first.json()
        first_id = first_data["id"]

        second = client.post(f"{settings.API_STR}/retailers/get-or-create", json=payload, headers=headers)
        assert second.status_code == 200
        second_data = second.json()
        assert second_data["id"] == first_id

    def test_post_get_or_create_derives_name_from_domain(self, client: TestClient, db_session: Session) -> None:
        """Test get-or-create derives name from domain when name omitted."""
        _, token = create_and_login_user(client, "derive_name", db_session)
        headers = {"Authorization": f"Bearer {token}"}

        domain = get_unique_name("a90shop.com")
        payload = {"domain": domain}

        response = client.post(f"{settings.API_STR}/retailers/get-or-create", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == domain
        assert data["name"]  # Derived from domain (e.g., A90shop)

    def test_post_get_or_create_empty_domain_returns_400(self, client: TestClient, db_session: Session) -> None:
        """Test get-or-create with empty domain returns 400."""
        _, token = create_and_login_user(client, "empty_domain", db_session)
        headers = {"Authorization": f"Bearer {token}"}

        payload = {"domain": "   "}
        response = client.post(f"{settings.API_STR}/retailers/get-or-create", json=payload, headers=headers)
        assert response.status_code == 400
        body = response.json()
        msg = (body.get("message") or body.get("detail") or "").lower()
        assert "domain" in msg or "required" in msg

    def test_post_get_or_create_unauthorized(self, client: TestClient) -> None:
        """Test get-or-create without auth returns 401."""
        payload = {"domain": "shop.com", "name": "Shop"}
        response = client.post(f"{settings.API_STR}/retailers/get-or-create", json=payload)
        assert response.status_code == 401

    def test_create_retailer_success(self, client: TestClient, db_session: Session) -> None:
        """Test creating a retailer (admin only)."""
        _, admin_token = create_and_login_admin_user(client, db_session, "create")
        headers = {"Authorization": f"Bearer {admin_token}"}

        name = get_unique_name("NewRetailer")
        domain = get_unique_name("newretailer.com")
        payload = {"name": name, "domain": domain, "base_url": "https://www.example.com", "is_active": True}

        response = client.post(f"{settings.API_STR}/retailers/", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == name
        assert data["domain"] == domain
        assert data["base_url"] == "https://www.example.com"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_retailer_unauthorized(self, client: TestClient) -> None:
        """Test creating a retailer without auth returns 401."""
        payload = {"name": get_unique_name("NoAuth"), "is_active": True}
        response = client.post(f"{settings.API_STR}/retailers/", json=payload)
        assert response.status_code == 401

    def test_create_retailer_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Test creating a retailer as non-admin returns 403."""
        _, token = create_and_login_user(client, "create_forbidden", db_session)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"name": get_unique_name("NoCreate"), "is_active": True}
        response = client.post(f"{settings.API_STR}/retailers/", json=payload, headers=headers)
        assert response.status_code == 403

    def test_create_retailer_duplicate_domain_returns_409(self, client: TestClient, db_session: Session) -> None:
        """Test creating a retailer with existing domain returns 409."""
        _, admin_token = create_and_login_admin_user(client, db_session, "dup")
        domain = get_unique_name("dupdomain.com")
        create_retailer_via_api(client, admin_token, get_unique_name("First"), domain=domain)

        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = {"name": get_unique_name("Second"), "domain": domain, "is_active": True}
        response = client.post(f"{settings.API_STR}/retailers/", json=payload, headers=headers)
        assert response.status_code == 409
        body = response.json()
        detail = str(body.get("detail", body.get("message", ""))).lower()
        assert "domain" in detail or "duplicate" in detail or "exists" in detail

    def test_update_retailer_success(self, client: TestClient, db_session: Session) -> None:
        """Test updating a retailer (admin only)."""
        _, admin_token = create_and_login_admin_user(client, db_session, "update")
        created = create_retailer_via_api(
            client, admin_token, get_unique_name("ToUpdate"), domain=get_unique_name("toupdate.com")
        )
        headers = {"Authorization": f"Bearer {admin_token}"}

        update_data = {"name": get_unique_name("UpdatedName"), "base_url": "https://updated.com"}
        response = client.put(
            f"{settings.API_STR}/retailers/{created['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["base_url"] == update_data["base_url"]

    def test_update_retailer_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Test updating a retailer as non-admin returns 403."""
        _, admin_token = create_and_login_admin_user(client, db_session, "update_creator")
        created = create_retailer_via_api(
            client, admin_token, get_unique_name("NoUpdate"), domain=get_unique_name("noupdate.com")
        )
        _, user_token = create_and_login_user(client, "update_forbidden", db_session)
        headers = {"Authorization": f"Bearer {user_token}"}

        response = client.put(
            f"{settings.API_STR}/retailers/{created['id']}",
            json={"name": "Hacked"},
            headers=headers,
        )
        assert response.status_code == 403

    def test_update_retailer_not_found(self, client: TestClient, db_session: Session) -> None:
        """Test updating a non-existent retailer."""
        _, admin_token = create_and_login_admin_user(client, db_session, "update_nf")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.put(
            f"{settings.API_STR}/retailers/99999",
            json={"name": "Missing"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_update_retailer_duplicate_domain_returns_409(self, client: TestClient, db_session: Session) -> None:
        """Test updating retailer to existing domain returns 409."""
        _, admin_token = create_and_login_admin_user(client, db_session, "dup_update")
        first = create_retailer_via_api(
            client, admin_token, get_unique_name("FirstRet"), domain=get_unique_name("firstret.com")
        )
        second = create_retailer_via_api(
            client, admin_token, get_unique_name("SecondRet"), domain=get_unique_name("secondret.com")
        )
        headers = {"Authorization": f"Bearer {admin_token}"}

        response = client.put(
            f"{settings.API_STR}/retailers/{second['id']}",
            json={"domain": first["domain"]},
            headers=headers,
        )
        assert response.status_code == 409

    def test_delete_retailer_success(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a retailer (admin only)."""
        _, admin_token = create_and_login_admin_user(client, db_session, "delete")
        created = create_retailer_via_api(
            client, admin_token, get_unique_name("ToDelete"), domain=get_unique_name("todelete.com")
        )
        headers = {"Authorization": f"Bearer {admin_token}"}

        response = client.delete(f"{settings.API_STR}/retailers/{created['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]

        get_resp = client.get(f"{settings.API_STR}/retailers/{created['id']}")
        assert get_resp.status_code == 404

    def test_delete_retailer_forbidden_non_admin(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a retailer as non-admin returns 403."""
        _, admin_token = create_and_login_admin_user(client, db_session, "delete_creator")
        created = create_retailer_via_api(
            client, admin_token, get_unique_name("NoDelete"), domain=get_unique_name("nodelete.com")
        )
        _, user_token = create_and_login_user(client, "delete_forbidden", db_session)
        headers = {"Authorization": f"Bearer {user_token}"}

        response = client.delete(f"{settings.API_STR}/retailers/{created['id']}", headers=headers)
        assert response.status_code == 403

    def test_delete_retailer_not_found(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a non-existent retailer."""
        _, admin_token = create_and_login_admin_user(client, db_session, "delete_nf")
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.delete(f"{settings.API_STR}/retailers/99999", headers=headers)
        assert response.status_code == 404

    def test_delete_retailer_with_part_listings_fails(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a retailer that has part listings returns 409."""
        _, admin_token = create_and_login_admin_user(client, db_session, "delete_with_listings")
        created = create_retailer_via_api(
            client, admin_token, get_unique_name("RetWithListings"), domain=get_unique_name("retwithlistings.com")
        )
        retailer_id = created["id"]

        # Create brand for global part
        brand = DBBrand(name=get_unique_name("RetBrand"), description="Brand", is_active=True)
        db_session.add(brand)
        db_session.commit()
        db_session.refresh(brand)

        # Create global part and part listing
        _, user_token = create_and_login_user(client, "ret_listings_user", db_session)
        category_id = get_default_category_id(db_session)
        part_data = {
            "name": get_unique_name("PartForListing"),
            "description": "Part",
            "category_id": category_id,
            "brand_id": brand.id,
        }
        part_resp = client.post(
            f"{settings.API_STR}/global-parts/", json=part_data, headers={"Authorization": f"Bearer {user_token}"}
        )
        assert part_resp.status_code == 200, f"Failed to create part: {part_resp.text}"
        global_part = part_resp.json()

        listing = PartListing(
            global_part_id=global_part["id"],
            retailer_id=retailer_id,
            product_url="https://example.com/part",
        )
        db_session.add(listing)
        db_session.commit()

        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.delete(f"{settings.API_STR}/retailers/{retailer_id}", headers=headers)
        assert response.status_code == 409
        body = response.json()
        detail = str(body.get("detail", body.get("message", ""))).lower()
        assert "listing" in detail or "cannot delete" in detail or "in use" in detail
