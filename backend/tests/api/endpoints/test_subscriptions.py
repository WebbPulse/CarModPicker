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


class TestSubscriptions:
    """Test cases for subscriptions endpoints."""

    def test_get_subscription_status(self, client: TestClient, test_user: User) -> None:
        """Test retrieving subscription status for the current user."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get subscription status
        response = client.get(f"{settings.API_STR}/subscriptions/status", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert "tier" in data
        assert "status" in data
        assert "limits" in data
        assert "usage" in data

    def test_get_subscription_status_unauthorized(self, client: TestClient) -> None:
        """Test retrieving subscription status without authentication."""
        response = client.get(f"{settings.API_STR}/subscriptions/status")
        assert response.status_code == 401

    def test_upgrade_subscription_success(self, client: TestClient, test_user: User) -> None:
        """Test successfully upgrading to premium subscription."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upgrade to premium
        upgrade_data = {
            "tier": "premium",
            "payment_method": "mock_payment",
        }
        response = client.post(f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert "user_id" in data
        assert "tier" in data
        assert "status" in data

    def test_upgrade_subscription_unauthorized(self, client: TestClient) -> None:
        """Test upgrading subscription without authentication."""
        upgrade_data = {
            "tier": "premium",
            "payment_method": "mock_payment",
        }
        response = client.post(f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data)
        assert response.status_code == 401

    def test_upgrade_subscription_invalid_tier(self, client: TestClient, test_user: User) -> None:
        """Test upgrading to an invalid subscription tier."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to upgrade to invalid tier
        upgrade_data = {
            "tier": "invalid_tier",
            "payment_method": "mock_payment",
        }
        response = client.post(f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data, headers=headers)
        assert response.status_code == 400

    def test_upgrade_subscription_already_premium(self, client: TestClient, test_user: User) -> None:
        """Test upgrading when user already has premium subscription."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # First upgrade to premium
        upgrade_data = {
            "tier": "premium",
            "payment_method": "mock_payment",
        }
        response = client.post(f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data, headers=headers)
        assert response.status_code == 200

        # Try to upgrade again
        response = client.post(f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data, headers=headers)
        assert response.status_code == 409  # 409 Conflict is correct for already having premium

    def test_cancel_subscription_success(self, client: TestClient, test_user: Any) -> None:
        """Test successfully canceling premium subscription."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # First upgrade to premium
        upgrade_data = {
            "tier": "premium",
            "payment_method": "mock_payment",
        }
        response = client.post(f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data, headers=headers)
        assert response.status_code == 200

        # Cancel subscription
        response = client.post(f"{settings.API_STR}/subscriptions/cancel", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert "user_id" in data
        assert "tier" in data
        assert "status" in data

    def test_cancel_subscription_unauthorized(self, client: TestClient) -> None:
        """Test canceling subscription without authentication."""
        response = client.post(f"{settings.API_STR}/subscriptions/cancel")
        assert response.status_code == 401

    def test_cancel_subscription_not_premium(self, client: TestClient, test_user: Any) -> None:
        """Test canceling subscription when user doesn't have premium."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to cancel without having premium
        response = client.post(f"{settings.API_STR}/subscriptions/cancel", headers=headers)
        assert response.status_code == 400

    def test_subscription_limits_and_usage(self, client: TestClient, test_user: User) -> None:
        """Test that subscription status includes limits and usage information."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get subscription status
        response = client.get(f"{settings.API_STR}/subscriptions/status", headers=headers)
        assert response.status_code == 200

        data = response.json()

        # Check limits structure
        assert "limits" in data
        limits = data["limits"]
        assert "build_lists" in limits
        assert "cars" in limits
        assert isinstance(limits["build_lists"], (int, type(None)))
        assert isinstance(limits["cars"], (int, type(None)))

        # Check usage structure
        assert "usage" in data
        usage = data["usage"]
        assert "build_lists" in usage
        assert "cars" in usage
        assert isinstance(usage["build_lists"], int)
        assert isinstance(usage["cars"], int)

    def test_subscription_tier_transitions(self, client: TestClient, test_user: User) -> None:
        """Test subscription tier transitions (free -> premium -> canceled)."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check initial status (should be free)
        response = client.get(f"{settings.API_STR}/subscriptions/status", headers=headers)
        assert response.status_code == 200
        initial_data = response.json()
        assert initial_data["tier"] == "free"

        # Upgrade to premium
        upgrade_data = {
            "tier": "premium",
            "payment_method": "mock_payment",
        }
        response = client.post(f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data, headers=headers)
        assert response.status_code == 200

        # Check premium status
        response = client.get(f"{settings.API_STR}/subscriptions/status", headers=headers)
        assert response.status_code == 200
        premium_data = response.json()
        assert premium_data["tier"] == "premium"
        assert premium_data["status"] == "active"

        # Cancel subscription
        response = client.post(f"{settings.API_STR}/subscriptions/cancel", headers=headers)
        assert response.status_code == 200

        # Check canceled status
        response = client.get(f"{settings.API_STR}/subscriptions/status", headers=headers)
        assert response.status_code == 200
        canceled_data = response.json()
        assert canceled_data["tier"] == "premium"
        assert canceled_data["status"] == "cancelled"

    def test_subscription_service_integration(self, client: TestClient, test_user: User, db_session: Session) -> None:
        """Test that subscription service properly integrates with user limits."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get initial subscription status
        response = client.get(f"{settings.API_STR}/subscriptions/status", headers=headers)
        assert response.status_code == 200
        initial_data = response.json()
        initial_usage = initial_data["usage"]["build_lists"]

        # Create a car first (requires admin)
        from app.api.dependencies.auth import get_password_hash
        from app.api.models.user import User as DBUser

        admin_user = DBUser(
            username=f"admin_sub_{os.getpid()}",
            email=f"admin_sub_{os.getpid()}@example.com",
            hashed_password=get_password_hash("testpassword"),
            is_admin=True,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
        db_session.add(admin_user)
        db_session.commit()
        db_session.refresh(admin_user)
        admin_login_data = {"username": admin_user.username, "password": "testpassword"}
        admin_token_response = client.post(f"{settings.API_STR}/auth/token", data=admin_login_data)
        admin_token = admin_token_response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        car_data = {
            "make": "Toyota",
            "model": "Camry",
            "generation_name": "8th Gen",
            "start_year": 2018,
            "end_year": 2024,
        }
        response = client.post(f"{settings.API_STR}/cars/admin/cars", json=car_data, headers=admin_headers)
        assert response.status_code == 200
        car = response.json()

        # Create a build list (should increment usage)
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "Test build list",
            "car_id": car["id"],
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200

        # Check that usage increased
        response = client.get(f"{settings.API_STR}/subscriptions/status", headers=headers)
        assert response.status_code == 200
        updated_data = response.json()
        updated_usage = updated_data["usage"]["build_lists"]
        assert updated_usage == initial_usage + 1

    def test_count_subscriptions_success(self, client: TestClient, test_user: User) -> None:
        """Test counting subscriptions."""
        # Get initial count (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/subscriptions/count")
        assert response.status_code == 200
        initial_data = response.json()
        assert "count" in initial_data
        initial_count = initial_data["count"]
        assert isinstance(initial_count, int)
        assert initial_count >= 0

        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upgrade to premium (creates a subscription)
        upgrade_data = {
            "tier": "premium",
            "payment_method": "mock_payment",
        }
        response = client.post(f"{settings.API_STR}/subscriptions/upgrade", json=upgrade_data, headers=headers)
        assert response.status_code == 200

        # Count again (should be increased by 1)
        response = client.get(f"{settings.API_STR}/subscriptions/count")
        assert response.status_code == 200
        updated_data = response.json()
        assert "count" in updated_data
        assert updated_data["count"] == initial_count + 1

    def test_count_subscriptions_public_endpoint(self, client: TestClient) -> None:
        """Test that counting subscriptions works without authentication."""
        # Count subscriptions (public endpoint, no auth required)
        response = client.get(f"{settings.API_STR}/subscriptions/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0

    def test_check_creation_limits_car(self, client: TestClient, test_user: User) -> None:
        """Test checking creation limits for cars."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check if user can create a car
        response = client.get(f"{settings.API_STR}/subscriptions/limits/check?resource_type=car", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "can_create" in data
        assert isinstance(data["can_create"], bool)

    def test_check_creation_limits_build_list(self, client: TestClient, test_user: User) -> None:
        """Test checking creation limits for build lists."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check if user can create a build list
        response = client.get(
            f"{settings.API_STR}/subscriptions/limits/check?resource_type=build_list", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "can_create" in data
        assert isinstance(data["can_create"], bool)

    def test_check_creation_limits_invalid_resource_type(self, client: TestClient, test_user: User) -> None:
        """Test checking creation limits with invalid resource type."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check with invalid resource type
        response = client.get(f"{settings.API_STR}/subscriptions/limits/check?resource_type=invalid", headers=headers)
        assert response.status_code == 400

    def test_check_creation_limits_unauthorized(self, client: TestClient) -> None:
        """Test checking creation limits without authentication."""
        response = client.get(f"{settings.API_STR}/subscriptions/limits/check?resource_type=car")
        assert response.status_code == 401

    def test_check_global_part_creation_limit_success(self, client: TestClient, test_user: User) -> None:
        """Test checking global part creation limit."""
        # Login as test user
        login_data = {"username": test_user.username, "password": "testpassword"}
        response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check if user can create a global part
        response = client.get(f"{settings.API_STR}/subscriptions/limits/check/global-part", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "can_create" in data
        assert isinstance(data["can_create"], bool)

    def test_check_global_part_creation_limit_unauthorized(self, client: TestClient) -> None:
        """Test checking global part creation limit without authentication."""
        response = client.get(f"{settings.API_STR}/subscriptions/limits/check/global-part")
        assert response.status_code == 401
