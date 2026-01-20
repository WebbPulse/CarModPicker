"""Tests for pagination utility functions."""

from sqlalchemy.orm import Query

from app.api.models.build_list import BuildList
from app.api.utils.pagination_utils import (
    apply_search_filter,
    apply_sorting,
    create_paginated_response,
    get_total_count,
    paginate_query,
)


class TestPaginationUtils:
    """Test cases for pagination utility functions."""

    def test_paginate_query(self, db_session) -> None:
        """Test paginating a query."""
        # Create some build lists
        from app.api.models.user import User
        from app.api.dependencies.auth import get_password_hash

        user = User(
            username="test_user_pagination",
            email="test_pagination@example.com",
            hashed_password=get_password_hash("password"),
            email_verified=True,
            disabled=False,
        )
        db_session.add(user)
        db_session.commit()

        for i in range(5):
            build_list = BuildList(
                name=f"Test Build List {i}",
                description="Test",
                user_id=user.id,
            )
            db_session.add(build_list)
        db_session.commit()

        query = db_session.query(BuildList)
        result = paginate_query(query, skip=1, limit=2)

        assert len(result) == 2

    def test_get_total_count(self, db_session) -> None:
        """Test getting total count of a query."""
        from app.api.models.user import User
        from app.api.dependencies.auth import get_password_hash

        user = User(
            username="test_user_count",
            email="test_count@example.com",
            hashed_password=get_password_hash("password"),
            email_verified=True,
            disabled=False,
        )
        db_session.add(user)
        db_session.commit()

        for i in range(3):
            build_list = BuildList(
                name=f"Test Build List {i}",
                description="Test",
                user_id=user.id,
            )
            db_session.add(build_list)
        db_session.commit()

        query = db_session.query(BuildList).filter(BuildList.user_id == user.id)
        count = get_total_count(query)

        assert count >= 3

    def test_create_paginated_response(self) -> None:
        """Test creating a paginated response."""
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = create_paginated_response(data, total=10, skip=0, limit=3)

        assert "data" in result
        assert "pagination" in result
        assert result["pagination"]["current_page"] == 1
        assert result["pagination"]["total_pages"] == 4
        assert result["pagination"]["total_items"] == 10
        assert result["pagination"]["has_next"] is True
        assert result["pagination"]["has_previous"] is False

    def test_apply_search_filter(self, db_session) -> None:
        """Test applying search filter to a query."""
        from app.api.models.user import User
        from app.api.dependencies.auth import get_password_hash

        user = User(
            username="test_user_search",
            email="test_search@example.com",
            hashed_password=get_password_hash("password"),
            email_verified=True,
            disabled=False,
        )
        db_session.add(user)
        db_session.commit()

        build_list1 = BuildList(
            name="Test Build List",
            description="Test",
            user_id=user.id,
        )
        build_list2 = BuildList(
            name="Another List",
            description="Test",
            user_id=user.id,
        )
        db_session.add_all([build_list1, build_list2])
        db_session.commit()

        query = db_session.query(BuildList).filter(BuildList.user_id == user.id)
        filtered_query = apply_search_filter(query, search="Test", search_fields=["name"])

        results = filtered_query.all()
        assert len(results) >= 1
        assert any("Test" in bl.name for bl in results)

    def test_apply_sorting(self, db_session) -> None:
        """Test applying sorting to a query."""
        from app.api.models.user import User
        from app.api.dependencies.auth import get_password_hash

        user = User(
            username="test_user_sort",
            email="test_sort@example.com",
            hashed_password=get_password_hash("password"),
            email_verified=True,
            disabled=False,
        )
        db_session.add(user)
        db_session.commit()

        build_list1 = BuildList(
            name="A Build List",
            description="Test",
            user_id=user.id,
        )
        build_list2 = BuildList(
            name="B Build List",
            description="Test",
            user_id=user.id,
        )
        db_session.add_all([build_list1, build_list2])
        db_session.commit()

        query = db_session.query(BuildList).filter(BuildList.user_id == user.id)
        sorted_query = apply_sorting(query, sort_by="name", sort_order="asc", allowed_sort_fields=["name"])

        results = sorted_query.all()
        assert len(results) >= 2
        # Results should be sorted by name ascending
        names = [bl.name for bl in results]
        assert names == sorted(names)
