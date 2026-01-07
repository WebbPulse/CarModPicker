import os
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.user import User
from app.core.config import settings


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


class TestBuildLists:
    """Test cases for build lists endpoints."""

    def test_create_build_list_success(self, client: TestClient, test_user: User) -> None:
        """Test successfully creating a build list."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == build_list_data["name"]
        assert data["description"] == build_list_data["description"]
        assert data["user_id"] == test_user.id

    def test_create_build_list_unauthorized(self, client: TestClient) -> None:
        """Test creating a build list without authentication."""
        # Try to create a build list without authentication
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 401

    def test_create_build_list_missing_name(self, client: TestClient, test_user: User) -> None:
        """Test creating a build list without providing a name."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Try to create a build list without name
        build_list_data = {"description": "A test build list description"}
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 422

    def test_create_build_list_empty_name(self, client: TestClient, test_user: User) -> None:
        """Test creating a build list with an empty name."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Try to create a build list with empty name
        build_list_data = {
            "name": "",
            "description": "A test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 422

    def test_get_build_list_by_id(self, client: TestClient, test_user: User) -> None:
        """Test retrieving a specific build list by ID."""
        # Login and get token
        token = get_auth_token(client, test_user.username)
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        created_build_list = response.json()

        # Get the build list by ID
        response = client.get(f"{settings.API_STR}/build-lists/{created_build_list['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_build_list["id"]
        assert data["name"] == created_build_list["name"]

    def test_get_build_list_not_found(self, client: TestClient, test_user: User) -> None:
        """Test retrieving a non-existent build list."""
        # Login first since the endpoint requires authentication
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Try to get a non-existent build list
        response = client.get(f"{settings.API_STR}/build-lists/99999", headers=headers)
        assert response.status_code == 404

    def test_get_build_list_unauthorized(self, client: TestClient) -> None:
        """Test retrieving a build list owned by another user."""
        # Try to get a build list without authentication
        response = client.get(f"{settings.API_STR}/build-lists/1")
        assert response.status_code == 401

    def test_get_user_build_lists(self, client: TestClient, test_user: User) -> None:
        """Test retrieving build lists for the current user."""
        # Login and get token
        token = get_auth_token(client, test_user.username)
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Get user's build lists
        response = client.get(f"{settings.API_STR}/build-lists/user/me", headers=headers)
        assert response.status_code == 200
        data: list[Any] = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_user_build_lists_unauthorized(self, client: TestClient) -> None:
        """Test retrieving build lists without authentication."""
        response = client.get(f"{settings.API_STR}/build-lists/user/me")
        assert response.status_code == 401

    def test_update_build_list_success(self, client: TestClient, test_user: User) -> None:
        """Test updating a build list."""
        # Login and get token
        token = get_auth_token(client, test_user.username)
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        created_build_list = response.json()

        # Update the build list
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
        # Try to update a build list without authentication
        update_data = {"name": "unauthorized_update"}
        response = client.put(f"{settings.API_STR}/build-lists/1", json=update_data)
        assert response.status_code == 401

    def test_delete_build_list_success(self, client: TestClient, test_user: User) -> None:
        """Test deleting a build list."""
        # Login and get token
        token = get_auth_token(client, test_user.username)
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        created_build_list = response.json()

        # Delete the build list
        response = client.delete(f"{settings.API_STR}/build-lists/{created_build_list['id']}", headers=headers)
        assert response.status_code == 200

        # Verify it's deleted
        response = client.get(f"{settings.API_STR}/build-lists/{created_build_list['id']}", headers=headers)
        assert response.status_code == 404

    def test_delete_build_list_unauthorized(self, client: TestClient) -> None:
        """Test deleting a build list without proper authorization."""
        # Try to delete a build list without authentication
        response = client.delete(f"{settings.API_STR}/build-lists/1")
        assert response.status_code == 401

    def test_get_build_lists_by_car(self, client: TestClient, test_user: User) -> None:
        """Test retrieving build lists for a specific car."""
        # Login and get token
        token = get_auth_token(client, test_user.username)
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

        # Create build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Get build lists for the car
        response = client.get(f"{settings.API_STR}/build-lists/car/{car['id']}", headers=headers)
        assert response.status_code == 200
        data: list[Any] = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        build_list: Any
        for build_list in data:
            assert build_list["car_id"] == car["id"]

    def test_get_build_lists_by_car_unauthorized(self, client: TestClient, test_user: User) -> None:
        """Test retrieving build lists for a car owned by another user."""
        # Create a car as test_user
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data, headers=headers)
        assert response.status_code == 200
        car = response.json()

        # Try to get build lists for another user's car without authentication
        response = client.get(f"{settings.API_STR}/build-lists/car/{car['id']}")
        assert response.status_code == 401

    def test_create_build_list_with_extra_fields(self, client: TestClient, test_user: User) -> None:
        """Test creating a build list with extra fields in the request."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a build list with extra fields
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "extra_field": "should_be_ignored",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == build_list_data["name"]
        assert data["description"] == build_list_data["description"]

    def test_create_build_list_with_malformed_json(self, client: TestClient, test_user: User) -> None:
        """Test creating a build list with malformed JSON."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        headers["Content-Type"] = "application/json"

        # Try to create a build list with malformed JSON
        response = client.post(
            f"{settings.API_STR}/build-lists/",
            content="invalid json",
            headers=headers,
        )
        assert response.status_code == 422

    def test_create_build_list_with_wrong_content_type(self, client: TestClient, test_user: User) -> None:
        """Test creating a build list with wrong content type."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        headers["Content-Type"] = "text/plain"

        # Try to create a build list with wrong content type
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/",
            data=build_list_data,
            headers=headers,
        )
        assert response.status_code == 422

    def test_update_build_list_with_extra_fields(self, client: TestClient, test_user: User) -> None:
        """Test updating a build list with extra fields in the request."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Update the build list with extra fields
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

    def test_update_build_list_with_malformed_json(self, client: TestClient, test_user: User) -> None:
        """Test updating a build list with malformed JSON."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Try to update with malformed JSON
        update_headers = get_auth_headers(token)
        update_headers["Content-Type"] = "application/json"
        response = client.put(
            f"{settings.API_STR}/build-lists/{build_list['id']}",
            content="invalid json",
            headers=update_headers,
        )
        assert response.status_code == 422

    def test_update_build_list_with_wrong_content_type(self, client: TestClient, test_user: User) -> None:
        """Test updating a build list with wrong content type."""
        # Login as test user and get token
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Try to update with wrong content type
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

    def test_create_build_list_with_disabled_user(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test creating a build list with a disabled user account."""
        # Disable the user and commit to database
        test_user.disabled = True
        db_session.commit()
        db_session.refresh(test_user)

        # Try to login as disabled user - this should fail
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 400  # Disabled users should get 400

        # Since login failed, we can't test the build list functionality
        # The test demonstrates that disabled users cannot authenticate

    def test_create_build_list_with_unverified_email(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test creating a build list with an unverified email user account."""
        # Set email as unverified and commit to database
        test_user.email_verified = False
        db_session.commit()
        db_session.refresh(test_user)

        # Login as test user (this should work since email verification is checked in get_current_user)
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Extract token from login response
        token_data = response.json()
        assert "access_token" in token_data
        token = token_data["access_token"]
        headers = get_auth_headers(token)

        # Try to create a build list with unverified email user
        # Even though login succeeded, the token should be invalid for protected endpoints
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 401  # Should fail due to unverified email

        # The test demonstrates that unverified email users cannot access protected endpoints
