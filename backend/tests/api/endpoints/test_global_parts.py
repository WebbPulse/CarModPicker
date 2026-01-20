import os
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.category import Category
from app.api.models.user import User
from app.core.config import settings


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def get_auth_token_and_headers(client: TestClient, username: str, password: str = "testpassword") -> dict[str, str]:
    """Login and return Authorization headers with Bearer token."""
    login_data = {"username": username, "password": password}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestGlobalParts:
    """Test cases for global parts endpoints."""

    def test_create_global_part_success(self, client: TestClient, test_user: User, test_category: Category) -> None:
        """Test successful creation of a global part."""
        # Login as test user and get token
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,  # Price in cents (integer)
            "category_id": test_category.id,
            "image_url": "https://example.com/image.jpg",
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == part_data["name"]
        assert data["description"] == part_data["description"]
        assert data["price"] == part_data["price"]
        assert data["category_id"] == test_category.id
        assert data["user_id"] == test_user.id
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_global_part_unauthorized(self, client: TestClient, test_category: Category) -> None:
        """Test creating a global part without authentication."""
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,  # Price in cents (integer)
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 401

    def test_get_global_parts_list(self, client: TestClient, test_user: User, test_category: Category) -> None:
        """Test retrieving list of global parts."""
        # Login and create a part first
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Get the list
        response = client.get(f"{settings.API_STR}/global-parts/", headers=headers)
        assert response.status_code == 200

        data: list[Any] = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_global_parts_with_pagination(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test pagination for global parts list."""
        # Login and create multiple parts
        headers = get_auth_token_and_headers(client, test_user.username)

        # Create multiple parts
        for i in range(3):
            part_data = {
                "name": get_unique_name(f"test_part_{i}"),
                "description": f"Test part {i}",
                "price": 9999 + i,  # Price in cents (integer)
                "category_id": test_category.id,
            }
            response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
            assert response.status_code == 200

        # Test pagination
        response = client.get(f"{settings.API_STR}/global-parts/?skip=0&limit=2", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2

    def test_get_global_parts_with_category_filter(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test filtering global parts by category."""
        # Login and create a part
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Filter by category
        response = client.get(f"{settings.API_STR}/global-parts/?category_id={test_category.id}", headers=headers)
        assert response.status_code == 200
        data: list[Any] = response.json()
        assert isinstance(data, list)
        part: Any
        for part in data:
            assert part["category_id"] == test_category.id

    def test_get_global_parts_with_search(self, client: TestClient, test_user: User, test_category: Category) -> None:
        """Test searching global parts."""
        # Login and create a part
        headers = get_auth_token_and_headers(client, test_user.username)

        unique_name = get_unique_name("searchable_part")
        part_data = {
            "name": unique_name,
            "description": "A searchable part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Search by name
        response = client.get(f"{settings.API_STR}/global-parts/?search={unique_name}", headers=headers)
        assert response.status_code == 200
        data: list[Any] = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(unique_name in part["name"] for part in data)  # type: ignore[misc]

    def test_get_global_part_by_id(self, client: TestClient, test_user: User, test_category: Category) -> None:
        """Test retrieving a specific global part by ID."""
        # Login and create a part
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        created_part = response.json()

        # Get the part by ID
        response = client.get(f"{settings.API_STR}/global-parts/{created_part['id']}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_part["id"]
        assert data["name"] == created_part["name"]

    def test_get_global_part_not_found(self, client: TestClient) -> None:
        """Test retrieving a non-existent global part."""
        response = client.get(f"{settings.API_STR}/global-parts/99999")
        assert response.status_code == 404

    def test_update_global_part_success(self, client: TestClient, test_user: User, test_category: Category) -> None:
        """Test successful update of a global part."""
        # Login and create a part
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        created_part = response.json()

        # Update the part
        update_data = {
            "name": get_unique_name("updated_part"),
            "description": "Updated description",
            "price": 14999,  # Price in cents (integer)
        }
        response = client.put(
            f"{settings.API_STR}/global-parts/{created_part['id']}", json=update_data, headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["price"] == update_data["price"]

    def test_update_global_part_unauthorized(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test updating a global part without proper authorization."""
        # Create a part as test_user
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        created_part = response.json()

        # Try to update without authentication
        update_data = {"name": "unauthorized_update"}
        response = client.put(f"{settings.API_STR}/global-parts/{created_part['id']}", json=update_data)
        assert response.status_code == 401

    def test_delete_global_part_success(self, client: TestClient, test_user: User, test_category: Category) -> None:
        """Test successful deletion of a global part."""
        # Login and create a part
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        created_part = response.json()

        # Delete the part
        response = client.delete(f"{settings.API_STR}/global-parts/{created_part['id']}", headers=headers)
        assert response.status_code == 200

        # Verify it's deleted
        response = client.get(f"{settings.API_STR}/global-parts/{created_part['id']}", headers=headers)
        assert response.status_code == 404

    def test_delete_global_part_unauthorized(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test deleting a global part without proper authorization."""
        # Create a part as test_user
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        created_part = response.json()

        # Try to delete without authentication
        response = client.delete(f"{settings.API_STR}/global-parts/{created_part['id']}")
        assert response.status_code == 401

    def test_get_global_parts_with_votes(self, client: TestClient, test_user: User, test_category: Category) -> None:
        """Test retrieving global parts with vote data."""
        # Login and create a part
        headers = get_auth_token_and_headers(client, test_user.username)

        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Get parts with votes
        response = client.get(f"{settings.API_STR}/global-parts/with-votes", headers=headers)
        assert response.status_code == 200
        result: dict[str, Any] = response.json()
        assert isinstance(result, dict)
        assert "data" in result
        assert "pagination" in result
        data: list[Any] = result["data"]
        assert isinstance(data, list)
        if len(data) > 0:
            part: Any = data[0]
            assert "upvotes" in part
            assert "downvotes" in part
            assert "user_vote" in part

    def test_create_global_part_with_invalid_price(
        self, client: TestClient, test_user: Any, test_category: Any
    ) -> None:
        """Test that creating a global part with an invalid price fails validation."""
        # Login as test user
        headers = get_auth_token_and_headers(client, test_user.username)

        # Test with price too large for PostgreSQL integer
        part_data = {
            "name": "Test Part with Invalid Price",
            "description": "A test part with invalid price",
            "price": 2147483648,  # One more than max PostgreSQL integer
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 422
        error_detail = response.json()["details"][0]
        assert error_detail["type"] == "less_than_equal"
        assert "price" in error_detail["field"]

        # Test with negative price
        part_data["price"] = -1
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 422
        error_detail = response.json()["details"][0]
        assert error_detail["type"] == "greater_than_equal"
        assert "price" in error_detail["field"]

        # Test with extremely large price
        part_data["price"] = 999999999999999999
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 422
        error_detail = response.json()["details"][0]
        assert error_detail["type"] == "less_than_equal"
        assert "price" in error_detail["field"]

    def test_get_global_parts_by_category_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test retrieving global parts by category."""
        # Login as test user and get token
        headers = get_auth_token_and_headers(client, test_user.username)

        # Create multiple global parts in the same category
        part_names = [get_unique_name(f"test_part_{i}") for i in range(3)]
        created_parts = []
        for part_name in part_names:
            part_data = {
                "name": part_name,
                "description": "A test part description",
                "price": 9999,
                "category_id": test_category.id,
            }
            response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
            assert response.status_code == 200
            created_parts.append(response.json())

        # Get global parts by category (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/global-parts/category/{test_category.id}")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        # Should return at least the parts we created
        assert len(data) >= len(created_parts)

        # Verify all returned parts are in the correct category
        for part in data:
            assert part["category_id"] == test_category.id

        # Verify our created parts are in the results
        part_ids = {part["id"] for part in data}
        created_part_ids = {part["id"] for part in created_parts}
        assert created_part_ids.issubset(part_ids)

    def test_get_global_parts_by_category_with_pagination(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test pagination for global parts by category."""
        # Login as test user and get token
        headers = get_auth_token_and_headers(client, test_user.username)

        # Create multiple global parts in the same category
        for i in range(5):
            part_data = {
                "name": get_unique_name(f"test_part_{i}"),
                "description": "A test part description",
                "price": 9999,
                "category_id": test_category.id,
            }
            response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
            assert response.status_code == 200

        # Get first page
        response = client.get(f"{settings.API_STR}/global-parts/category/{test_category.id}?skip=0&limit=2")
        assert response.status_code == 200
        first_page = response.json()
        assert isinstance(first_page, list)
        assert len(first_page) <= 2

        # Get second page
        response = client.get(f"{settings.API_STR}/global-parts/category/{test_category.id}?skip=2&limit=2")
        assert response.status_code == 200
        second_page = response.json()
        assert isinstance(second_page, list)
        assert len(second_page) <= 2

        # Verify no overlap
        first_page_ids = {part["id"] for part in first_page}
        second_page_ids = {part["id"] for part in second_page}
        assert first_page_ids.isdisjoint(second_page_ids)

    def test_get_global_parts_by_category_not_found(self, client: TestClient) -> None:
        """Test retrieving global parts for a non-existent category."""
        # Try to get parts for non-existent category (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/global-parts/category/99999")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_global_parts_by_category_public_endpoint(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test that getting global parts by category works without authentication."""
        # Login as test user to create data
        headers = get_auth_token_and_headers(client, test_user.username)

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Get global parts by category without authentication (public endpoint)
        response = client.get(f"{settings.API_STR}/global-parts/category/{test_category.id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_count_global_parts_by_user_success(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test counting global parts created by a specific user."""
        # Login as test user and get token
        headers = get_auth_token_and_headers(client, test_user.username)

        # Get initial count (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/global-parts/user/{test_user.id}/count")
        assert response.status_code == 200
        initial_data = response.json()
        assert "count" in initial_data
        initial_count = initial_data["count"]
        assert isinstance(initial_count, int)
        assert initial_count >= 0

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Count again (should be increased by 1)
        response = client.get(f"{settings.API_STR}/global-parts/user/{test_user.id}/count")
        assert response.status_code == 200
        updated_data = response.json()
        assert "count" in updated_data
        assert updated_data["count"] == initial_count + 1

    def test_count_global_parts_by_user_zero(self, client: TestClient, db_session: Session) -> None:
        """Test counting global parts for a user with no parts."""
        # Create a new user with no parts
        from app.api.dependencies.auth import get_password_hash
        from app.api.models.user import User as DBUser

        new_user = DBUser(
            username=f"new_user_{os.getpid()}_{id(db_session)}",
            email=f"new_user_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(new_user)
        db_session.commit()
        db_session.refresh(new_user)

        # Count global parts for this user (should be 0)
        response = client.get(f"{settings.API_STR}/global-parts/user/{new_user.id}/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert data["count"] == 0

    def test_count_global_parts_by_user_public_endpoint(
        self, client: TestClient, test_user: User, test_category: Category
    ) -> None:
        """Test that counting global parts by user works without authentication."""
        # Login as test user to create data
        headers = get_auth_token_and_headers(client, test_user.username)

        # Create a global part
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "price": 9999,
            "category_id": test_category.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Count global parts by user without authentication (public endpoint)
        response = client.get(f"{settings.API_STR}/global-parts/user/{test_user.id}/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
