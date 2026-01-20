"""Tests for car service."""

import logging
import os

from sqlalchemy.orm import Session

from app.api.models.car import Car
from app.api.models.user import User
from app.api.schemas.car import CarCreate, CarUpdate
from app.api.services.car_service import CarService


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestCarService:
    """Test cases for car service."""

    def test_get_cars_by_make_model_with_make(self, db_session: Session) -> None:
        """Test getting cars filtered by make."""
        # Create cars
        car1 = Car(
            make="Honda",
            model="Civic",
            generation_name="10th Gen",
            start_year=2016,
            end_year=2021,
        )
        car2 = Car(
            make="Honda",
            model="Accord",
            generation_name="10th Gen",
            start_year=2018,
            end_year=2022,
        )
        car3 = Car(
            make="Toyota",
            model="Camry",
            generation_name="8th Gen",
            start_year=2018,
            end_year=2024,
        )
        db_session.add_all([car1, car2, car3])
        db_session.commit()

        # Test the service
        service = CarService()
        result = service.get_cars_by_make_model(db_session, make="Honda")
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(car.make == "Honda" for car in result)

    def test_get_cars_by_make_model_with_make_and_model(self, db_session: Session) -> None:
        """Test getting cars filtered by make and model."""
        # Create cars
        car1 = Car(
            make="Honda",
            model="Civic",
            generation_name="10th Gen",
            start_year=2016,
            end_year=2021,
        )
        car2 = Car(
            make="Honda",
            model="Civic",
            generation_name="11th Gen",
            start_year=2022,
            end_year=2024,
        )
        car3 = Car(
            make="Honda",
            model="Accord",
            generation_name="10th Gen",
            start_year=2018,
            end_year=2022,
        )
        db_session.add_all([car1, car2, car3])
        db_session.commit()

        # Test the service
        service = CarService()
        result = service.get_cars_by_make_model(db_session, make="Honda", model="Civic")
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(car.make == "Honda" and car.model == "Civic" for car in result)

    def test_get_cars_by_make_model_with_no_filters(self, db_session: Session) -> None:
        """Test getting cars with no filters."""
        # Create cars
        car1 = Car(
            make="Honda",
            model="Civic",
            generation_name="10th Gen",
            start_year=2016,
            end_year=2021,
        )
        car2 = Car(
            make="Toyota",
            model="Camry",
            generation_name="8th Gen",
            start_year=2018,
            end_year=2024,
        )
        db_session.add_all([car1, car2])
        db_session.commit()

        # Test the service
        service = CarService()
        result = service.get_cars_by_make_model(db_session)
        assert isinstance(result, list)
        assert len(result) >= 2

    def test_get_cars_by_make_model_with_pagination(self, db_session: Session) -> None:
        """Test getting cars with pagination."""
        # Create multiple cars
        cars = []
        for i in range(5):
            car = Car(
                make="Honda",
                model=f"Model{i}",
                generation_name=f"Gen{i}",
                start_year=2016 + i,
                end_year=2021 + i,
            )
            cars.append(car)
        db_session.add_all(cars)
        db_session.commit()

        # Test the service with pagination
        service = CarService()
        result = service.get_cars_by_make_model(db_session, make="Honda", skip=2, limit=2)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_search_cars_by_make(self, db_session: Session) -> None:
        """Test searching cars by make."""
        # Create cars
        car1 = Car(
            make="Tesla",
            model="Model 3",
            generation_name="1st Gen",
            start_year=2017,
            end_year=2023,
        )
        car2 = Car(
            make="Toyota",
            model="Corolla",
            generation_name="12th Gen",
            start_year=2019,
            end_year=2022,
        )
        db_session.add_all([car1, car2])
        db_session.commit()

        # Test the service
        service = CarService()
        result = service.search_cars(db_session, search_term="Tesla")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert any(car.make == "Tesla" for car in result)

    def test_search_cars_by_model(self, db_session: Session) -> None:
        """Test searching cars by model."""
        # Create cars
        car1 = Car(
            make="BMW",
            model="M3",
            generation_name="G80",
            start_year=2021,
            end_year=2024,
        )
        car2 = Car(
            make="BMW",
            model="M4",
            generation_name="G82",
            start_year=2021,
            end_year=2024,
        )
        db_session.add_all([car1, car2])
        db_session.commit()

        # Test the service
        service = CarService()
        result = service.search_cars(db_session, search_term="M3")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert any(car.model == "M3" for car in result)

    def test_search_cars_by_generation_name(self, db_session: Session) -> None:
        """Test searching cars by generation name."""
        # Create cars
        car1 = Car(
            make="Honda",
            model="Civic",
            generation_name="10th Gen",
            start_year=2016,
            end_year=2021,
        )
        car2 = Car(
            make="Honda",
            model="Civic",
            generation_name="11th Gen",
            start_year=2022,
            end_year=2024,
        )
        db_session.add_all([car1, car2])
        db_session.commit()

        # Test the service
        service = CarService()
        result = service.search_cars(db_session, search_term="10th Gen")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert any("10th Gen" in car.generation_name for car in result)

    def test_search_cars_no_results(self, db_session: Session) -> None:
        """Test searching cars with no matching results."""
        # Test the service
        service = CarService()
        result = service.search_cars(db_session, search_term="NonExistentCarBrandXYZ123")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_search_cars_with_pagination(self, db_session: Session) -> None:
        """Test searching cars with pagination."""
        # Create multiple cars
        cars = []
        for i in range(5):
            car = Car(
                make="Honda",
                model=f"Model{i}",
                generation_name=f"Gen{i}",
                start_year=2016 + i,
                end_year=2021 + i,
            )
            cars.append(car)
        db_session.add_all(cars)
        db_session.commit()

        # Test the service with pagination
        service = CarService()
        result = service.search_cars(db_session, search_term="Honda", skip=2, limit=2)
        assert isinstance(result, list)
        assert len(result) <= 2

    def test_delete_car_success(self, db_session: Session, test_user: User) -> None:
        """Test deleting a car."""
        # Create a car
        car = Car(
            make="Honda",
            model="Civic",
            generation_name="10th Gen",
            start_year=2016,
            end_year=2021,
        )
        db_session.add(car)
        db_session.commit()
        db_session.refresh(car)

        # Test the service
        service = CarService()
        logger = logging.getLogger(__name__)
        deleted_car = service.delete(db_session, car.id, test_user, logger)

        assert deleted_car.id == car.id
        assert deleted_car.make == car.make

        # Verify car is deleted
        result = db_session.query(Car).filter(Car.id == car.id).first()
        assert result is None

    def test_delete_car_not_found(self, db_session: Session, test_user: User) -> None:
        """Test deleting a non-existent car."""
        # Test the service
        service = CarService()
        logger = logging.getLogger(__name__)

        from fastapi import HTTPException

        try:
            service.delete(db_session, 99999, test_user, logger)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 404
