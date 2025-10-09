import os
from typing import Any
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.models.user import User
from app.api.models.category import Category


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestUnifiedVotes:
    """Test cases for unified votes endpoints."""

    def test_upvote_car_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully upvoting a car."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Honda"),
            "model": "Civic",
            "year": 2022,
            "trim": "Sport",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Upvote the car
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car/{car['id']}",
            json=vote_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["entity_id"] == car["id"]
        assert data["entity_type"] == "car"
        assert data["user_id"] == test_user.id
        assert data["vote_type"] == "upvote"

    def test_downvote_build_list_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully downvoting a build list."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a build list
        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data)
        assert response.status_code == 200
        build_list = response.json()

        # Downvote the build list
        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/votes/build_list/{build_list['id']}",
            json=vote_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["entity_id"] == build_list["id"]
        assert data["entity_type"] == "build_list"
        assert data["user_id"] == test_user.id
        assert data["vote_type"] == "downvote"

    def test_vote_global_part_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully voting on a global part."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a category first
        from app.api.models.category import Category as DBCategory

        category = DBCategory(name=get_unique_name("Test Category"))
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

        # Create a global part
        part_data = {
            "name": get_unique_name("Test Part"),
            "description": "A test part description",
            "category_id": category.id,
            "price": 99.99,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data)
        assert response.status_code == 200
        part = response.json()

        # Upvote the part
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/global_part/{part['id']}",
            json=vote_data,
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

        # Try to vote on non-existent entity
        vote_data = {"vote_type": "upvote"}
        response = client.post(f"{settings.API_STR}/votes/car/99999", json=vote_data)
        assert response.status_code == 404

    def test_update_existing_vote(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test updating an existing vote."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Ford"),
            "model": "Mustang",
            "year": 2023,
            "trim": "GT",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # First upvote
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car/{car['id']}",
            json=vote_data,
        )
        assert response.status_code == 200
        first_vote = response.json()
        assert first_vote["vote_type"] == "upvote"

        # Change to downvote
        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car/{car['id']}",
            json=vote_data,
        )
        assert response.status_code == 200
        updated_vote = response.json()
        assert updated_vote["id"] == first_vote["id"]
        assert updated_vote["vote_type"] == "downvote"

    def test_remove_vote_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully removing a vote."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Chevrolet"),
            "model": "Camaro",
            "year": 2022,
            "trim": "SS",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Create a vote
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car/{car['id']}",
            json=vote_data,
        )
        assert response.status_code == 200

        # Remove the vote
        response = client.delete(f"{settings.API_STR}/votes/car/{car['id']}")
        assert response.status_code == 200
        assert response.json()["message"] == "Vote removed successfully"

    def test_remove_vote_not_found(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test removing a vote that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("BMW"),
            "model": "3 Series",
            "year": 2021,
            "trim": "330i",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Try to remove non-existent vote
        response = client.delete(f"{settings.API_STR}/votes/car/{car['id']}")
        assert response.status_code == 404

    def test_get_vote_summary_success(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test successfully getting vote summary for an entity."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Audi"),
            "model": "A4",
            "year": 2023,
            "trim": "Premium",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Create an upvote
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car/{car['id']}",
            json=vote_data,
        )
        assert response.status_code == 200

        # Get vote summary
        response = client.get(f"{settings.API_STR}/votes/car/{car['id']}/summary")
        assert response.status_code == 200
        summary = response.json()
        assert summary["entity_id"] == car["id"]
        assert summary["entity_type"] == "car"
        assert summary["upvotes"] == 1
        assert summary["downvotes"] == 0
        assert summary["total_votes"] == 1
        assert summary["vote_score"] == 1
        assert summary["user_vote"] == "upvote"

    def test_get_vote_summary_not_found(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test getting vote summary for an entity that doesn't exist."""
        # Try to get vote summary for non-existent entity
        response = client.get(f"{settings.API_STR}/votes/car/99999/summary")
        assert response.status_code == 404

    def test_get_flagged_entities_admin_only(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test that getting flagged entities requires admin access."""
        # Login as regular user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to get flagged entities
        response = client.get(f"{settings.API_STR}/votes/admin/flagged/car")
        assert response.status_code == 403

    def test_get_flagged_entities_success(
        self, client: TestClient, test_admin_user: User, db_session: Session
    ) -> None:
        """Test successfully getting flagged entities as admin."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Get flagged entities
        response = client.get(f"{settings.API_STR}/votes/admin/flagged/car")
        assert response.status_code == 200
        # Should return empty list if no entities meet flagging criteria
        assert isinstance(response.json(), list)

    def test_vote_invalid_entity_type(
        self, client: TestClient, test_user: User
    ) -> None:
        """Test voting with invalid entity type."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Try to vote with invalid entity type
        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/invalid_type/1", json=vote_data
        )
        assert response.status_code == 422  # Validation error

    def test_vote_invalid_vote_type(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """Test voting with invalid vote type."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200

        # Create a car
        car_data = {
            "make": get_unique_name("Tesla"),
            "model": "Model 3",
            "year": 2023,
            "trim": "Performance",
        }
        response = client.post(f"{settings.API_STR}/cars/", json=car_data)
        assert response.status_code == 200
        car = response.json()

        # Try to vote with invalid vote type
        vote_data = {"vote_type": "invalid_vote"}
        response = client.post(
            f"{settings.API_STR}/votes/car/{car['id']}", json=vote_data
        )
        assert response.status_code == 422  # Validation error
