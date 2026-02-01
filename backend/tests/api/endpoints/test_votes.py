import os
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.user import User
from app.api.models.user import User as DBUser
from app.core.config import settings


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def get_auth_headers(token: str) -> dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {token}"}


def create_and_login_admin_user(
    client: TestClient, db_session: Session, username_suffix: str = "admin"
) -> tuple[dict[str, Any], str]:
    """Create an admin user and log them in. Returns (user_dict, token)."""
    username = f"admin_vote_test_{username_suffix}"
    email = f"admin_vote_test_{username_suffix}@example.com"
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


def create_car_via_admin(
    client: TestClient,
    admin_token: str,
    make: str = "Honda",
    model: str = "Civic",
    generation_name: str = "10th Gen",
    start_year: int = 2016,
    end_year: int = 2021,
) -> dict[str, Any]:
    """Create a car via admin endpoint and return the created car data."""
    headers = get_auth_headers(admin_token)
    car_data = {
        "make": make,
        "model": model,
        "generation_name": generation_name,
        "start_year": start_year,
        "end_year": end_year,
    }

    response = client.post(f"{settings.API_STR}/cars/admin/cars", json=car_data, headers=headers)
    assert response.status_code == 200, f"Failed to create car: {response.text}"
    return response.json()


class TestUnifiedVotes:
    """Test cases for unified votes endpoints."""

    def test_upvote_car_success(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test successfully upvoting a car."""
        # Create a car via admin (cars are now centrally managed)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token, get_unique_name("Honda"), "Civic", "10th Gen", 2016, 2021)

        # Login as test user and upvote the car
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        test_user_headers = {"Authorization": f"Bearer {test_user_token}"}

        # Upvote the car
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car/{car['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["entity_id"] == car["id"]
        assert data["entity_type"] == "car"
        assert data["user_id"] == test_user.id
        assert data["vote_type"] == "upvote"

    def test_downvote_build_list_success(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test successfully downvoting a build list."""
        # Create a second user to own the build list
        from app.api.dependencies.auth import get_password_hash
        from app.api.models.user import User as DBUser

        build_list_owner = DBUser(
            username=f"build_list_owner_{os.getpid()}_{id(db_session)}",
            email=f"build_list_owner_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(build_list_owner)
        db_session.commit()
        db_session.refresh(build_list_owner)

        # Login as build list owner and create a build list
        login_data = {"username": build_list_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        build_list_owner_token = response.json()["access_token"]
        build_list_owner_headers = {"Authorization": f"Bearer {build_list_owner_token}"}

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token)

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/", json=build_list_data, headers=build_list_owner_headers
        )
        assert response.status_code == 200
        build_list = response.json()

        # Login as test user and downvote the build list
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        test_user_headers = {"Authorization": f"Bearer {test_user_token}"}

        # Downvote the build list
        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/votes/build_list/{build_list['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["entity_id"] == build_list["id"]
        assert data["entity_type"] == "build_list"
        assert data["user_id"] == test_user.id
        assert data["vote_type"] == "downvote"

    def test_vote_global_part_success(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test successfully voting on a global part."""
        # Create a second user to own the global part
        from app.api.dependencies.auth import get_password_hash
        from app.api.models.user import User as DBUser

        part_owner = DBUser(
            username=f"part_owner_{os.getpid()}_{id(db_session)}",
            email=f"part_owner_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(part_owner)
        db_session.commit()
        db_session.refresh(part_owner)

        # Create a category first
        from app.api.models.category import Category as DBCategory

        category = DBCategory(name=get_unique_name("Test Category"))
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

        # Create a brand
        from app.api.models.brand import Brand as DBBrand

        brand = DBBrand(name=get_unique_name("Test Brand"), description="Test brand", is_active=True)
        db_session.add(brand)
        db_session.commit()
        db_session.refresh(brand)

        # Login as part owner and create a global part
        login_data = {"username": part_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        part_owner_token = response.json()["access_token"]
        part_owner_headers = {"Authorization": f"Bearer {part_owner_token}"}

        # Create a global part
        part_data = {
            "name": get_unique_name("Test Part"),
            "description": "A test part description",
            "category_id": category.id,
            "brand_id": brand.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=part_owner_headers)
        assert response.status_code == 200
        part = response.json()

        # Login as test user and upvote the part
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        test_user_headers = {"Authorization": f"Bearer {test_user_token}"}

        # Upvote the part
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/global_part/{part['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["entity_id"] == part["id"]
        assert data["entity_type"] == "global_part"
        assert data["user_id"] == test_user.id
        assert data["vote_type"] == "upvote"

    def test_vote_unauthorized(self, client: TestClient, db_session: Session) -> None:
        """Test voting without authentication."""
        # Try to upvote without authentication
        vote_data = {"vote_type": "upvote"}
        response = client.post(f"{settings.API_STR}/votes/car/1", json=vote_data)
        assert response.status_code == 401

    def test_vote_entity_not_found(self, client: TestClient, test_user: User) -> None:
        """Test voting on an entity that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to vote on non-existent entity
        vote_data = {"vote_type": "upvote"}
        response = client.post(f"{settings.API_STR}/votes/car/99999", json=vote_data, headers=headers)
        assert response.status_code == 404

    def test_update_existing_vote(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test updating an existing vote."""
        # Create a car via admin (cars are now centrally managed)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token, get_unique_name("Ford"), "Mustang", "S550", 2015, 2023)

        # Login as test user and vote
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        test_user_headers = {"Authorization": f"Bearer {test_user_token}"}

        # First upvote
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car/{car['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200
        first_vote = response.json()
        assert first_vote["vote_type"] == "upvote"

        # Change to downvote
        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car/{car['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200
        updated_vote = response.json()
        assert updated_vote["id"] == first_vote["id"]
        assert updated_vote["vote_type"] == "downvote"

    def test_remove_vote_success(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test successfully removing a vote."""
        # Create a car via admin (cars are now centrally managed)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token, get_unique_name("Chevrolet"), "Camaro", "6th Gen", 2016, 2023)

        # Login as test user and create a vote
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        test_user_headers = {"Authorization": f"Bearer {test_user_token}"}

        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car/{car['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        # Remove the vote
        response = client.delete(f"{settings.API_STR}/votes/car/{car['id']}", headers=test_user_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Vote removed successfully"

    def test_remove_vote_not_found(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test removing a vote that doesn't exist."""
        # Create a car via admin (cars are now centrally managed)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token, get_unique_name("BMW"), "3 Series", "G20", 2019, 2023)

        # Login as test user and try to remove non-existent vote
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        test_user_headers = {"Authorization": f"Bearer {test_user_token}"}

        response = client.delete(f"{settings.API_STR}/votes/car/{car['id']}", headers=test_user_headers)
        assert response.status_code == 404

    def test_get_vote_summary_success(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test successfully getting vote summary for an entity."""
        # Create a car via admin (cars are now centrally managed)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token, get_unique_name("Audi"), "A4", "B9", 2016, 2023)

        # Login as test user and create an upvote
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        test_user_headers = {"Authorization": f"Bearer {test_user_token}"}

        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car/{car['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        # Get vote summary
        response = client.get(f"{settings.API_STR}/votes/car/{car['id']}/summary", headers=test_user_headers)
        assert response.status_code == 200
        summary = response.json()
        assert summary["entity_id"] == car["id"]
        assert summary["entity_type"] == "car"
        assert summary["upvotes"] == 1
        assert summary["downvotes"] == 0
        assert summary["total_votes"] == 1
        assert summary["vote_score"] == 1
        assert summary["user_vote"] == "upvote"

    def test_get_vote_summary_not_found(self, client: TestClient, test_user: User) -> None:
        """Test getting vote summary for an entity that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to get vote summary for non-existent entity
        response = client.get(f"{settings.API_STR}/votes/car/99999/summary", headers=headers)
        assert response.status_code == 404

    def test_get_flagged_entities_admin_only(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test that getting flagged entities requires admin access."""
        # Login as regular user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to get flagged entities
        response = client.get(f"{settings.API_STR}/votes/admin/flagged/car", headers=headers)
        assert response.status_code == 403

    def test_get_flagged_entities_success(self, client: TestClient, test_admin_user: User, db_session: Session) -> None:
        """Test successfully getting flagged entities as admin."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get flagged entities
        response = client.get(f"{settings.API_STR}/votes/admin/flagged/car", headers=headers)
        assert response.status_code == 200
        # Should return empty list if no entities meet flagging criteria
        assert isinstance(response.json(), list)

    def test_vote_invalid_entity_type(self, client: TestClient, test_user: User) -> None:
        """Test voting with invalid entity type."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to vote with invalid entity type
        vote_data = {"vote_type": "upvote"}
        response = client.post(f"{settings.API_STR}/votes/invalid_type/1", json=vote_data, headers=headers)
        assert response.status_code == 422  # Validation error

    def test_vote_invalid_vote_type(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test voting with invalid vote type."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a car via admin (cars are now centrally managed)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token, get_unique_name("Tesla"), "Model 3", "1st Gen", 2017, 2023)

        # Try to vote with invalid vote type
        vote_data = {"vote_type": "invalid_vote"}
        response = client.post(f"{settings.API_STR}/votes/car/{car['id']}", json=vote_data, headers=headers)
        assert response.status_code == 422  # Validation error

    def test_count_votes_success(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test counting votes."""
        # Get initial count (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/votes/count")
        assert response.status_code == 200
        initial_data = response.json()
        assert "count" in initial_data
        initial_count = initial_data["count"]
        assert isinstance(initial_count, int)
        assert initial_count >= 0

        # Create a car via admin (cars are now centrally managed)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token, get_unique_name("Honda"), "Civic", "10th Gen", 2016, 2021)

        # Login as test user and vote
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        test_user_headers = {"Authorization": f"Bearer {test_user_token}"}

        # Upvote the car
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car/{car['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        # Count again (should be increased by 1)
        response = client.get(f"{settings.API_STR}/votes/count")
        assert response.status_code == 200
        updated_data = response.json()
        assert "count" in updated_data
        assert updated_data["count"] == initial_count + 1

    def test_count_votes_public_endpoint(self, client: TestClient) -> None:
        """Test that counting votes works without authentication."""
        # Count votes (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/votes/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
