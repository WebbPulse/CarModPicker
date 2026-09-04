"""Tests for car service."""

import logging
import os

from sqlalchemy.orm import Session

from app.api.models.car_generation import CarGeneration
from app.api.schemas.car_generation import CarGenerationCreate, CarGenerationUpdate
from app.api.services.car_generation_service import CarGenerationService
from app.db.dynamo.users import User
from tests.conftest import create_car_orm_in_db


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestCarService:
    """Test cases for car service."""

    def test_get_cars_by_make_model_with_make(self, db_session: Session) -> None:
        """Test getting cars filtered by make."""
        create_car_orm_in_db(
            db_session, make="Honda", model="Civic", generation_name="10th Gen", start_year=2016, end_year=2021
        )
        create_car_orm_in_db(
            db_session, make="Honda", model="Accord", generation_name="10th Gen", start_year=2018, end_year=2022
        )
        create_car_orm_in_db(
            db_session, make="Toyota", model="Camry", generation_name="8th Gen", start_year=2018, end_year=2024
        )

        service = CarGenerationService()
        result = service.get_car_generations_by_make_model(db_session, car_make_name="Honda")
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(car.car_make_name == "Honda" for car in result)

    def test_get_cars_by_make_model_with_make_and_model(self, db_session: Session) -> None:
        """Test getting cars filtered by make and model."""
        create_car_orm_in_db(
            db_session, make="Honda", model="Civic", generation_name="10th Gen", start_year=2016, end_year=2021
        )
        create_car_orm_in_db(
            db_session, make="Honda", model="Civic", generation_name="11th Gen", start_year=2022, end_year=2024
        )
        create_car_orm_in_db(
            db_session, make="Honda", model="Accord", generation_name="10th Gen", start_year=2018, end_year=2022
        )

        service = CarGenerationService()
        result = service.get_car_generations_by_make_model(db_session, car_make_name="Honda", car_model_name="Civic")
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(car.car_make_name == "Honda" and car.car_model_name == "Civic" for car in result)

    def test_get_cars_by_make_model_with_no_filters(self, db_session: Session) -> None:
        """Test getting cars with no filters."""
        create_car_orm_in_db(
            db_session, make="Honda", model="Civic", generation_name="10th Gen", start_year=2016, end_year=2021
        )
        create_car_orm_in_db(
            db_session, make="Toyota", model="Camry", generation_name="8th Gen", start_year=2018, end_year=2024
        )

        service = CarGenerationService()
        result = service.get_car_generations_by_make_model(db_session)
        assert isinstance(result, list)
        assert len(result) >= 2

    def test_get_cars_by_make_model_with_pagination(self, db_session: Session) -> None:
        """Test getting cars with pagination."""
        for i in range(5):
            create_car_orm_in_db(
                db_session,
                make="Honda",
                model=f"Model{i}",
                generation_name=f"Gen{i}",
                start_year=2016 + i,
                end_year=2021 + i,
            )

        service = CarGenerationService()
        result = service.get_car_generations_by_make_model(db_session, car_make_name="Honda", skip=2, limit=2)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_search_cars_by_make(self, db_session: Session) -> None:
        """Test searching cars by make."""
        create_car_orm_in_db(
            db_session, make="Tesla", model="Model 3", generation_name="1st Gen", start_year=2017, end_year=2023
        )
        create_car_orm_in_db(
            db_session, make="Toyota", model="Corolla", generation_name="12th Gen", start_year=2019, end_year=2022
        )

        service = CarGenerationService()
        result = service.search_car_generations(db_session, search_term="Tesla")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert any(car.car_make_name == "Tesla" for car in result)

    def test_search_cars_by_model(self, db_session: Session) -> None:
        """Test searching cars by model."""
        create_car_orm_in_db(db_session, make="BMW", model="M3", generation_name="G80", start_year=2021, end_year=2024)
        create_car_orm_in_db(db_session, make="BMW", model="M4", generation_name="G82", start_year=2021, end_year=2024)

        service = CarGenerationService()
        result = service.search_car_generations(db_session, search_term="M3")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert any(car.car_model_name == "M3" for car in result)

    def test_search_cars_by_generation_name(self, db_session: Session) -> None:
        """Test searching cars by generation name."""
        create_car_orm_in_db(
            db_session, make="Honda", model="Civic", generation_name="10th Gen", start_year=2016, end_year=2021
        )
        create_car_orm_in_db(
            db_session, make="Honda", model="Civic", generation_name="11th Gen", start_year=2022, end_year=2024
        )

        service = CarGenerationService()
        result = service.search_car_generations(db_session, search_term="10th Gen")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert any("10th Gen" in car.generation_name for car in result)

    def test_search_cars_no_results(self, db_session: Session) -> None:
        """Test searching cars with no matching results."""
        service = CarGenerationService()
        result = service.search_car_generations(db_session, search_term="NonExistentCarBrandXYZ123")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_search_cars_with_pagination(self, db_session: Session) -> None:
        """Test searching cars with pagination."""
        for i in range(5):
            create_car_orm_in_db(
                db_session,
                make="Honda",
                model=f"Model{i}",
                generation_name=f"Gen{i}",
                start_year=2016 + i,
                end_year=2021 + i,
            )

        service = CarGenerationService()
        result = service.search_car_generations(db_session, search_term="Honda", skip=2, limit=2)
        assert isinstance(result, list)
        assert len(result) <= 2

    def test_delete_car_success(self, db_session: Session, test_user: User) -> None:
        """Test deleting a car."""
        car = create_car_orm_in_db(
            db_session,
            make="Honda",
            model="Civic",
            generation_name="10th Gen",
            start_year=2016,
            end_year=2021,
        )

        service = CarGenerationService()
        logger = logging.getLogger(__name__)
        deleted_car = service.delete(db_session, car.id, test_user, logger)

        assert deleted_car.id == car.id
        assert deleted_car.car_make_name == car.car_make_name

        result = db_session.query(CarGeneration).filter(CarGeneration.id == car.id).first()
        assert result is None

    def test_delete_car_not_found(self, db_session: Session, test_user: User) -> None:
        """Test deleting a non-existent car."""
        service = CarGenerationService()
        logger = logging.getLogger(__name__)

        from fastapi import HTTPException

        try:
            import uuid

            service.delete(db_session, uuid.uuid4(), test_user, logger)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 404
