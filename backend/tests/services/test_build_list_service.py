"""Tests for build list service."""

import os
from uuid import uuid4

from sqlalchemy.orm import Session

from app.api.services.build_list_service import BuildListService
from app.db.dynamo.build_lists import BuildList, BuildListRepository
from app.db.dynamo.users import User


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestBuildListService:
    """Test cases for build list service."""

    def test_get_build_lists_by_car(self, db_session: Session, test_user: User) -> None:
        """Test getting build lists by car ID."""
        car_id = uuid4()
        repository = BuildListRepository()

        # Create build lists for the car
        repository.create(
            BuildList(
                name=get_unique_name("test_build_list_1"),
                description="Test build list 1",
                car_id=car_id,
                user_id=test_user.id,
            )
        )
        repository.create(
            BuildList(
                name=get_unique_name("test_build_list_2"),
                description="Test build list 2",
                car_id=car_id,
                user_id=test_user.id,
            )
        )
        repository.create(BuildList(name=get_unique_name("other_car"), car_id=uuid4(), user_id=test_user.id))

        # Test the service
        service = BuildListService()
        result = service.get_build_lists_by_car(car_id)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_get_build_lists_by_user(self, db_session: Session, test_user: User) -> None:
        """Test getting build lists by user ID."""
        BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_user_build_list"),
                description="Test user build list",
                car_id=uuid4(),
                user_id=test_user.id,
            )
        )

        # Test the service
        service = BuildListService()
        result = service.get_build_lists_by_user(test_user.id)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_count_by_user(self, db_session: Session, test_user: User) -> None:
        """Test counting build lists by user."""
        # Get initial count
        service = BuildListService()
        initial_count = service.count_by_user(test_user.id)

        # Create a build list
        BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_count_build_list"),
                description="Test count build list",
                car_id=uuid4(),
                user_id=test_user.id,
            )
        )

        # Test the count increased
        new_count = service.count_by_user(test_user.id)
        assert new_count == initial_count + 1
