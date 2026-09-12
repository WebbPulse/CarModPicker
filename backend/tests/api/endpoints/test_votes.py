"""Covers the vote endpoints: casting, changing and clearing votes on each entity type."""

import os
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.users import User
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import INVALID_UUID_STR, auth_headers, create_car_in_db, login_user, save_catalog


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
    username = f"admin_vote_test_{username_suffix}"
    email = f"admin_vote_test_{username_suffix}@example.com"
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


class TestUnifiedVotes:
    """Test cases for unified votes endpoints."""

    def test_upvote_car_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test successfully upvoting a car."""
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, get_unique_name("Honda"), "Civic", "10th Gen", 2016, 2021)

        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car_generation/{car['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["vote"]["entity_id"] == str(car["id"])
        assert data["vote"]["entity_type"] == "car_generation"
        assert data["vote"]["user_id"] == str(test_user.id)
        assert data["vote"]["vote_type"] == "upvote"
        assert data["upvotes"] == 1
        assert data["downvotes"] == 0
        assert data["total_votes"] == 1
        assert data["vote_score"] == 1

    def test_downvote_build_list_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test successfully downvoting a build list."""
        from app.db.dynamo.users import User as DBUser

        build_list_owner = UserRepository().create_user(
            DBUser(
                username=f"build_list_owner_{os.getpid()}_{id(db_session)}",
                email=f"build_list_owner_{os.getpid()}_{id(db_session)}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        build_list_owner_token = login_user(client, build_list_owner.username)
        build_list_owner_headers = auth_headers(build_list_owner_token)

        car = create_car_in_db(db_session)

        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(
            f"{settings.API_STR}/build-lists/", json=build_list_data, headers=build_list_owner_headers
        )
        assert response.status_code == 200
        build_list = response.json()

        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/votes/build_list/{build_list['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["vote"]["entity_id"] == build_list["id"]
        assert data["vote"]["entity_type"] == "build_list"
        assert data["vote"]["user_id"] == str(test_user.id)
        assert data["vote"]["vote_type"] == "downvote"
        assert data["upvotes"] == 0
        assert data["downvotes"] == 1
        assert data["vote_score"] == -1

    def test_vote_part_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test successfully voting on a global part."""
        from app.db.dynamo.users import User as DBUser

        part_owner = UserRepository().create_user(
            DBUser(
                username=f"part_owner_{os.getpid()}_{id(db_session)}",
                email=f"part_owner_{os.getpid()}_{id(db_session)}@example.com",
                email_verified=True,
                disabled=False,
                is_admin=False,
                is_superuser=False,
            )
        )

        from app.db.dynamo.catalog import Category as DBCategory

        category = DBCategory(name=get_unique_name("Test Category"))
        category = save_catalog(category)

        from app.db.dynamo.catalog import PartManufacturer as DBPartManufacturer

        part_manufacturer = DBPartManufacturer(
            name=get_unique_name("Test PartManufacturer"), description="Test part_manufacturer", is_active=True
        )
        part_manufacturer = save_catalog(part_manufacturer)

        part_owner_token = login_user(client, part_owner.username)
        part_owner_headers = auth_headers(part_owner_token)

        part_data = {
            "name": get_unique_name("Test Part"),
            "description": "A test part description",
            "category_id": str(category.id),
            "part_manufacturer_id": str(part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=part_owner_headers)
        assert response.status_code == 200
        part = response.json()

        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/part/{part['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["vote"]["entity_id"] == part["id"]
        assert data["vote"]["entity_type"] == "part"
        assert data["vote"]["user_id"] == str(test_user.id)
        assert data["vote"]["vote_type"] == "upvote"
        assert data["upvotes"] == 1
        assert data["downvotes"] == 0
        assert data["vote_score"] == 1

    def test_vote_unauthorized(self, client: TestClient, db_session: Any) -> None:
        """Test voting without authentication."""
        vote_data = {"vote_type": "upvote"}
        response = client.post(f"{settings.API_STR}/votes/car_generation/{INVALID_UUID_STR}", json=vote_data)
        assert response.status_code == 401

    def test_vote_entity_not_found(self, client: TestClient, test_user: User) -> None:
        """Test voting on an entity that doesn't exist."""
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car_generation/{INVALID_UUID_STR}", json=vote_data, headers=headers
        )
        assert response.status_code == 404

    def test_update_existing_vote(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test updating an existing vote."""
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, get_unique_name("Ford"), "Mustang", "S550", 2015, 2023)

        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car_generation/{car['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200
        first_vote = response.json()["vote"]
        assert first_vote["vote_type"] == "upvote"

        vote_data = {"vote_type": "downvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car_generation/{car['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["vote"]["id"] == first_vote["id"]
        assert updated["vote"]["vote_type"] == "downvote"
        assert updated["upvotes"] == 0
        assert updated["downvotes"] == 1
        assert updated["total_votes"] == 1
        assert updated["vote_score"] == -1

    def test_remove_vote_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test successfully removing a vote."""
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, get_unique_name("Chevrolet"), "Camaro", "6th Gen", 2016, 2023)

        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car_generation/{car['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        response = client.delete(f"{settings.API_STR}/votes/car_generation/{car['id']}", headers=test_user_headers)
        assert response.status_code == 200
        removed = response.json()
        assert removed["vote"] is None
        assert removed["upvotes"] == 0
        assert removed["downvotes"] == 0
        assert removed["total_votes"] == 0
        assert removed["vote_score"] == 0

    def test_remove_vote_not_found(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test removing a vote that doesn't exist."""
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, get_unique_name("BMW"), "3 Series", "G20", 2019, 2023)

        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        response = client.delete(f"{settings.API_STR}/votes/car_generation/{car['id']}", headers=test_user_headers)
        assert response.status_code == 404

    def test_get_vote_summary_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test successfully getting vote summary for an entity."""
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, get_unique_name("Audi"), "A4", "B9", 2016, 2023)

        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car_generation/{car['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/votes/car_generation/{car['id']}/summary", headers=test_user_headers)
        assert response.status_code == 200
        summary = response.json()
        assert summary["entity_id"] == str(car["id"])
        assert summary["entity_type"] == "car_generation"
        assert summary["upvotes"] == 1
        assert summary["downvotes"] == 0
        assert summary["total_votes"] == 1
        assert summary["vote_score"] == 1
        assert summary["user_vote"] == "upvote"

    def test_get_vote_summary_not_found(self, client: TestClient, test_user: User) -> None:
        """Test getting vote summary for an entity that doesn't exist."""
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        response = client.get(f"{settings.API_STR}/votes/car_generation/{INVALID_UUID_STR}/summary", headers=headers)
        assert response.status_code == 404

    def test_get_flagged_entities_admin_only(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test that getting flagged entities requires admin access."""
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        response = client.get(f"{settings.API_STR}/votes/admin/flagged/car_generation", headers=headers)
        assert response.status_code == 403

    def test_get_flagged_entities_success(self, client: TestClient, test_admin_user: User, db_session: Any) -> None:
        """Test successfully getting flagged entities as admin."""
        token = login_user(client, test_admin_user.username)
        headers = auth_headers(token)

        response = client.get(f"{settings.API_STR}/votes/admin/flagged/car_generation", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_vote_invalid_entity_type(self, client: TestClient, test_user: User) -> None:
        """Test voting with invalid entity type."""
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/invalid_type/{INVALID_UUID_STR}", json=vote_data, headers=headers
        )
        assert response.status_code == 422

    def test_vote_invalid_vote_type(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test voting with invalid vote type."""
        token = login_user(client, test_user.username)
        headers = auth_headers(token)

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, get_unique_name("Tesla"), "Model 3", "1st Gen", 2017, 2023)

        vote_data = {"vote_type": "invalid_vote"}
        response = client.post(f"{settings.API_STR}/votes/car_generation/{car['id']}", json=vote_data, headers=headers)
        assert response.status_code == 422

    def test_count_votes_success(self, client: TestClient, test_user: User, db_session: Any) -> None:
        """Test counting votes."""
        response = client.get(f"{settings.API_STR}/votes/count")
        assert response.status_code == 200
        initial_data = response.json()
        assert "count" in initial_data
        initial_count = initial_data["count"]
        assert isinstance(initial_count, int)
        assert initial_count >= 0

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_in_db(db_session, get_unique_name("Honda"), "Civic", "10th Gen", 2016, 2021)

        test_user_token = login_user(client, test_user.username)
        test_user_headers = auth_headers(test_user_token)

        vote_data = {"vote_type": "upvote"}
        response = client.post(
            f"{settings.API_STR}/votes/car_generation/{car['id']}",
            json=vote_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        response = client.get(f"{settings.API_STR}/votes/count")
        assert response.status_code == 200
        updated_data = response.json()
        assert "count" in updated_data
        assert updated_data["count"] == initial_count + 1

    def test_count_votes_public_endpoint(self, client: TestClient) -> None:
        """Test that counting votes works without authentication."""
        response = client.get(f"{settings.API_STR}/votes/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
