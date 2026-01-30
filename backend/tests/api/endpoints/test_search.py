import os
from typing import Any, Dict

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.user import User as DBUser
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


def get_auth_headers(token: str) -> Dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {token}"}


def create_and_login_admin_user(
    client: TestClient, db_session: Session, username_suffix: str = "admin"
) -> tuple[Dict[str, Any], str]:
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


def create_car_via_admin(
    client: TestClient,
    admin_token: str,
    make: str = "Toyota",
    model: str = "Camry",
    generation_name: str = "8th Gen",
    start_year: int = 2018,
    end_year: int = 2024,
) -> Dict[str, Any]:
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


class TestSearch:
    """Test cases for search endpoint."""

    def test_search_all_public_access(self, client: TestClient) -> None:
        """Test that search endpoint is publicly accessible."""
        response = client.get(f"{settings.API_STR}/search/?q=test")
        assert response.status_code == 200
        data = response.json()
        assert "build_lists" in data
        assert "users" in data
        assert "global_parts" in data
        assert "query" in data

    def test_search_build_lists_by_name(self, client: TestClient, test_user: DBUser, db_session: Session) -> None:
        """Test searching build lists by name."""
        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token)

        # Create a build list
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_name = get_unique_name("searchable_build_list")
        build_list_data = {
            "name": build_list_name,
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search for the build list
        search_term = build_list_name.split("_")[0]  # Use part of the name
        response = client.get(f"{settings.API_STR}/search/?q={search_term}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["build_lists"]["data"]) > 0
        assert any(build_list_name in bl["name"] for bl in data["build_lists"]["data"])

    def test_search_build_lists_by_car_make(self, client: TestClient, test_user: DBUser, db_session: Session) -> None:
        """Test searching build lists by associated car make."""
        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token, make="Honda", model="Civic")

        # Create a build list
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_data = {
            "name": get_unique_name("honda_build_list"),
            "description": "A Honda build list",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search for "Honda"
        response = client.get(f"{settings.API_STR}/search/?q=Honda")
        assert response.status_code == 200
        data = response.json()
        assert len(data["build_lists"]["data"]) > 0
        # Verify the build list was found (search by car make works)
        # BuildListRead schema only includes car_id, not the full car object
        assert any(bl.get("car_id") == car["id"] for bl in data["build_lists"]["data"])

    def test_search_users_by_username(self, client: TestClient, test_user: DBUser) -> None:
        """Test searching users by username."""
        # Search for the test user's username
        search_term = test_user.username.split("_")[0]  # Use part of the username
        response = client.get(f"{settings.API_STR}/search/?q={search_term}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]["data"]) > 0
        assert any(search_term.lower() in u["username"].lower() for u in data["users"]["data"])

    def test_search_users_by_email(self, client: TestClient, test_user: DBUser) -> None:
        """Test searching users by email."""
        # Search for part of the email
        search_term = test_user.email.split("@")[0]  # Use part before @
        response = client.get(f"{settings.API_STR}/search/?q={search_term}")
        assert response.status_code == 200
        data = response.json()
        # Note: email might not be in PublicUserRead, so we check username matches
        assert len(data["users"]["data"]) > 0

    def test_search_global_parts_by_name(
        self, client: TestClient, test_user: DBUser, test_category, test_brand, db_session: Session
    ) -> None:
        """Test searching global parts by name."""
        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token)

        # Create a global part
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        part_name = get_unique_name("searchable_part")
        part_data = {
            "name": part_name,
            "description": "A test part description",
            "category_id": test_category.id,
            "car_id": car["id"],
            "brand_id": test_brand.id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Search for the part
        search_term = part_name.split("_")[0]  # Use part of the name
        response = client.get(f"{settings.API_STR}/search/?q={search_term}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["global_parts"]["data"]) > 0
        assert any(search_term.lower() in gp["name"].lower() for gp in data["global_parts"]["data"])

    def test_search_global_parts_by_brand(
        self, client: TestClient, test_user: DBUser, test_category, db_session: Session
    ) -> None:
        """Test searching global parts by brand."""
        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token)

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a brand "ACME" (any authenticated user can create)
        brand_resp = client.post(
            f"{settings.API_STR}/brands/",
            json={"name": "ACME", "description": "ACME brand", "is_active": True},
            headers=headers,
        )
        assert brand_resp.status_code == 200
        brand_id = brand_resp.json()["id"]

        # Create a global part with that brand
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": test_category.id,
            "car_id": car["id"],
            "brand_id": brand_id,
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200

        # Search for "ACME" (matches brand name)
        response = client.get(f"{settings.API_STR}/search/?q=ACME")
        assert response.status_code == 200
        data = response.json()
        assert len(data["global_parts"]["data"]) > 0
        assert any(gp.get("brand_id") == brand_id for gp in data["global_parts"]["data"])

    def test_search_empty_query(self, client: TestClient) -> None:
        """Test search with empty query."""
        response = client.get(f"{settings.API_STR}/search/?q=")
        assert response.status_code == 200
        data = response.json()
        assert data["build_lists"]["data"] == []
        assert data["users"]["data"] == []
        assert data["global_parts"]["data"] == []
        assert data["query"] == ""

    def test_search_no_results(self, client: TestClient) -> None:
        """Test search with query that returns no results."""
        response = client.get(f"{settings.API_STR}/search/?q=nonexistentxyz123")
        assert response.status_code == 200
        data = response.json()
        assert len(data["build_lists"]["data"]) == 0
        assert len(data["users"]["data"]) == 0
        assert len(data["global_parts"]["data"]) == 0

    def test_search_case_insensitive(self, client: TestClient, test_user: DBUser, db_session: Session) -> None:
        """Test that search is case-insensitive."""
        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token)

        # Create a build list with lowercase name
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_name = get_unique_name("lowercase_build_list")
        build_list_data = {
            "name": build_list_name,
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search with uppercase
        search_term = build_list_name.upper()
        response = client.get(f"{settings.API_STR}/search/?q={search_term}")
        assert response.status_code == 200
        data = response.json()
        # Should find results (case-insensitive)
        assert len(data["build_lists"]["data"]) > 0

    def test_search_with_pagination(self, client: TestClient, test_user: DBUser, db_session: Session) -> None:
        """Test search with pagination parameters."""
        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token)

        # Create multiple build lists
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        base_name = get_unique_name("paginated")
        for i in range(5):
            build_list_data = {
                "name": f"{base_name}_{i}",
                "description": f"Build list {i}",
                "car_id": car["id"],
            }
            response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
            assert response.status_code == 200

        # Search with pagination
        response = client.get(f"{settings.API_STR}/search/?q={base_name}&skip=0&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["build_lists"]["data"]) <= 2
        assert data["build_lists"]["limit"] == 2
        assert data["build_lists"]["skip"] == 0
        assert "total" in data["build_lists"]
        assert "has_next" in data["build_lists"]

    def test_search_partial_match(self, client: TestClient, test_user: DBUser, db_session: Session) -> None:
        """Test that search supports partial matches."""
        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token)

        # Create a build list with a specific name
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_name = get_unique_name("partial_match_test")
        build_list_data = {
            "name": build_list_name,
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search with partial match (just "partial")
        response = client.get(f"{settings.API_STR}/search/?q=partial")
        assert response.status_code == 200
        data = response.json()
        # Should find the build list with partial match
        assert len(data["build_lists"]["data"]) > 0

    def test_search_sql_injection_attempt(self, client: TestClient) -> None:
        """Test that search handles SQL injection attempts safely."""
        # Common SQL injection patterns
        sql_injection_attempts = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; SELECT * FROM users; --",
            "1' UNION SELECT NULL--",
        ]

        for attempt in sql_injection_attempts:
            response = client.get(f"{settings.API_STR}/search/?q={attempt}")
            # Should not crash, return 200 with empty or safe results
            assert response.status_code == 200
            data = response.json()
            assert "build_lists" in data
            assert "users" in data
            assert "global_parts" in data

    def test_search_special_characters(self, client: TestClient) -> None:
        """Test search with special characters."""
        special_chars = ["%", "_", "@", "#", "$", "&", "*", "(", ")", "[", "]", "{", "}", "|", "\\"]

        for char in special_chars:
            response = client.get(f"{settings.API_STR}/search/?q={char}")
            assert response.status_code == 200
            data = response.json()
            assert "build_lists" in data
            assert "users" in data
            assert "global_parts" in data

    def test_search_unicode_characters(self, client: TestClient, test_user: DBUser, db_session: Session) -> None:
        """Test search with unicode and emoji characters."""
        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token)

        # Create a build list with unicode characters
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_name = get_unique_name("unicode_test_🚗")
        build_list_data = {
            "name": build_list_name,
            "description": "Test with unicode: 测试 🚗",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search with unicode
        response = client.get(f"{settings.API_STR}/search/?q=🚗")
        assert response.status_code == 200
        data = response.json()
        # Should handle unicode gracefully
        assert "build_lists" in data

    def test_search_very_long_query(self, client: TestClient) -> None:
        """Test search with very long query string."""
        # Create a very long query (1000 characters)
        long_query = "a" * 1000
        response = client.get(f"{settings.API_STR}/search/?q={long_query}")
        # Should handle gracefully, not crash
        assert response.status_code == 200
        data = response.json()
        assert "build_lists" in data
        assert "users" in data
        assert "global_parts" in data

    def test_search_whitespace_only(self, client: TestClient) -> None:
        """Test search with whitespace-only query."""
        from urllib.parse import quote

        # Test with spaces, tabs, newlines (URL encode them)
        whitespace_queries = ["   ", "\t\t", "\n\n", "   \t\n   "]

        for query in whitespace_queries:
            encoded_query = quote(query)
            response = client.get(f"{settings.API_STR}/search/?q={encoded_query}")
            assert response.status_code == 200
            data = response.json()
            # Should return empty results or handle gracefully
            assert "build_lists" in data
            assert "users" in data
            assert "global_parts" in data

    def test_search_pagination_skip_beyond_total(
        self, client: TestClient, test_user: DBUser, db_session: Session
    ) -> None:
        """Test search pagination with skip beyond total results."""
        # Create a build list
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token)

        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search with skip beyond total (should return empty arrays for each category)
        response = client.get(f"{settings.API_STR}/search/?q=test_build_list&skip=1000&limit=10")
        assert response.status_code == 200
        data = response.json()
        # New API format returns dict with categories
        if isinstance(data, dict):
            assert "build_lists" in data
            assert "users" in data
            assert "global_parts" in data
            assert data["build_lists"]["data"] == []
            assert data["users"]["data"] == []
            assert data["global_parts"]["data"] == []
        else:
            # Old format (list) - for backward compatibility
            assert isinstance(data, list)
            assert len(data) == 0

    def test_search_pagination_limit_zero(self, client: TestClient) -> None:
        """Test search with limit=0 (should validate and reject)."""
        response = client.get(f"{settings.API_STR}/search/?q=test&limit=0")
        # Should validate and reject (400 or 422)
        assert response.status_code in [400, 422]

    def test_search_pagination_very_large_limit(self, client: TestClient) -> None:
        """Test search with very large limit value (should respect max limit)."""
        response = client.get(f"{settings.API_STR}/search/?q=test&limit=10000")
        # Endpoint validates limit with le=100, so 10000 should be rejected with 422
        assert response.status_code == 422
        data = response.json()
        # When validation fails, response is an error format, not search results
        assert "message" in data or "detail" in data

    def test_search_very_large_skip_value(self, client: TestClient) -> None:
        """Test search with very large skip value."""
        response = client.get(f"{settings.API_STR}/search/?q=test&skip=999999999&limit=10")
        assert response.status_code == 200
        data = response.json()

        # Should return empty results for all categories
        if isinstance(data, dict):
            assert data["build_lists"]["data"] == []
            assert data["users"]["data"] == []
            assert data["global_parts"]["data"] == []
        else:
            # Old format
            assert isinstance(data, list)
            assert len(data) == 0

    def test_search_case_insensitive_matching(self, client: TestClient, test_user: DBUser, db_session: Session) -> None:
        """Test that search is case-insensitive."""
        # Create a build list with mixed case
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token)

        build_list_name = get_unique_name("MiXeDcAsE")
        build_list_data = {
            "name": build_list_name,
            "description": "A test build list",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Search with different case variations
        for query in ["mixedcase", "MIXEDCASE", "MixedCase", "MiXeDcAsE"]:
            response = client.get(f"{settings.API_STR}/search/?q={query}")
            assert response.status_code == 200
            data = response.json()
            # Should find the build list regardless of case
            found = any(item.get("name") == build_list_name for item in data["build_lists"]["data"])
            assert found, f"Search with '{query}' should find '{build_list_name}'"
