"""Tests for build list service."""

import os

from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList
from app.api.models.car import Car
from app.api.models.user import User
from app.api.services.build_list_service import BuildListService


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestBuildListService:
    """Test cases for build list service."""

    def test_get_build_lists_by_car(self, db_session: Session, test_user: User) -> None:
        """Test getting build lists by car ID."""
        # Create a car
        car = Car(
            make="Honda",
            model="Civic",
            year=2020,
            user_id=test_user.id,
        )
        db_session.add(car)
        db_session.commit()
        db_session.refresh(car)

        # Create build lists for the car
        build_list1 = BuildList(
            name=get_unique_name("test_build_list_1"),
            description="Test build list 1",
            car_id=car.id,
            user_id=test_user.id,
        )
        build_list2 = BuildList(
            name=get_unique_name("test_build_list_2"),
            description="Test build list 2",
            car_id=car.id,
            user_id=test_user.id,
        )
        db_session.add(build_list1)
        db_session.add(build_list2)
        db_session.commit()

        # Test the service
        service = BuildListService()
        result = service.get_build_lists_by_car(db_session, car.id)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_get_build_lists_by_user(self, db_session: Session, test_user: User) -> None:
        """Test getting build lists by user ID."""
        # Create a car
        car = Car(
            make="Toyota",
            model="Camry",
            year=2019,
            user_id=test_user.id,
        )
        db_session.add(car)
        db_session.commit()
        db_session.refresh(car)

        # Create build lists for the user
        build_list = BuildList(
            name=get_unique_name("test_user_build_list"),
            description="Test user build list",
            car_id=car.id,
            user_id=test_user.id,
        )
        db_session.add(build_list)
        db_session.commit()

        # Test the service
        service = BuildListService()
        result = service.get_build_lists_by_user(db_session, test_user.id)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_count_by_user(self, db_session: Session, test_user: User) -> None:
        """Test counting build lists by user."""
        # Create a car
        car = Car(
            make="Ford",
            model="Mustang",
            year=2022,
            user_id=test_user.id,
        )
        db_session.add(car)
        db_session.commit()
        db_session.refresh(car)

        # Get initial count
        service = BuildListService()
        initial_count = service.count_by_user(db_session, test_user.id)

        # Create a build list
        build_list = BuildList(
            name=get_unique_name("test_count_build_list"),
            description="Test count build list",
            car_id=car.id,
            user_id=test_user.id,
        )
        db_session.add(build_list)
        db_session.commit()

        # Test the count increased
        new_count = service.count_by_user(db_session, test_user.id)
        assert new_count == initial_count + 1
