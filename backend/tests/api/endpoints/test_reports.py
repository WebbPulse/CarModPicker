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


def create_and_login_admin_user(
    client: TestClient, db_session: Session, username_suffix: str = "admin"
) -> tuple[dict[str, Any], str]:
    """Create an admin user and log them in. Returns (user_dict, token)."""
    from app.api.dependencies.auth import get_password_hash
    from app.api.models.user import User as DBUser

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
    make: str = "Honda",
    model: str = "Civic",
    generation_name: str = "10th Gen",
    start_year: int = 2016,
    end_year: int = 2021,
) -> dict[str, Any]:
    """Create a car via admin endpoint and return the created car data."""
    headers = {"Authorization": f"Bearer {admin_token}"}
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


class TestUnifiedReports:
    """Test cases for unified reports endpoints."""

    def test_create_build_list_report_success(
        self,
        client: TestClient,
        test_user: User,
        db_session: Session,
    ) -> None:
        """Test successfully creating a report for a build list."""
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

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {test_user_token}"}

        # Create a report
        report_data = {
            "reason": "spam",
            "description": "This build list is spam",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}",
            json=report_data,
            headers=headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["entity_id"] == build_list["id"]
        assert data["entity_type"] == "build_list"
        assert data["user_id"] == test_user.id
        assert data["reason"] == "spam"
        assert data["description"] == "This build list is spam"
        assert data["status"] == "pending"

    def test_create_global_part_report_success(
        self,
        client: TestClient,
        test_user: User,
        db_session: Session,
    ) -> None:
        """Test successfully creating a report for a global part."""
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

        # Login as part owner and create a global part
        login_data = {"username": part_owner.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        part_owner_token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {part_owner_token}"}

        # Create a global part
        part_data = {
            "name": get_unique_name("Test Part"),
            "description": "A test part description",
            "category_id": category.id,
            "price": 9999,  # price in cents (99.99)
        }
        response = client.post(f"{settings.API_STR}/global-parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part = response.json()

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        test_user_headers = {"Authorization": f"Bearer {test_user_token}"}

        # Create a report
        report_data = {
            "reason": "inaccurate",
            "description": "This part information is inaccurate",
        }
        response = client.post(
            f"{settings.API_STR}/reports/global_part/{part['id']}",
            json=report_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["entity_id"] == part["id"]
        assert data["entity_type"] == "global_part"
        assert data["user_id"] == test_user.id
        assert data["reason"] == "inaccurate"
        assert data["description"] == "This part information is inaccurate"
        assert data["status"] == "pending"

    def test_create_report_unauthorized(self, client: TestClient, db_session: Session) -> None:
        """Test creating a report without authentication."""
        # Try to create a report without authentication
        report_data = {
            "reason": "inappropriate_content",
            "description": "This entity contains inappropriate content",
        }
        response = client.post(f"{settings.API_STR}/reports/build_list/1", json=report_data)
        assert response.status_code == 401

    def test_create_report_entity_not_found(self, client: TestClient, test_user: User) -> None:
        """Test creating a report for an entity that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to report non-existent entity
        report_data = {
            "reason": "inappropriate_content",
            "description": "This entity contains inappropriate content",
        }
        response = client.post(f"{settings.API_STR}/reports/build_list/99999", json=report_data, headers=headers)
        assert response.status_code == 404

    def test_create_report_own_entity(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test that users cannot report their own entities."""
        # Login as test user and create a build list
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a car first (requires admin)
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("car_creator"))
        car = create_car_via_admin(client, admin_token)

        # Create a build list owned by test user
        build_list_data = {
            "name": get_unique_name("Test Build List"),
            "description": "A test build list description",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list = response.json()

        # Try to report own build list (should fail)
        report_data = {
            "reason": "inappropriate_content",
            "description": "This build list contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}", json=report_data, headers=headers
        )
        assert response.status_code == 400
        response_data = response.json()
        # Handle both "detail" and "message" response formats
        error_text = response_data.get("detail", response_data.get("message", "")).lower()
        assert "cannot report your own" in error_text or "report your own" in error_text

    def test_create_report_already_reported(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test that users cannot report the same entity twice."""
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

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        test_user_headers = {"Authorization": f"Bearer {test_user_token}"}

        # Create first report
        report_data = {
            "reason": "inappropriate_content",
            "description": "This build list contains inappropriate content",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}",
            json=report_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200

        # Try to create second report
        report_data = {
            "reason": "spam",
            "description": "This build list is spam",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}",
            json=report_data,
            headers=test_user_headers,
        )
        assert response.status_code == 400
        assert "already reported" in response.json()["message"]

    def test_list_reports_admin_only(self, client: TestClient, test_user: User) -> None:
        """Test that listing reports requires admin access."""
        # Login as regular user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to list reports
        response = client.get(f"{settings.API_STR}/reports/admin/list", headers=headers)
        assert response.status_code == 403

    def test_list_reports_success(self, client: TestClient, test_admin_user: User, db_session: Session) -> None:
        """Test successfully listing reports as admin."""
        # Login as admin user
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # List reports
        response = client.get(f"{settings.API_STR}/reports/admin/list", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_my_reports_success(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test successfully getting user's own reports."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get my reports
        response = client.get(f"{settings.API_STR}/reports/my-reports", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_report_by_id_success(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test successfully getting a specific report by ID."""
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

        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        test_user_headers = {"Authorization": f"Bearer {test_user_token}"}

        # Create a report
        report_data = {
            "reason": "spam",
            "description": "This build list is spam",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}",
            json=report_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200
        report = response.json()

        # Get the report by ID
        response = client.get(f"{settings.API_STR}/reports/{report['id']}", headers=test_user_headers)
        assert response.status_code == 200
        retrieved_report = response.json()
        assert retrieved_report["id"] == report["id"]
        assert retrieved_report["entity_id"] == build_list["id"]

    def test_get_report_by_id_not_found(self, client: TestClient, test_user: User) -> None:
        """Test getting a report that doesn't exist."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to get non-existent report
        response = client.get(f"{settings.API_STR}/reports/99999", headers=headers)
        assert response.status_code == 404

    def test_update_report_status_admin_only(self, client: TestClient, test_user: User) -> None:
        """Test that updating report status requires admin access."""
        # Login as regular user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to update report status
        update_data = {"status": "resolved", "admin_notes": "Issue resolved"}
        response = client.put(f"{settings.API_STR}/reports/1", json=update_data, headers=headers)
        assert response.status_code == 403

    def test_update_report_status_success(self, client: TestClient, test_admin_user: User, db_session: Session) -> None:
        """Test successfully updating report status as admin."""
        from app.api.dependencies.auth import get_password_hash
        from app.api.models.user import User as DBUser

        # Create a test user to own the build list
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

        # Create a test user to make the report
        test_user = DBUser(
            username=f"test_user_{os.getpid()}_{id(db_session)}",
            email=f"test_user_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        test_user_headers = {"Authorization": f"Bearer {test_user_token}"}

        # Create a report
        report_data = {
            "reason": "duplicate",
            "description": "This build list is a duplicate",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}",
            json=report_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200
        report = response.json()

        # Login as admin and update report status
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        admin_token = response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        update_data = {"status": "resolved", "admin_notes": "Issue resolved"}
        response = client.put(f"{settings.API_STR}/reports/{report['id']}", json=update_data, headers=admin_headers)
        assert response.status_code == 200
        updated_report = response.json()
        assert updated_report["status"] == "resolved"
        assert updated_report["admin_notes"] == "Issue resolved"

    def test_delete_report_admin_only(self, client: TestClient, test_user: User) -> None:
        """Test that deleting reports requires admin access."""
        # Login as regular user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to delete report
        response = client.delete(f"{settings.API_STR}/reports/1", headers=headers)
        assert response.status_code == 403

    def test_delete_report_success(self, client: TestClient, test_admin_user: User, db_session: Session) -> None:
        """Test successfully deleting a report as admin."""
        from app.api.dependencies.auth import get_password_hash
        from app.api.models.user import User as DBUser

        # Create a test user to own the build list
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

        # Create a test user to make the report
        test_user = DBUser(
            username=f"test_user2_{os.getpid()}_{id(db_session)}",
            email=f"test_user2_{os.getpid()}_{id(db_session)}@example.com",
            hashed_password=get_password_hash("testpassword"),
            email_verified=True,
            disabled=False,
            is_admin=False,
            is_superuser=False,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Login as test user and create a report
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        test_user_token = response.json()["access_token"]
        test_user_headers = {"Authorization": f"Bearer {test_user_token}"}

        # Create a report
        report_data = {
            "reason": "other",
            "description": "Other issue with this build list",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}",
            json=report_data,
            headers=test_user_headers,
        )
        assert response.status_code == 200
        report = response.json()

        # Login as admin and delete report
        login_data = {"username": test_admin_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        admin_token = response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        response = client.delete(f"{settings.API_STR}/reports/{report['id']}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Report deleted successfully"

    def test_report_invalid_entity_type(self, client: TestClient, test_user: User) -> None:
        """Test reporting with invalid entity type."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to report with invalid entity type
        report_data = {
            "reason": "inappropriate_content",
            "description": "This entity contains inappropriate content",
        }
        response = client.post(f"{settings.API_STR}/reports/invalid_type/1", json=report_data, headers=headers)
        assert response.status_code == 422  # Validation error

    def test_report_invalid_reason(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test reporting with invalid reason."""
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

        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to report with invalid reason
        report_data = {
            "reason": "invalid_reason",
            "description": "This build list has an invalid reason",
        }
        response = client.post(
            f"{settings.API_STR}/reports/build_list/{build_list['id']}", json=report_data, headers=headers
        )
        assert response.status_code == 422  # Validation error
