import os
from typing import Any, Dict

from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_password_hash
from app.core.config import settings
from app.db.dynamo.catalog import Category as DBCategory
from app.db.dynamo.users import User
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import INVALID_UUID_STR, create_car_in_db, save_catalog


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def get_auth_token(client: TestClient, username: str, password: str = "testpassword") -> str:
    """Login and return the Bearer token for use in Authorization headers."""
    login_data = {"username": username, "password": password}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert response.status_code == 200
    response_data = response.json()
    assert "access_token" in response_data
    return response_data["access_token"]


def get_auth_headers(token: str) -> dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {token}"}


def create_and_login_admin_user(
    client: TestClient, db_session: Any, username_suffix: str = "admin"
) -> tuple[dict[str, Any], str]:
    """Create an admin user and log them in. Returns (user_dict, token)."""
    username = f"admin_test_{username_suffix}"
    email = f"admin_test_{username_suffix}@example.com"
    password = "testpassword"

    admin_user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            is_admin=True,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
    )

    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert token_response.status_code == 200, f"Failed to login admin user: {token_response.text}"
    token = token_response.json()["access_token"]

    return admin_user.__dict__, token


class TestBuildLists:
    """Test cases for build lists endpoints."""

    def test_create_build_list_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test successfully creating a build list."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == build_list_data["name"]
        assert data["description"] == build_list_data["description"]
        assert data["user_id"] == str(test_user.id)
        assert data["car_id"] == str(car["id"])

    def test_create_build_list_unauthorized(self, client: TestClient) -> None:
        """Test creating a build list without authentication."""
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 401

    def test_create_build_list_missing_name(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test creating a build list without providing a name."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {"description": "A test build list description", "car_id": str(car["id"])}
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 422

    def test_create_build_list_empty_name(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test creating a build list with an empty name."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": "",
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 422

    def test_create_build_list_free_user_limit_402(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Free users are limited to 1 build list; second create returns 402."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        car = create_car_in_db(db_session)
        build_list_data = {
            "name": get_unique_name("first_build_list"),
            "description": "First",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        second_data = {
            "name": get_unique_name("second_build_list"),
            "description": "Second",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=second_data, headers=headers)
        assert response.status_code == 402
        data = response.json()
        msg = data.get("detail") or data.get("message") or ""
        if isinstance(msg, list):
            msg = msg[0].get("msg", "") if msg else ""
        assert "free" in str(msg).lower() or "limit" in str(msg).lower()

    def test_create_build_list_premium_user_unlimited(
        self, client: TestClient, premium_test_user: User, db_session: Any
    ) -> None:
        """Premium users can create multiple build lists."""
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)
        car = create_car_in_db(db_session)
        for i in range(3):
            build_list_data = {
                "name": get_unique_name(f"premium_build_list_{i}"),
                "description": f"Build list {i}",
                "car_id": str(car["id"]),
            }
            response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
            assert response.status_code == 200, f"Premium user should create build list {i + 1}"

    def test_get_build_list_by_id(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving a specific build list by ID."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        created_build_list = response.json()

        response = client.get(f"{settings.API_STR}/build-lists/{created_build_list['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_build_list["id"]
        assert data["name"] == created_build_list["name"]

    def test_get_build_list_not_found(self, client: TestClient, test_user: User) -> None:
        """Test retrieving a non-existent build list."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        response = client.get(f"{settings.API_STR}/build-lists/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 404

    def test_get_build_list_unauthorized(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving a build list without authentication (public read is allowed)."""
        car = create_car_in_db(db_session)

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list_id = response.json()["id"]

        response = client.get(f"{settings.API_STR}/build-lists/{build_list_id}")
        assert response.status_code == 200

    def test_get_user_build_lists(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving build lists for the current user."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-lists/user/me", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert isinstance(data, dict)
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1

    def test_get_user_build_lists_unauthorized(self, client: TestClient) -> None:
        """Test retrieving build lists without authentication."""
        response = client.get(f"{settings.API_STR}/build-lists/user/me")
        assert response.status_code == 401

    def test_update_build_list_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test updating a build list."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        created_build_list = response.json()

        update_data = {
            "name": get_unique_name("updated_build_list"),
            "description": "Updated description",
        }
        response = client.put(
            f"{settings.API_STR}/build-lists/{created_build_list['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    def test_update_build_list_unauthorized(self, client: TestClient) -> None:
        """Test updating a build list without proper authorization."""
        update_data = {"name": "unauthorized_update"}
        response = client.put(f"{settings.API_STR}/build-lists/{INVALID_UUID_STR}", json=update_data)
        assert response.status_code == 401

    def test_delete_build_list_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test deleting a build list."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        created_build_list = response.json()

        response = client.delete(f"{settings.API_STR}/build-lists/{created_build_list['id']}", headers=headers)
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-lists/{created_build_list['id']}", headers=headers)
        assert response.status_code == 404

    def test_delete_build_list_unauthorized(self, client: TestClient) -> None:
        """Test deleting a build list without proper authorization."""
        response = client.delete(f"{settings.API_STR}/build-lists/{INVALID_UUID_STR}")
        assert response.status_code == 401

    def test_get_build_lists_by_car(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving build lists for a specific car."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-lists/car/{car['id']}", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert isinstance(data, dict)
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1
        build_list: Any
        for build_list in data["data"]:
            assert build_list["car_id"] == str(car["id"])

    def test_get_build_lists_by_car_unauthorized(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving build lists for a car (public read is allowed)."""
        car = create_car_in_db(db_session)

        response = client.get(f"{settings.API_STR}/build-lists/car/{car['id']}")
        assert response.status_code == 200

    def test_create_build_list_with_extra_fields(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test creating a build list with extra fields in the request."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
            "extra_field": "should_be_ignored",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == build_list_data["name"]
        assert data["description"] == build_list_data["description"]

    def test_create_build_list_with_malformed_json(self, client: TestClient, test_user: User) -> None:
        """Test creating a build list with malformed JSON."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        headers["Content-Type"] = "application/json"

        response = client.post(
            f"{settings.API_STR}/build-lists/",
            content="invalid json",
            headers=headers,
        )
        assert response.status_code == 422

    def test_create_build_list_with_wrong_content_type(
        self, client: TestClient, test_user: User, db_session: Any
    ) -> None:
        """Test creating a build list with wrong content type."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        headers["Content-Type"] = "text/plain"

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/",
            data=build_list_data,
            headers=headers,
        )
        assert response.status_code == 422

    def test_update_build_list_with_extra_fields(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test updating a build list with extra fields in the request."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        update_data = {
            "name": get_unique_name("updated_build_list"),
            "description": "An updated build list description",
            "extra_field": "should_be_ignored",
        }
        response = client.put(f"{settings.API_STR}/build-lists/{build_list['id']}", json=update_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    def test_update_build_list_with_malformed_json(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test updating a build list with malformed JSON."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        update_headers = get_auth_headers(token)
        update_headers["Content-Type"] = "application/json"
        response = client.put(
            f"{settings.API_STR}/build-lists/{build_list['id']}",
            content="invalid json",
            headers=update_headers,
        )
        assert response.status_code == 422

    def test_update_build_list_with_wrong_content_type(
        self, client: TestClient, test_user: User, db_session: Any
    ) -> None:
        """Test updating a build list with wrong content type."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        update_data = {
            "name": get_unique_name("updated_build_list"),
            "description": "An updated build list description",
        }
        update_headers = get_auth_headers(token)
        update_headers["Content-Type"] = "text/plain"
        response = client.put(
            f"{settings.API_STR}/build-lists/{build_list['id']}",
            data=update_data,
            headers=update_headers,
        )
        assert response.status_code == 422

    def test_create_build_list_with_disabled_user(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test creating a build list with a disabled user account."""
        test_user = UserRepository().update(test_user.id, disabled=True)

        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 400

    def test_create_build_list_with_unverified_email(
        self, client: TestClient, test_user: User, db_session: Any
    ) -> None:
        """Test creating a build list with an unverified email user account."""
        test_user = UserRepository().update(test_user.id, email_verified=False)

        car = create_car_in_db(db_session)

        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        token_data = response.json()
        assert "access_token" in token_data
        token = token_data["access_token"]
        headers = get_auth_headers(token)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 401

    def test_copy_build_list_success(self, client: TestClient, premium_test_user: User, db_session: Any) -> None:
        """Test successfully copying a build list.

        Uses premium_test_user: IN-02 closed the free-tier cap bypass on the copy
        path, so a free user who already has 1 build list (the source of the copy)
        hits the cap on the POST /copy call. Premium bypasses the cap entirely,
        which is the scenario this test actually cares about.
        """
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("original_build_list"),
            "description": "Original build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        original_build_list = response.json()

        category = DBCategory(name=get_unique_name("Test Category"))
        category = save_catalog(category)

        from app.db.dynamo.catalog import PartManufacturer as DBPartManufacturer

        part_manufacturer = DBPartManufacturer(
            name=get_unique_name("Test PartManufacturer"), description="Test part_manufacturer", is_active=True
        )
        part_manufacturer = save_catalog(part_manufacturer)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(category.id),
            "part_manufacturer_id": str(part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {"notes": "Original notes", "quantity": 2}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{original_build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        response = client.post(
            f"{settings.API_STR}/build-lists/{original_build_list['id']}/copy",
            json={},
            headers=headers,
        )
        assert response.status_code == 200
        copied_build_list = response.json()

        assert copied_build_list["id"] != original_build_list["id"]
        assert copied_build_list["name"] == f"Copy of {original_build_list['name']}"
        assert copied_build_list["description"] == original_build_list["description"]
        assert copied_build_list["car_id"] == original_build_list["car_id"]
        assert copied_build_list["user_id"] == str(premium_test_user.id)

        response = client.get(
            f"{settings.API_STR}/build-list-parts/{copied_build_list['id']}",
            headers=headers,
        )
        assert response.status_code == 200
        parts = response.json()
        assert len(parts) == 1
        assert parts[0]["part_id"] == part["id"]
        assert parts[0]["notes"] == "Original notes"
        assert parts[0]["quantity"] == 2

    def test_copy_build_list_with_custom_name(
        self, client: TestClient, premium_test_user: User, db_session: Any
    ) -> None:
        """Test copying a build list with a custom name. Uses premium_test_user per IN-02 (see test_copy_build_list_success)."""
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("original_build_list"),
            "description": "Original build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        original_build_list = response.json()

        custom_name = get_unique_name("copied_build_list")
        response = client.post(
            f"{settings.API_STR}/build-lists/{original_build_list['id']}/copy",
            json={"new_name": custom_name},
            headers=headers,
        )
        assert response.status_code == 200
        copied_build_list = response.json()

        assert copied_build_list["name"] == custom_name
        assert copied_build_list["id"] != original_build_list["id"]

    def test_copy_build_list_without_custom_name(
        self, client: TestClient, premium_test_user: User, db_session: Any
    ) -> None:
        """Test copying a build list without custom name (uses default). Uses premium_test_user per IN-02."""
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("original_build_list"),
            "description": "Original build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        original_build_list = response.json()

        response = client.post(
            f"{settings.API_STR}/build-lists/{original_build_list['id']}/copy",
            json={},
            headers=headers,
        )
        assert response.status_code == 200
        copied_build_list = response.json()

        assert copied_build_list["name"] == f"Copy of {original_build_list['name']}"

    def test_copy_build_list_not_found(self, client: TestClient, test_user: User) -> None:
        """Test copying a non-existent build list."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        response = client.post(
            f"{settings.API_STR}/build-lists/{INVALID_UUID_STR}/copy",
            json={},
            headers=headers,
        )
        assert response.status_code == 404

    def test_copy_build_list_unauthorized(self, client: TestClient) -> None:
        """Test copying a build list without authentication."""
        response = client.post(
            f"{settings.API_STR}/build-lists/{INVALID_UUID_STR}/copy",
            json={},
        )
        assert response.status_code == 401

    def test_copy_build_list_ownership(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test that copied build list is owned by the current user."""
        original_owner = UserRepository().create_user(
            DBUser(
                username=get_unique_name("original_owner"),
                email=f"{get_unique_name('original_owner')}@example.com",
                hashed_password=get_password_hash("testpassword"),
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        original_token = get_auth_token(client, original_owner.username)
        original_headers = get_auth_headers(original_token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("original_build_list"),
            "description": "Original build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=original_headers)
        assert response.status_code == 200
        original_build_list = response.json()

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        response = client.post(
            f"{settings.API_STR}/build-lists/{original_build_list['id']}/copy",
            json={},
            headers=headers,
        )
        assert response.status_code == 200
        copied_build_list = response.json()

        assert copied_build_list["user_id"] == str(test_user.id)
        assert copied_build_list["user_id"] != str(original_owner.id)

    def test_copy_free_tier_cap(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """IN-02 regression — free-tier user at the 1-list cap cannot copy to
        create a second list.

        Before IN-02 landed, ``copy_build_list`` bypassed the cap enforcement
        that ``create`` already applied — a free user could press Copy to grow
        unbounded. The service now raises 402 at the copy path too
        (``build_list_service.copy_build_list`` — see the ``Free accounts are
        limited`` block). This test pins the 402 so a future PR that removes
        or relaxes the check fails CI.
        """
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        original_data = {
            "name": get_unique_name("at_cap"),
            "description": "first and only free-tier build list",
            "car_id": str(car["id"]),
        }
        resp = client.post(f"{settings.API_STR}/build-lists/", json=original_data, headers=headers)
        assert resp.status_code == 200, resp.text
        original_id = resp.json()["id"]

        resp = client.post(
            f"{settings.API_STR}/build-lists/{original_id}/copy",
            json={"new_name": "should-fail"},
            headers=headers,
        )
        assert resp.status_code == 402, f"Expected 402 on copy at free-tier cap, got {resp.status_code}: {resp.text}"
        data = resp.json()
        msg = data.get("detail") or data.get("message") or ""
        assert (
            "Free accounts are limited to 1 build list" in msg
        ), f"Expected cap-exceeded message in 402 body, got: {data}"

        resp = client.get(
            f"{settings.API_STR}/build-lists/user/{test_user.id}",
            headers=headers,
        )
        assert resp.status_code == 200
        user_lists = resp.json()
        assert isinstance(user_lists, list), f"Expected list response, got {type(user_lists)}"
        assert len(user_lists) == 1, f"Expected exactly 1 build list after blocked copy, got {len(user_lists)}"
        assert user_lists[0]["id"] == original_id

    def test_get_build_lists_with_votes_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving build lists with vote data."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        voter = UserRepository().create_user(
            DBUser(
                username=get_unique_name("voter"),
                email=f"{get_unique_name('voter')}@example.com",
                hashed_password=get_password_hash("testpassword"),
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        voter_token = get_auth_token(client, voter.username)
        voter_headers = get_auth_headers(voter_token)

        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/build_list/{build_list['id']}",
            json=vote_data,
            headers=voter_headers,
        )
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-lists/with-votes", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()

        assert isinstance(data, dict)
        assert "data" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data

        found_build_list = None
        for bl in data["data"]:
            if bl["id"] == build_list["id"]:
                found_build_list = bl
                break

        assert found_build_list is not None
        assert "upvotes" in found_build_list
        assert "downvotes" in found_build_list
        assert "total_votes" in found_build_list
        assert found_build_list["upvotes"] == 1
        assert found_build_list["downvotes"] == 0
        assert found_build_list["total_votes"] == 1

    def test_get_build_lists_with_votes_no_votes(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test retrieving build lists with no votes."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        response = client.get(f"{settings.API_STR}/build-lists/with-votes", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()

        found_build_list = None
        for bl in data["data"]:
            if bl["id"] == build_list["id"]:
                found_build_list = bl
                break

        assert found_build_list is not None
        assert found_build_list["upvotes"] == 0
        assert found_build_list["downvotes"] == 0
        assert found_build_list["total_votes"] == 0

    def test_get_build_lists_with_votes_public_access(
        self, client: TestClient, test_user: User, db_session: Any
    ) -> None:
        """Test that build lists with votes endpoint allows public access."""
        car = create_car_in_db(db_session)

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-lists/with-votes")
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert "data" in data

    def test_get_build_lists_with_votes_pagination(
        self, client: TestClient, premium_test_user: User, db_session: Any
    ) -> None:
        """Test pagination with build lists with votes."""
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        for i in range(5):
            build_list_data = {
                "name": get_unique_name(f"test_build_list_{i}"),
                "description": f"Build list {i}",
                "car_id": str(car["id"]),
            }
            response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
            assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-lists/with-votes?skip=0&limit=2", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert len(data["data"]) <= 2
        assert "total" in data
        assert "skip" in data
        assert "limit" in data

    def test_get_build_lists_with_votes_search(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test search functionality with build lists with votes."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        unique_name = get_unique_name("searchable_build_list")
        build_list_data = {
            "name": unique_name,
            "description": "A searchable build list",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        search_term = unique_name.split("_")[0]
        response = client.get(
            f"{settings.API_STR}/build-lists/with-votes?search={search_term}",
            headers=headers,
        )
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        assert len(data["data"]) >= 1
        found = any(bl["name"] == unique_name for bl in data["data"])
        assert found

    def test_get_build_lists_with_votes_filter_by_car(
        self, client: TestClient, premium_test_user: User, db_session: Any
    ) -> None:
        """Test filtering by car_id with build lists with votes."""
        token = get_auth_token(client, premium_test_user.username)
        headers = get_auth_headers(token)

        car1 = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)
        car2 = create_car_in_db(db_session, "Honda", "Civic", "10th Gen", 2016, 2021)

        build_list_data1 = {
            "name": get_unique_name("car1_build_list"),
            "description": "Build list for car 1",
            "car_id": str(car1["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data1, headers=headers)
        assert response.status_code == 200
        build_list1 = response.json()

        build_list_data2 = {
            "name": get_unique_name("car2_build_list"),
            "description": "Build list for car 2",
            "car_id": str(car2["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data2, headers=headers)
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-lists/with-votes?car_id={car1['id']}", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()

        for bl in data["data"]:
            assert bl["car_id"] == str(car1["id"])

        found = any(bl["id"] == build_list1["id"] for bl in data["data"])
        assert found

    def test_get_build_lists_with_votes_filter_by_owner(
        self, client: TestClient, test_user: User, db_session: Any
    ) -> None:
        """Test filtering /with-votes by owner_id returns only that user's build lists."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("owned_build_list"),
            "description": "Owned by test_user",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        owned_build_list = response.json()

        other_user = UserRepository().create_user(
            DBUser(
                username=get_unique_name("other_owner"),
                email=f"{get_unique_name('other_owner')}@example.com",
                hashed_password=get_password_hash("testpassword"),
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )
        other_token = get_auth_token(client, other_user.username)
        other_headers = get_auth_headers(other_token)
        other_build_list_data = {
            "name": get_unique_name("other_build_list"),
            "description": "Owned by other user",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=other_build_list_data, headers=other_headers)
        assert response.status_code == 200
        other_build_list = response.json()

        response = client.get(
            f"{settings.API_STR}/build-lists/with-votes?owner_id={test_user.id}",
            headers=headers,
        )
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()
        returned_ids = {bl["id"] for bl in data["data"]}
        assert owned_build_list["id"] in returned_ids
        assert other_build_list["id"] not in returned_ids

    def test_get_build_lists_with_votes_multiple_votes(
        self, client: TestClient, test_user: User, db_session: Any
    ) -> None:
        """Test build lists with multiple votes."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        for i in range(3):
            voter = UserRepository().create_user(
                DBUser(
                    username=get_unique_name(f"voter_{i}"),
                    email=f"{get_unique_name(f'voter_{i}')}@example.com",
                    hashed_password=get_password_hash("testpassword"),
                    email_verified=True,
                    disabled=False,
                    is_admin=False,
                    is_superuser=False,
                )
            )

            voter_token = get_auth_token(client, voter.username)
            voter_headers = get_auth_headers(voter_token)

            vote_data = {"vote_type": "upvote"}
            response = client.post(
                f"{settings.API_STR}/votes/build_list/{build_list['id']}",
                json=vote_data,
                headers=voter_headers,
            )
            assert response.status_code == 200

        downvoter = UserRepository().create_user(
            DBUser(
                username=get_unique_name("downvoter"),
                email=f"{get_unique_name('downvoter')}@example.com",
                hashed_password=get_password_hash("testpassword"),
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        downvoter_token = get_auth_token(client, downvoter.username)
        downvoter_headers = get_auth_headers(downvoter_token)

        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/votes/build_list/{build_list['id']}",
            json=vote_data,
            headers=downvoter_headers,
        )
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-lists/with-votes", headers=headers)
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()

        found_build_list = None
        for bl in data["data"]:
            if bl["id"] == build_list["id"]:
                found_build_list = bl
                break

        assert found_build_list is not None
        assert found_build_list["upvotes"] == 3
        assert found_build_list["downvotes"] == 1
        assert found_build_list["total_votes"] == 4
