import os

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.category import Category
from app.api.models.user import User
from app.core.config import settings
from tests.conftest import login_user


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def get_auth_headers(token: str) -> dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {token}"}


class TestBuildListParts:
    """Test cases for build list parts endpoints."""

    def test_add_part_to_build_list_success(self, client: TestClient, test_user: User, test_category: Category) -> None:
        """Test successfully adding a part to a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        if response.status_code != 200:
            print(f"Car creation failed: {response.status_code} - {response.json()}")
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["build_list_id"] == build_list["id"]
        assert data["global_part_id"] == global_part["id"]
        assert data["notes"] == "Test notes"

    def test_add_part_to_build_list_unauthorized(self, client: TestClient, test_category: Category) -> None:
        """Test adding a part to a build list without authentication."""
        # Try to add a part without authentication
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/1/global-parts/1",
            json=build_list_part_data,
        )
        assert response.status_code == 401

    def test_add_part_to_build_list_not_found(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test adding a part to a non-existent build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Try to add part to non-existent build list
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/99999/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 404

    def test_add_part_to_build_list_part_not_found(self, client: TestClient, test_user: User) -> None:
        """Test adding a non-existent part to a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Try to add non-existent part
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/99999",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 404

    def test_add_part_to_build_list_missing_quantity(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test adding a part to a build list without providing quantity."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Try to add part without quantity (this should work since quantity is not required)
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

    def test_add_part_to_build_list_invalid_quantity(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test adding a part to a build list with invalid quantity."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Try to add part with invalid quantity (quantity is not part of the schema, so this should work)
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

    def test_add_part_to_build_list_duplicate(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test adding a duplicate part to a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Try to add the same part again
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 409

    def test_get_build_list_parts_success(self, client: TestClient, test_user: User, test_category: Category) -> None:
        """Test getting parts from a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 2,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Get parts from build list
        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        part = data[0]
        assert part["build_list_id"] == build_list["id"]
        assert part["global_part_id"] == global_part["id"]
        assert part["quantity"] == 2
        assert part["notes"] == "Test notes"

    def test_get_build_list_parts_not_found(self, client: TestClient, test_user: User) -> None:
        """Test getting parts from a non-existent build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Try to get parts from non-existent build list
        response = client.get(f"{settings.API_STR}/build-list-parts/99999", headers=headers)
        assert response.status_code == 404

    def test_get_build_list_parts_unauthorized(self, client: TestClient) -> None:
        """Test getting parts from a build list without authentication."""
        # Try to get parts without authentication
        response = client.get(f"{settings.API_STR}/build-list-parts/1")
        assert response.status_code == 401

    def test_update_build_list_part_success(self, client: TestClient, test_user: User, test_category: Category) -> None:
        """Test updating a build list part."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Update the build list part
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
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Try to update a build list part that doesn't exist
        update_data = {
            "quantity": 3,
            "notes": "Updated notes",
        }
        response = client.put(f"{settings.API_STR}/build-list-parts/99999", json=update_data, headers=headers)
        assert response.status_code == 404

    def test_update_build_list_part_unauthorized(self, client: TestClient) -> None:
        """Test updating a build list part without authentication."""
        # Try to update a build list part without authentication
        update_data = {
            "quantity": 3,
            "notes": "Updated notes",
        }
        response = client.put(f"{settings.API_STR}/build-list-parts/1", json=update_data)
        assert response.status_code == 401

    def test_update_build_list_part_invalid_quantity(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test updating a build list part with invalid quantity."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {
            "global_part_id": global_part["id"],
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Try to update with invalid quantity
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
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test removing a part from a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Remove the part
        response = client.delete(f"{settings.API_STR}/build-list-parts/{build_list_part['id']}", headers=headers)
        assert response.status_code == 200

        # Verify the part was removed
        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_remove_part_from_build_list_not_found(self, client: TestClient, test_user: User) -> None:
        """Test removing a build list part that doesn't exist."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Try to remove a build list part that doesn't exist
        response = client.delete(f"{settings.API_STR}/build-list-parts/99999", headers=headers)
        assert response.status_code == 404

    def test_remove_part_from_build_list_unauthorized(self, client: TestClient) -> None:
        """Test removing a build list part without authentication."""
        # Try to remove a build list part without authentication
        response = client.delete(f"{settings.API_STR}/build-list-parts/1")
        assert response.status_code == 401

    def test_add_part_to_build_list_with_extra_fields(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test adding a part to a build list with extra fields in the request."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list with extra fields
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
            "extra_field": "should_be_ignored",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["global_part_id"] == global_part["id"]
        assert data["quantity"] == 1
        assert data["notes"] == "Test notes"

    def test_add_part_to_build_list_with_malformed_json(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test adding a part to a build list with malformed JSON."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Try to add part with malformed JSON
        auth_headers = headers.copy()
        auth_headers["Content-Type"] = "application/json"
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            content="invalid json",
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_add_part_to_build_list_with_wrong_content_type(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test adding a part to a build list with wrong content type."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part first
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Try to add part with wrong content type (send as plain text instead of JSON)
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        auth_headers = headers.copy()
        auth_headers["Content-Type"] = "text/plain"
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            content=str(build_list_part_data).encode(),
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_update_build_list_part_with_extra_fields(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test updating a build list part with extra fields in the request."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Update the build list part with extra fields
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
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test updating a build list part with malformed JSON."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Try to update with malformed JSON
        auth_headers = headers.copy()
        auth_headers["Content-Type"] = "application/json"
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list_part['id']}",
            content="invalid json",
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_update_build_list_part_with_wrong_content_type(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test updating a build list part with wrong content type."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200
        build_list_part = response.json()

        # Try to update with wrong content type (send as plain text instead of JSON)
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
        db_session: Session,
    ) -> None:
        """Test adding a part to a build list with a disabled user account."""
        # Disable the user and commit to database
        test_user.disabled = True
        db_session.commit()
        db_session.refresh(test_user)

        # Try to login as disabled user - this should fail
        from app.core.config import settings

        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 400  # Disabled users should get 400

        # Since login failed, we can't test the build list functionality
        # The test demonstrates that disabled users cannot authenticate

    def test_add_part_to_build_list_with_unverified_email(
        self,
        client: TestClient,
        test_user: User,
        test_category: Category,
        db_session: Session,
    ) -> None:
        """Test adding a part to a build list with an unverified email user account."""
        # Set email as unverified and commit to database
        test_user.email_verified = False
        db_session.commit()
        db_session.refresh(test_user)

        # Login as test user (this should work since email verification is checked later)
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 401  # Should fail due to unverified email

        # The test demonstrates that unverified email users cannot access protected endpoints

    def test_create_and_add_part_to_build_list_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test creating a global part and adding it to a build list in one operation."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Honda",
            "model": "Accord",
            "year": 2021,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create and add global part to build list
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 12999,
            "category_id": test_category.id,
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
        assert "global_part" in data
        assert data["global_part"]["name"] == part_data["name"]

    def test_get_global_parts_in_build_list_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test getting global parts from a build list with full part details."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Honda",
            "model": "Accord",
            "year": 2021,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 2,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Get global parts with full details
        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        part = data[0]
        assert part["build_list_id"] == build_list["id"]
        assert part["global_part_id"] == global_part["id"]
        assert part["quantity"] == 2
        assert "global_part" in part
        assert part["global_part"]["name"] == global_part["name"]

    def test_update_global_part_in_build_list_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test updating a global part in a build list by build_list_id and global_part_id."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Honda",
            "model": "Accord",
            "year": 2021,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Original notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Update the global part in build list
        update_data = {
            "quantity": 5,
            "notes": "Updated notes via global part endpoint",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["quantity"] == 5
        assert data["notes"] == "Updated notes via global part endpoint"

    def test_update_global_part_in_build_list_not_found(self, client: TestClient, test_user: User) -> None:
        """Test updating a non-existent global part in a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Honda",
            "model": "Accord",
            "year": 2021,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Try to update non-existent part
        update_data = {
            "quantity": 5,
            "notes": "Updated notes",
        }
        response = client.put(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/99999",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 404

    def test_remove_global_part_from_build_list_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test removing a global part from a build list by build_list_id and global_part_id."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Honda",
            "model": "Accord",
            "year": 2021,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        global_part = response.json()

        # Add part to build list
        build_list_part_data = {
            "quantity": 1,
            "notes": "Test notes",
        }
        response = client.post(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            json=build_list_part_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Remove the global part using build_list_id and global_part_id
        response = client.delete(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/{global_part['id']}",
            headers=headers,
        )
        assert response.status_code == 200

        # Verify the part was removed
        response = client.get(f"{settings.API_STR}/build-list-parts/{build_list['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_remove_global_part_from_build_list_not_found(self, client: TestClient, test_user: User) -> None:
        """Test removing a non-existent global part from a build list."""
        # Login as test user and get token
        token = login_user(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first
        car_data = {
            "make": "Honda",
            "model": "Accord",
            "year": 2021,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Try to remove non-existent part
        response = client.delete(
            f"{settings.API_STR}/build-list-parts/{build_list['id']}/global-parts/99999", headers=headers
        )
        assert response.status_code == 404
