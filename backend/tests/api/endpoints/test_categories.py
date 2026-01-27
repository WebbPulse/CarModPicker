import os
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.brand import Brand
from app.api.models.category import Category
from app.api.models.user import User as DBUser
from app.core.config import settings
from tests.conftest import get_default_category_id, test_brand


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


# Helper function to create and login an admin user
def create_and_login_admin_user(
    client: TestClient, db_session: Session, username_suffix: str = "admin"
) -> tuple[dict[str, Any], str]:
    """Create an admin user and log them in. Returns (user_dict, token)."""
    username = f"admin_test_{username_suffix}"
    email = f"admin_test_{username_suffix}@example.com"
    password = "testpassword"

    # Create admin user directly in database
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

    # Log in and get token
    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert token_response.status_code == 200, f"Failed to login admin user: {token_response.text}"
    token = token_response.json()["access_token"]

    return admin_user.__dict__, token


# Helper function to create a user and log them in. Returns (user_id, token)
def create_and_login_user(client: TestClient, username_suffix: str) -> tuple[int, str]:
    username = f"category_test_user_{username_suffix}"
    email = f"category_test_user_{username_suffix}@example.com"
    password = "testpassword"

    user_data = {
        "username": username,
        "email": email,
        "password": password,
    }
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    user_id = -1
    if response.status_code == 200:
        user_id = response.json()["id"]
    elif response.status_code == 400 and "already registered" in response.json().get("detail", ""):
        pass
    else:
        response.raise_for_status()

    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    if token_response.status_code != 200:
        raise Exception(
            f"Failed to log in user {username}. Status: {token_response.status_code}, Detail: {token_response.text}"
        )
    token = token_response.json()["access_token"]

    if user_id == -1:
        headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get(f"{settings.API_STR}/users/me", headers=headers)
        if me_response.status_code == 200:
            user_id = me_response.json()["id"]
        else:
            raise Exception(f"Could not retrieve user_id for existing user {username} via /users/me.")

    if user_id == -1:
        raise Exception(f"User ID for {username} could not be determined.")
    return user_id, token


# Helper function to create a car via admin (cars are now centrally managed)
def create_car_via_admin_for_categories(
    client: TestClient,
    db_session: Session,
    admin_token: str,
    car_make: str = "TestMakeCategory",
    car_model: str = "TestModelCategory",
    generation_name: str = "Test Gen",
    start_year: int = 2020,
    end_year: int = 2024,
) -> int:
    """Create a car via admin endpoint and return the car ID."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    car_data = {
        "make": car_make,
        "model": car_model,
        "generation_name": generation_name,
        "start_year": start_year,
        "end_year": end_year,
    }
    response = client.post(f"{settings.API_STR}/cars/admin/cars", json=car_data, headers=headers)
    assert response.status_code == 200, f"Failed to create car for category tests: {response.text}"
    return int(response.json()["id"])


# Legacy function name for backward compatibility - now requires admin token
def create_car_for_user_cookie_auth(
    client: TestClient,
    token: str,
    car_make: str = "TestMakeCategory",
    car_model: str = "TestModelCategory",
    db_session: Session | None = None,
) -> int:
    """Create a car via admin (cars are now centrally managed).

    Note: This function signature is kept for backward compatibility but now requires
    an admin token since cars are centrally managed.
    """
    if db_session is None:
        raise ValueError("db_session is required for admin car creation")

    # Create admin user if token is not from admin, or use existing admin token
    # For simplicity, assume token is from admin
    headers = {"Authorization": f"Bearer {token}"}
    car_data = {
        "make": car_make,
        "model": car_model,
        "generation_name": "Test Gen",
        "start_year": 2020,
        "end_year": 2024,
    }
    response = client.post(f"{settings.API_STR}/cars/admin/cars", json=car_data, headers=headers)
    assert response.status_code == 200, f"Failed to create car for category tests: {response.text}"
    return int(response.json()["id"])


# Helper function to create a build list for a car (cars are centrally managed, not owned by users)
def create_build_list_for_car_cookie_auth(
    client: TestClient, token: str, car_id: int, bl_name: str = "TestBLCategory"
) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    build_list_data = {
        "name": bl_name,
        "description": "Test BL for categories",
        "car_id": car_id,
    }
    response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
    assert response.status_code == 200, f"Failed to create build list for category tests: {response.text}"
    return int(response.json()["id"])


class TestCategories:
    """Test cases for category endpoints."""

    def test_get_categories_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting all active categories."""
        # Create a default category if none exist
        if db_session.query(Category).count() == 0:
            default_category = Category(
                name="test_category",
                display_name="Test Category",
                description="A test category",
                is_active=True,
                sort_order=1,
            )
            db_session.add(default_category)
            db_session.commit()

        response = client.get(f"{settings.API_STR}/categories/")
        assert response.status_code == 200

        categories: list[Any] = response.json()
        assert isinstance(categories, list)
        # Should return at least the default categories
        assert len(categories) > 0

        # Check that all returned categories are active
        category: Any
        for category in categories:
            assert category["is_active"] is True

    def test_get_category_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting a specific category."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        response = client.get(f"{settings.API_STR}/categories/{category_id}")
        assert response.status_code == 200

        category = response.json()
        assert category["id"] == category_id
        assert "name" in category
        assert "display_name" in category

    def test_get_category_not_found(self, client: TestClient, db_session: Session) -> None:
        """Test getting a non-existent category."""
        response = client.get(f"{settings.API_STR}/categories/99999")
        assert response.status_code == 404
        assert "Category not found" in response.json()["message"]

    def test_get_parts_by_category_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting parts by category."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        response = client.get(f"{settings.API_STR}/categories/{category_id}/global-parts")
        assert response.status_code == 200

        parts = response.json()
        assert isinstance(parts, list)

    def test_get_parts_by_category_with_pagination(
        self, client: TestClient, test_brand: Brand, db_session: Session
    ) -> None:
        """Test getting parts by category with pagination."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        # Create a user and log them in
        _, token = create_and_login_user(client, "parts_by_category")
        headers = {"Authorization": f"Bearer {token}"}

        # Create a car via admin (cars are now centrally managed)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car_id = create_car_via_admin_for_categories(client, db_session, admin_token)

        # Create a build list for the car
        build_list_id = create_build_list_for_car_cookie_auth(client, token, car_id)

        # Create some parts in the category
        for i in range(3):
            part_data = {
                "name": f"Test Part {i}",
                "description": f"Test part description {i}",
                "price": 100 + i * 10,
                "build_list_id": build_list_id,
                "category_id": category_id,
                "brand_id": test_brand.id,
            }
            response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
            assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/categories/{category_id}/global-parts?skip=2&limit=2")
        assert response.status_code == 200

        parts: list[Any] = response.json()
        assert isinstance(parts, list)
        assert len(parts) <= 2

    def test_get_parts_by_category_empty(self, client: TestClient, db_session: Session) -> None:
        """Test getting parts by category when no parts exist."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        response = client.get(f"{settings.API_STR}/categories/{category_id}/global-parts")
        assert response.status_code == 200

        parts = response.json()
        assert isinstance(parts, list)
        # Note: This might not be empty if there are existing parts in the test database

    def test_create_category_success(self, client: TestClient, db_session: Session) -> None:
        """Test creating a new category."""
        # Create and login as admin user
        _, token = create_and_login_admin_user(client, db_session, "create_cat")
        headers = {"Authorization": f"Bearer {token}"}

        category_data = {
            "name": "test_category",
            "display_name": "Test Category",
            "description": "A test category",
            "icon": "test-icon",
            "is_active": True,
            "sort_order": 50,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data, headers=headers)
        assert response.status_code == 200

        category = response.json()
        assert category["name"] == category_data["name"]
        assert category["display_name"] == category_data["display_name"]
        assert category["description"] == category_data["description"]
        assert category["icon"] == category_data["icon"]
        assert category["is_active"] == category_data["is_active"]
        assert category["sort_order"] == category_data["sort_order"]

    def test_create_category_duplicate_name(self, client: TestClient, db_session: Session) -> None:
        """Test creating a category with duplicate name."""
        # Create and login as admin user
        _, token = create_and_login_admin_user(client, db_session, "duplicate_cat")
        headers = {"Authorization": f"Bearer {token}"}

        # First create a category
        category_data = {
            "name": "duplicate_test",
            "display_name": "Duplicate Test",
            "description": "A test category",
            "is_active": True,
            "sort_order": 50,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data, headers=headers)
        assert response.status_code == 200

        # Try to create another category with the same name
        response = client.post(f"{settings.API_STR}/categories/", json=category_data, headers=headers)
        assert response.status_code == 409  # 409 Conflict is correct for duplicates
        assert "already exists" in response.json()["message"]

    def test_update_category_success(self, client: TestClient, db_session: Session) -> None:
        """Test updating a category."""
        # Create and login as admin user
        _, token = create_and_login_admin_user(client, db_session, "update_cat")
        headers = {"Authorization": f"Bearer {token}"}

        # First create a category
        category_data = {
            "name": "update_test",
            "display_name": "Update Test",
            "description": "A test category",
            "is_active": True,
            "sort_order": 50,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data, headers=headers)
        assert response.status_code == 200
        category_id = response.json()["id"]

        # Update the category
        update_data = {
            "display_name": "Updated Test Category",
            "description": "Updated description",
            "sort_order": 60,
        }

        response = client.put(f"{settings.API_STR}/categories/{category_id}", json=update_data, headers=headers)
        assert response.status_code == 200

        category = response.json()
        assert category["display_name"] == update_data["display_name"]
        assert category["description"] == update_data["description"]
        assert category["sort_order"] == update_data["sort_order"]
        # Original values should remain unchanged
        assert category["name"] == category_data["name"]
        assert category["is_active"] == category_data["is_active"]

    def test_update_category_not_found(self, client: TestClient, db_session: Session) -> None:
        """Test updating a non-existent category."""
        # Create and login as admin user
        _, token = create_and_login_admin_user(client, db_session, "update_not_found")
        headers = {"Authorization": f"Bearer {token}"}

        update_data = {"display_name": "Updated Test Category"}

        response = client.put(f"{settings.API_STR}/categories/99999", json=update_data, headers=headers)
        assert response.status_code == 404
        assert "category" in response.json()["message"].lower() and "not found" in response.json()["message"].lower()

    def test_delete_category_success(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a category."""
        # Create and login as admin user
        _, token = create_and_login_admin_user(client, db_session, "delete_cat")
        headers = {"Authorization": f"Bearer {token}"}

        # First create a category
        category_data = {
            "name": "delete_test",
            "display_name": "Delete Test",
            "description": "A test category",
            "is_active": True,
            "sort_order": 50,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data, headers=headers)
        assert response.status_code == 200
        category_id = response.json()["id"]

        # Delete the category
        response = client.delete(f"{settings.API_STR}/categories/{category_id}", headers=headers)
        assert response.status_code == 200

        # Verify the category is deleted
        get_response = client.get(f"{settings.API_STR}/categories/{category_id}")
        assert get_response.status_code == 404

    def test_delete_category_not_found(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a non-existent category."""
        # Create and login as admin user
        _, token = create_and_login_admin_user(client, db_session, "delete_not_found")
        headers = {"Authorization": f"Bearer {token}"}

        response = client.delete(f"{settings.API_STR}/categories/99999", headers=headers)
        assert response.status_code == 404
        response_data = response.json()
        # Check that the error message indicates category not found (flexible matching)
        error_msg = response_data.get("detail", response_data.get("message", "")).lower()
        assert "category" in error_msg and "not found" in error_msg

    def test_delete_category_with_parts(self, client: TestClient, db_session: Session) -> None:
        """Test deleting a category that has parts (should fail)."""
        # Create and login as admin user (not used here, but kept for test setup clarity)
        _, _ = create_and_login_admin_user(client, db_session, "delete_with_parts")

        # Create a user and log them in
        _, user_token = create_and_login_user(client, "delete_with_parts")
        user_headers = {"Authorization": f"Bearer {user_token}"}

        # Create a car via admin (cars are now centrally managed)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car_id = create_car_via_admin_for_categories(client, db_session, admin_token)

        # Create a build list for the car
        build_list_id = create_build_list_for_car_cookie_auth(client, user_token, car_id)

        # Get a category ID that has parts
        category_id = get_default_category_id(db_session)

        # Create a part in that category
        # Create a brand for the part
        brand = Brand(name=get_unique_name("Test Brand"), description="Test brand", is_active=True)
        db_session.add(brand)
        db_session.commit()
        db_session.refresh(brand)

        part_data = {
            "name": "Test Part",
            "description": "Test part description",
            "price": 100,
            "build_list_id": build_list_id,
            "category_id": category_id,
            "brand_id": brand.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=user_headers)
        assert response.status_code == 200

        # Re-login as admin user for the delete operation
        _, admin_token2 = create_and_login_admin_user(client, db_session, "delete_with_parts_admin")
        admin_headers = {"Authorization": f"Bearer {admin_token2}"}

        # Try to delete the category
        response = client.delete(f"{settings.API_STR}/categories/{category_id}", headers=admin_headers)
        assert response.status_code == 409  # Conflict - category has associated parts
        response_data = response.json()
        # ResponsePatterns.raise_conflict uses "detail" key for HTTPException
        assert "Cannot delete category" in response_data.get("detail", response_data.get("message", ""))
        assert "associated parts" in response_data.get("detail", response_data.get("message", ""))

    def test_get_category_parts_count_success(self, client: TestClient, db_session: Session) -> None:
        """Test getting parts count for a category."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        # Get initial count
        response = client.get(f"{settings.API_STR}/categories/{category_id}/parts-count")
        assert response.status_code == 200
        initial_data = response.json()
        assert "parts_count" in initial_data
        initial_count = initial_data["parts_count"]
        assert isinstance(initial_count, int)
        assert initial_count >= 0

        # Create a user and log them in
        _, user_token = create_and_login_user(client, "parts_count_user")
        user_headers = {"Authorization": f"Bearer {user_token}"}

        # Create a car via admin (cars are now centrally managed)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car_id = create_car_via_admin_for_categories(client, db_session, admin_token)

        # Create a build list for the car
        build_list_id = create_build_list_for_car_cookie_auth(client, user_token, car_id)

        # Create a brand for the part
        brand = Brand(name=get_unique_name("Test Brand"), description="Test brand", is_active=True)
        db_session.add(brand)
        db_session.commit()
        db_session.refresh(brand)

        # Create a part in that category
        part_data = {
            "name": "Test Part for Count",
            "description": "Test part description",
            "price": 100,
            "build_list_id": build_list_id,
            "category_id": category_id,
            "brand_id": brand.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=user_headers)
        assert response.status_code == 200

        # Get count again (should be increased by 1)
        response = client.get(f"{settings.API_STR}/categories/{category_id}/parts-count")
        assert response.status_code == 200
        updated_data = response.json()
        assert "parts_count" in updated_data
        assert updated_data["parts_count"] == initial_count + 1

    def test_get_category_parts_count_not_found(self, client: TestClient, db_session: Session) -> None:
        """Test getting parts count for a non-existent category."""
        response = client.get(f"{settings.API_STR}/categories/99999/parts-count")
        assert response.status_code == 404
        assert (
            "category" in response.json().get("message", "").lower()
            or "not found" in response.json().get("message", "").lower()
        )

    def test_get_category_parts_count_public_endpoint(self, client: TestClient, db_session: Session) -> None:
        """Test that getting parts count works without authentication."""
        # Get a category ID from the database
        category_id = get_default_category_id(db_session)

        # Get parts count (public endpoint, no auth required)
        client.cookies.clear()
        response = client.get(f"{settings.API_STR}/categories/{category_id}/parts-count")
        assert response.status_code == 200
        data = response.json()
        assert "parts_count" in data
        assert isinstance(data["parts_count"], int)
        assert data["parts_count"] >= 0

    def test_count_categories_success(self, client: TestClient, db_session: Session) -> None:
        """Test counting categories."""
        # Get initial count (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/categories/count")
        assert response.status_code == 200
        initial_data = response.json()
        assert "count" in initial_data
        initial_count = initial_data["count"]
        assert isinstance(initial_count, int)
        assert initial_count >= 0

        # Create a category as admin
        _, token = create_and_login_admin_user(client, db_session, "count_cat")
        headers = {"Authorization": f"Bearer {token}"}

        category_data = {
            "name": get_unique_name("count_test"),
            "display_name": "Count Test Category",
            "description": "A test category for counting",
            "is_active": True,
            "sort_order": 50,
        }

        response = client.post(f"{settings.API_STR}/categories/", json=category_data, headers=headers)
        assert response.status_code == 200
        category_id = response.json()["id"]

        # Count again (should be increased by 1)
        response = client.get(f"{settings.API_STR}/categories/count")
        assert response.status_code == 200
        updated_data = response.json()
        assert "count" in updated_data
        assert updated_data["count"] == initial_count + 1

        # Delete the category
        response = client.delete(f"{settings.API_STR}/categories/{category_id}", headers=headers)
        assert response.status_code == 200

        # Count again (should be back to initial count)
        response = client.get(f"{settings.API_STR}/categories/count")
        assert response.status_code == 200
        final_data = response.json()
        assert final_data["count"] == initial_count

    def test_count_categories_public_endpoint(self, client: TestClient, db_session: Session) -> None:
        """Test that counting categories works without authentication."""
        # Count categories (public endpoint, no auth required)
        client.cookies.clear()
        response = client.get(f"{settings.API_STR}/categories/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
