"""Tests for pagination utility functions."""

from app.api.utils.pagination_utils import create_paginated_response, get_pagination_params


class TestPaginationParams:
    """Test pagination parameter handling."""

    def test_get_pagination_params_default(self) -> None:
        skip, limit = get_pagination_params(skip=0, limit=100)
        assert skip == 0
        assert limit == 100

    def test_get_pagination_params_custom(self) -> None:
        skip, limit = get_pagination_params(skip=10, limit=50)
        assert skip == 10
        assert limit == 50

    def test_get_pagination_params_boundary(self) -> None:
        skip, limit = get_pagination_params(skip=0, limit=1000)
        assert skip == 0
        assert limit == 1000

    def test_get_pagination_params_clamps_out_of_range(self) -> None:
        skip, limit = get_pagination_params(skip=-5, limit=5000)
        assert skip == 0
        assert limit == 1000


class TestPaginatedResponse:
    """Test paginated response creation."""

    def test_create_paginated_response_first_page(self) -> None:
        data = [{"id": i} for i in range(10)]
        response = create_paginated_response(data=data, total=25, skip=0, limit=10, entity_name="items")

        assert len(response["data"]) == 10
        assert response["total"] == 25
        assert response["pagination"]["current_page"] == 1
        assert response["pagination"]["total_pages"] == 3
        assert response["pagination"]["total_items"] == 25
        assert response["pagination"]["items_per_page"] == 10
        assert response["pagination"]["has_next"] is True
        assert response["pagination"]["has_previous"] is False

    def test_create_paginated_response_middle_page(self) -> None:
        data = [{"id": i} for i in range(10, 20)]
        response = create_paginated_response(data=data, total=30, skip=10, limit=10, entity_name="items")

        assert response["pagination"]["current_page"] == 2
        assert response["pagination"]["total_pages"] == 3
        assert response["pagination"]["has_next"] is True
        assert response["pagination"]["has_previous"] is True

    def test_create_paginated_response_last_page(self) -> None:
        data = [{"id": i} for i in range(20, 25)]
        response = create_paginated_response(data=data, total=25, skip=20, limit=10, entity_name="items")

        assert len(response["data"]) == 5
        assert response["pagination"]["current_page"] == 3
        assert response["pagination"]["total_pages"] == 3
        assert response["pagination"]["has_next"] is False
        assert response["pagination"]["has_previous"] is True

    def test_create_paginated_response_single_page(self) -> None:
        data = [{"id": i} for i in range(5)]
        response = create_paginated_response(data=data, total=5, skip=0, limit=10, entity_name="items")

        assert response["pagination"]["current_page"] == 1
        assert response["pagination"]["total_pages"] == 1
        assert response["pagination"]["has_next"] is False
        assert response["pagination"]["has_previous"] is False

    def test_create_paginated_response_empty(self) -> None:
        data: list[dict[str, int]] = []
        response = create_paginated_response(data=data, total=0, skip=0, limit=10, entity_name="items")

        assert len(response["data"]) == 0
        assert response["pagination"]["total_items"] == 0
        assert response["pagination"]["total_pages"] == 0
