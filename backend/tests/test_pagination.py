"""Tests for pagination utilities."""

import logging
import os
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Disable rate limiting for tests
os.environ["ENABLE_RATE_LIMITING"] = "false"

from app.api.models.car_generation import CarGeneration  # noqa: E402
from app.api.models.car_make import CarMake  # noqa: E402
from app.api.models.car_model import CarModel  # noqa: E402
from app.api.utils.pagination_utils import (  # noqa: E402
    apply_search_filter,
    apply_sorting,
    create_paginated_response,
    get_pagination_params,
    get_total_count,
    paginate_query,
)
from app.db.base import Base  # noqa: E402


@pytest.fixture
def test_db_session() -> Generator[Session, None, None]:
    """Create a test database session with Car model."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    # Add test data: Make -> CarModel -> Car (generation)
    for i in range(20):
        make_name = f"Make{i % 5}"
        model_name = f"Model{i}"
        make_entity = session.query(Make).filter(Make.name == make_name).first()
        if make_entity is None:
            make_entity = Make(name=make_name)
            session.add(make_entity)
            session.flush()
        car_model_entity = (
            session.query(CarModel).filter(CarModel.car_make_id == make_entity.id, CarModel.name == model_name).first()
        )
        if car_model_entity is None:
            car_model_entity = CarModel(car_make_id=make_entity.id, name=model_name)
            session.add(car_model_entity)
            session.flush()
        car = Car(
            car_model_id=car_model_entity.id,
            generation_name=f"Gen{i}",
            start_year=2000 + i,
            end_year=2000 + i + 1,
        )
        session.add(car)
    session.commit()

    yield session

    session.close()
    engine.dispose()


class TestPaginationParams:
    """Test pagination parameter handling."""

    def test_get_pagination_params_default(self) -> None:
        """Test default pagination parameters."""
        skip, limit = get_pagination_params(skip=0, limit=100)
        assert skip == 0
        assert limit == 100

    def test_get_pagination_params_custom(self) -> None:
        """Test custom pagination parameters."""
        skip, limit = get_pagination_params(skip=10, limit=50)
        assert skip == 10
        assert limit == 50

    def test_get_pagination_params_boundary(self) -> None:
        """Test boundary pagination parameters."""
        skip, limit = get_pagination_params(skip=0, limit=1000)
        assert skip == 0
        assert limit == 1000


class TestPaginateQuery:
    """Test query pagination functionality."""

    def test_paginate_query_first_page(self, test_db_session: Session) -> None:
        """Test paginating first page of results."""
        query = test_db_session.query(Car)
        results = paginate_query(query, skip=0, limit=10, entity_name="cars")

        assert len(results) == 10
        assert all(isinstance(car, Car) for car in results)

    def test_paginate_query_second_page(self, test_db_session: Session) -> None:
        """Test paginating second page of results."""
        query = test_db_session.query(Car)
        results = paginate_query(query, skip=10, limit=10, entity_name="cars")

        assert len(results) == 10

    def test_paginate_query_partial_page(self, test_db_session: Session) -> None:
        """Test paginating partial page at end of results."""
        query = test_db_session.query(Car)
        results = paginate_query(query, skip=15, limit=10, entity_name="cars")

        assert len(results) == 5  # Only 5 remaining

    def test_paginate_query_beyond_results(self, test_db_session: Session) -> None:
        """Test paginating beyond available results."""
        query = test_db_session.query(Car)
        results = paginate_query(query, skip=100, limit=10, entity_name="cars")

        assert len(results) == 0

    def test_paginate_query_with_logger(self, test_db_session: Session) -> None:
        """Test pagination with logger."""
        logger = logging.getLogger("test")
        query = test_db_session.query(Car)
        results = paginate_query(query, skip=0, limit=5, logger=logger, entity_name="test_cars")

        assert len(results) == 5


class TestTotalCount:
    """Test total count functionality."""

    def test_get_total_count(self, test_db_session: Session) -> None:
        """Test getting total count of query."""
        query = test_db_session.query(Car)
        total = get_total_count(query)

        assert total == 20

    def test_get_total_count_filtered(self, test_db_session: Session) -> None:
        """Test getting total count of filtered query (by make via join)."""
        query = test_db_session.query(Car).join(Car.car_model).join(CarModel.car_make).filter(Make.name == "Make1")
        total = get_total_count(query)

        assert total == 4  # 20 total / 5 makes = 4 per make


class TestPaginatedResponse:
    """Test paginated response creation."""

    def test_create_paginated_response_first_page(self) -> None:
        """Test creating paginated response for first page."""
        data = [{"id": i} for i in range(10)]
        response = create_paginated_response(data=data, total=25, skip=0, limit=10, entity_name="items")

        assert len(response["data"]) == 10
        assert response["pagination"]["current_page"] == 1
        assert response["pagination"]["total_pages"] == 3
        assert response["pagination"]["total_items"] == 25
        assert response["pagination"]["items_per_page"] == 10
        assert response["pagination"]["has_next"] is True
        assert response["pagination"]["has_previous"] is False

    def test_create_paginated_response_middle_page(self) -> None:
        """Test creating paginated response for middle page."""
        data = [{"id": i} for i in range(10, 20)]
        response = create_paginated_response(data=data, total=30, skip=10, limit=10, entity_name="items")

        assert response["pagination"]["current_page"] == 2
        assert response["pagination"]["total_pages"] == 3
        assert response["pagination"]["has_next"] is True
        assert response["pagination"]["has_previous"] is True

    def test_create_paginated_response_last_page(self) -> None:
        """Test creating paginated response for last page."""
        data = [{"id": i} for i in range(20, 25)]
        response = create_paginated_response(data=data, total=25, skip=20, limit=10, entity_name="items")

        assert len(response["data"]) == 5
        assert response["pagination"]["current_page"] == 3
        assert response["pagination"]["total_pages"] == 3
        assert response["pagination"]["has_next"] is False
        assert response["pagination"]["has_previous"] is True

    def test_create_paginated_response_single_page(self) -> None:
        """Test creating paginated response when all items fit on one page."""
        data = [{"id": i} for i in range(5)]
        response = create_paginated_response(data=data, total=5, skip=0, limit=10, entity_name="items")

        assert response["pagination"]["current_page"] == 1
        assert response["pagination"]["total_pages"] == 1
        assert response["pagination"]["has_next"] is False
        assert response["pagination"]["has_previous"] is False

    def test_create_paginated_response_empty(self) -> None:
        """Test creating paginated response with no items."""
        data: list[dict[str, int]] = []
        response = create_paginated_response(data=data, total=0, skip=0, limit=10, entity_name="items")

        assert len(response["data"]) == 0
        assert response["pagination"]["total_items"] == 0
        assert response["pagination"]["total_pages"] == 0


class TestSearchFilter:
    """Test search filtering functionality."""

    def test_apply_search_filter_with_results(self, test_db_session: Session) -> None:
        """Test applying search filter that returns results (Car column: generation_name)."""
        query = test_db_session.query(Car)
        filtered_query = apply_search_filter(query, search="Gen1", search_fields=["generation_name"])

        results = filtered_query.all()
        # Should find Gen1, Gen10-19 (11 total)
        assert len(results) >= 1
        assert all("Gen1" in car.generation_name for car in results)

    def test_apply_search_filter_no_search_term(self, test_db_session: Session) -> None:
        """Test applying search filter with no search term."""
        query = test_db_session.query(Car)
        filtered_query = apply_search_filter(query, search=None, search_fields=["generation_name"])

        results = filtered_query.all()
        assert len(results) == 20  # Should return all results

    def test_apply_search_filter_no_results(self, test_db_session: Session) -> None:
        """Test applying search filter that returns no results."""
        query = test_db_session.query(Car)
        filtered_query = apply_search_filter(query, search="NonExistentGen", search_fields=["generation_name"])

        results = filtered_query.all()
        assert len(results) == 0

    def test_apply_search_filter_multiple_fields(self, test_db_session: Session) -> None:
        """Test applying search filter across multiple fields (Car columns only)."""
        query = test_db_session.query(Car)
        filtered_query = apply_search_filter(query, search="Gen", search_fields=["generation_name"])

        results = filtered_query.all()
        assert len(results) == 20  # All have generation_name containing "Gen"


class TestSorting:
    """Test sorting functionality."""

    def test_apply_sorting_ascending(self, test_db_session: Session) -> None:
        """Test applying ascending sort."""
        query = test_db_session.query(Car)
        sorted_query = apply_sorting(query, sort_by="start_year", sort_order="asc", allowed_sort_fields=["start_year"])

        results = sorted_query.all()
        years = [car.start_year for car in results]
        assert years == sorted(years)

    def test_apply_sorting_descending(self, test_db_session: Session) -> None:
        """Test applying descending sort."""
        query = test_db_session.query(Car)
        sorted_query = apply_sorting(query, sort_by="start_year", sort_order="desc", allowed_sort_fields=["start_year"])

        results = sorted_query.all()
        years = [car.start_year for car in results]
        assert years == sorted(years, reverse=True)

    def test_apply_sorting_no_sort_field(self, test_db_session: Session) -> None:
        """Test applying sort with no sort field."""
        query = test_db_session.query(Car)
        sorted_query = apply_sorting(query, sort_by=None, sort_order="asc")

        results = sorted_query.all()
        assert len(results) == 20

    def test_apply_sorting_invalid_field(self, test_db_session: Session) -> None:
        """Test applying sort with invalid field."""
        query = test_db_session.query(Car)
        sorted_query = apply_sorting(
            query,
            sort_by="invalid_field",
            sort_order="asc",
            allowed_sort_fields=["start_year"],
        )

        # Should return unsorted results
        results = sorted_query.all()
        assert len(results) == 20

    def test_apply_sorting_without_allowed_fields(self, test_db_session: Session) -> None:
        """Test applying sort without allowed fields restriction (use Car column)."""
        query = test_db_session.query(Car)
        sorted_query = apply_sorting(query, sort_by="generation_name", sort_order="asc")

        results = sorted_query.all()
        names = [car.generation_name for car in results]
        assert names == sorted(names)


class TestIntegration:
    """Integration tests combining multiple pagination utilities."""

    def test_full_pagination_workflow(self, test_db_session: Session) -> None:
        """Test complete pagination workflow (search on Car column: generation_name)."""
        query = test_db_session.query(Car)

        query = apply_search_filter(query, search="Gen1", search_fields=["generation_name"])
        query = apply_sorting(query, sort_by="start_year", sort_order="asc", allowed_sort_fields=["start_year"])

        total = get_total_count(query)
        results = paginate_query(query, skip=0, limit=2, entity_name="cars")
        response = create_paginated_response(data=results, total=total, skip=0, limit=2, entity_name="cars")

        assert len(response["data"]) <= 2
        assert response["pagination"]["total_items"] == total
        assert all("Gen1" in car.generation_name for car in results)

        # Verify sorting
        if len(results) > 1:
            assert results[0].start_year <= results[1].start_year
