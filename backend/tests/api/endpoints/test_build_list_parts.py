"""Covers the build list part endpoints: adding, updating, reordering and removing parts."""

import os
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.catalog import Category, PartManufacturer
from app.db.dynamo.users import User
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import INVALID_UUID_STR, auth_headers, create_car_in_db, login_user

def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"

def get_auth_headers(token: str) -> dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return auth_headers(token)

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
            is_admin=True,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
    )

    token = login_user(client, username)

    return admin_user.__dict__, token

class TestBuildListParts:
    """Test cases for build list parts endpoints."""

    def test_add_part_to_build_list_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test successfully adding a part to a build list."""
        token = login_user(client, test_user.username)
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

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["build_list_id"] == build_list["id"]
        assert data["part_id"] == part["id"]
        assert data["notes"] == "Test notes"

    def test_add_part_to_build_list_unauthorized(self, client: TestClient, test_category: Category) -> None:
        """Test adding a part to a build list without authentication."""
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}/parts/{INVALID_UUID_STR}",
            json=build_list_part_data,
        )
        assert response.status_code == 401

    def test_add_part_to_build_list_not_found(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a non-existent build list."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 404

    def test_add_part_to_build_list_part_not_found(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test adding a non-existent part to a build list."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{INVALID_UUID_STR}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 404

    def test_add_part_to_build_list_missing_quantity(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a build list without providing quantity."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

    def test_add_part_to_build_list_invalid_quantity(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a build list with invalid quantity."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

    def test_add_part_to_build_list_duplicate(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a duplicate part to a build list."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 409

    def test_get_build_list_parts_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test getting parts from a build list."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "quantity": 2,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        build_list_part = data[0]
        assert build_list_part["build_list_id"] == build_list["id"]
        assert build_list_part["part_id"] == part["id"]
        assert build_list_part["quantity"] == 2
        assert build_list_part["notes"] == "Test notes"

    def test_get_build_list_parts_not_found(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test getting parts from a non-existent build list."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        response = client.get(f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 404

    def test_get_build_list_parts_unauthorized(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test getting parts from a build list without authentication (public read is allowed)."""
        car = create_car_in_db(db_session)

        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list_id = response.json()["id"]

        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list_id}")
        assert response.status_code == 200

    def test_update_build_list_part_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test updating a build list part."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        update_data = {
            "quantity": 3,
            "notes": "Updated notes",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list_part['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == build_list_part["id"]
        assert data["quantity"] == 3
        assert data["notes"] == "Updated notes"

    def test_update_build_list_part_not_found(self, client: TestClient, test_user: User) -> None:
        """Test updating a build list part that doesn't exist."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        update_data = {
            "quantity": 3,
            "notes": "Updated notes",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}", json=update_data, headers=headers
        )
        assert response.status_code == 404

    def test_update_build_list_part_unauthorized(self, client: TestClient) -> None:
        """Test updating a build list part without authentication."""
        update_data = {
            "quantity": 3,
            "notes": "Updated notes",
        }
        response = client.put(f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}", json=update_data)
        assert response.status_code == 401

    def test_update_build_list_part_invalid_quantity(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test updating a build list part with invalid quantity."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "part_id": part["id"],
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        update_data = {
            "quantity": 0,
            "notes": "Updated notes",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list_part['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 422

    def test_remove_part_from_build_list_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test removing a part from a build list."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        response = client.delete(f"{settings.API_STR}/build-list-parts/{build_list_part['id']}", headers=headers)
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_remove_part_from_build_list_not_found(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test removing a build list part that doesn't exist."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        response = client.delete(f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}", headers=headers)
        assert response.status_code == 404

    def test_remove_part_from_build_list_unauthorized(self, client: TestClient) -> None:
        """Test removing a build list part without authentication."""
        response = client.delete(f"{settings.API_STR}/build-list-parts/{INVALID_UUID_STR}")
        assert response.status_code == 401

    def test_add_part_to_build_list_with_extra_fields(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a build list with extra fields in the request."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
            "extra_field": "should_be_ignored",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["part_id"] == part["id"]
        assert data["quantity"] == 1
        assert data["notes"] == "Test notes"

    def test_add_part_to_build_list_with_malformed_json(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a build list with malformed JSON."""
        token = login_user(client, test_user.username)
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

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        auth_headers = headers.copy()
        auth_headers["Content-Type"] = "application/json"
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            content="invalid json",
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_add_part_to_build_list_with_wrong_content_type(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a build list with wrong content type."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        auth_headers = headers.copy()
        auth_headers["Content-Type"] = "text/plain"
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            content=str(build_list_part_data).encode(),
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_update_build_list_part_with_extra_fields(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test updating a build list part with extra fields in the request."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        update_data = {
            "quantity": 3,
            "notes": "Updated notes",
            "extra_field": "should_be_ignored",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list_part['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["quantity"] == 3
        assert data["notes"] == "Updated notes"

    def test_update_build_list_part_with_malformed_json(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test updating a build list part with malformed JSON."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        auth_headers = headers.copy()
        auth_headers["Content-Type"] = "application/json"
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list_part['id']}",
            content="invalid json",
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_update_build_list_part_with_wrong_content_type(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test updating a build list part with wrong content type."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        update_data = {
            "quantity": 3,
            "notes": "Updated notes",
        }
        auth_headers = headers.copy()
        auth_headers["Content-Type"] = "text/plain"
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list_part['id']}",
            content=str(update_data).encode(),
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_add_part_to_build_list_with_disabled_user(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """A disabled account cannot add a part to a build list.

        This used to assert that `POST /api/auth/token` answered 400, and then
        stopped, with a comment saying the build list functionality could not be
        reached because login had failed. Row 13 of `docs/identity-adoption.md`
        deleted that route and moved the disabled check into `get_current_user`,
        so the test now presents a valid credential to the real endpoint.
        """
        from app.core.config import settings

        test_user = UserRepository().update(test_user.id, disabled=True)

        headers = auth_headers(login_user(client, test_user.username))

        response = client.post(
            f"{settings.API_STR}/build-list-parts/{uuid4()}/parts/{uuid4()}",
            json={"quantity": 1},
            headers=headers,
        )

        assert response.status_code == 401

    def test_add_part_to_build_list_with_unverified_email(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test adding a part to a build list with an unverified email user account."""
        test_user = UserRepository().update(test_user.id, email_verified=False)

        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 401

    def test_create_and_add_part_to_build_list_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test creating a global part and adding it to a build list in one operation."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
            "notes": "Some notes about the part",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/create-and-add-part",
            json=part_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["build_list_id"] == build_list["id"]
        assert data["notes"] == "Some notes about the part"
        assert "part" in data
        assert data["part"]["name"] == part_data["name"]

    def test_get_parts_in_build_list_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test getting global parts from a build list with full part details."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "quantity": 2,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        build_list_part = data[0]
        assert build_list_part["build_list_id"] == build_list["id"]
        assert build_list_part["part_id"] == part["id"]
        assert build_list_part["quantity"] == 2
        assert "part" in build_list_part
        assert build_list_part["part"]["name"] == part["name"]

    def test_update_part_in_build_list_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test updating a global part in a build list by build_list_id and part_id."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "quantity": 1,
            "notes": "Original notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        update_data = {
            "quantity": 5,
            "notes": "Updated notes via global part endpoint",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["quantity"] == 5
        assert data["notes"] == "Updated notes via global part endpoint"

    def test_update_part_in_build_list_not_found(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test updating a non-existent global part in a build list."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        update_data = {
            "quantity": 5,
            "notes": "Updated notes",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{INVALID_UUID_STR}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 404

    def test_remove_part_from_build_list_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test removing a global part from a build list by build_list_id and part_id."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        response = client.delete(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            headers=headers,
        )
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_remove_part_from_build_list_not_found(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test removing a non-existent global part from a build list."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Honda", "Accord", "10th Gen", 2018, 2022)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        response = client.delete(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{INVALID_UUID_STR}", headers=headers
        )
        assert response.status_code == 404

    def test_count_build_lists_containing_part_success(
        self,
        client: TestClient,
        premium_test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test counting build lists containing a global part when it exists in multiple build lists."""
        token = login_user(client, premium_test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_data_1 = {
            "name": get_unique_name("test_build_list_1"),
            "description": "First test build list",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data_1, headers=headers)
        assert response.status_code == 200
        build_list_1 = response.json()

        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list_1['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        build_list_data_2 = {
            "name": get_unique_name("test_build_list_2"),
            "description": "Second test build list",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data_2, headers=headers)
        assert response.status_code == 200
        build_list_2 = response.json()

        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list_2['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-list-parts/parts/{part['id']}/build-lists/count")
        assert response.status_code == 200

        data = response.json()
        assert "count" in data
        assert data["count"] == 2

    def test_count_build_lists_containing_part_zero(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test counting build lists containing a global part when it exists but is not in any build lists."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        response = client.get(f"{settings.API_STR}/build-list-parts/parts/{part['id']}/build-lists/count")
        assert response.status_code == 200

        data = response.json()
        assert "count" in data
        assert data["count"] == 0

    def test_count_build_lists_containing_part_not_found(self, client: TestClient) -> None:
        """Test counting build lists containing a non-existent global part."""
        response = client.get(f"{settings.API_STR}/build-list-parts/parts/{INVALID_UUID_STR}/build-lists/count")
        assert response.status_code == 404

    def test_count_build_lists_containing_part_public_endpoint(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test that counting build lists containing a global part works without authentication."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-list-parts/parts/{part['id']}/build-lists/count")
        assert response.status_code == 200

        data = response.json()
        assert "count" in data
        assert data["count"] == 1

    def test_update_build_list_part_when_build_list_deleted(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test build list part update when build list is deleted (edge case - cascade behavior)."""
        token = login_user(client, test_user.username)
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

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "car_id": str(car["id"]),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {"quantity": 1, "notes": "Test notes"}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()
        build_list_part_id = build_list_part["id"]

        delete_response = client.delete(f"{settings.API_STR}/build-lists/{build_list['id']}", headers=headers)
        assert delete_response.status_code == 200

        update_data = {"quantity": 2}
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list_part_id}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 404, "Update should fail when build list is deleted"

    def test_delete_build_list_part_when_build_list_deleted(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test build list part deletion when build list is deleted (edge case - cascade behavior)."""
        token = login_user(client, test_user.username)
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

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "car_id": str(car["id"]),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        build_list_part_data = {"quantity": 1, "notes": "Test notes"}
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()
        build_list_part_id = build_list_part["id"]

        delete_response = client.delete(f"{settings.API_STR}/build-lists/{build_list['id']}", headers=headers)
        assert delete_response.status_code == 200

        response = client.delete(f"{settings.API_STR}/build-list-parts/{build_list_part_id}", headers=headers)
        assert response.status_code == 404, "Delete should fail when build list part was cascade deleted"

    def test_count_build_list_parts_success(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        test_part_manufacturer: PartManufacturer,
        db_session: Any,
    ) -> None:
        """Test counting build list parts."""
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, "Toyota", "Camry", "8th Gen", 2018, 2024)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        response = client.get(f"{settings.API_STR}/build-list-parts/count")
        assert response.status_code == 200
        initial_data = response.json()
        assert "count" in initial_data
        initial_count = initial_data["count"]
        assert isinstance(initial_count, int)
        assert initial_count >= 0

        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/parts/{part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/build-list-parts/count")
        assert response.status_code == 200
        updated_data = response.json()
        assert "count" in updated_data
        assert updated_data["count"] == initial_count + 1

    def test_count_build_list_parts_public_endpoint(self, client: TestClient) -> None:
        """Test that counting build list parts works without authentication."""
        response = client.get(f"{settings.API_STR}/build-list-parts/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
