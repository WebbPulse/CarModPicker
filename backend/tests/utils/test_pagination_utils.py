"""Tests for pagination utility functions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.api.models.report import Report
from app.api.utils.pagination_utils import (
    apply_search_filter,
    apply_sorting,
    create_paginated_response,
    get_total_count,
    paginate_query,
)


def _seed_reports(db_session: Session, user_id: UUID, descriptions: list[str]) -> None:
    """Persist Reports as a stand-in SQL table with an owner and a searchable text column."""
    db_session.add_all(
        Report(user_id=user_id, entity_type="part", entity_id=uuid7(), reason="spam", description=description)
        for description in descriptions
    )
    db_session.commit()


class TestPaginationUtils:
    """Test cases for pagination utility functions."""

    def test_paginate_query(self, db_session: Session) -> None:
        """Test paginating a query."""
        user_id = uuid7()
        _seed_reports(db_session, user_id, [f"Test Report {i}" for i in range(5)])

        stmt = select(Report).where(Report.user_id == user_id)
        result = paginate_query(db_session, stmt, skip=1, limit=2)

        assert len(result) == 2

    def test_get_total_count(self, db_session: Session) -> None:
        """Test getting total count of a query."""
        user_id = uuid7()
        _seed_reports(db_session, user_id, [f"Test Report {i}" for i in range(3)])

        stmt = select(Report).where(Report.user_id == user_id)
        count = get_total_count(db_session, stmt)

        assert count == 3

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

    def test_apply_search_filter(self, db_session: Session) -> None:
        """Test applying search filter to a query."""
        user_id = uuid7()
        _seed_reports(db_session, user_id, ["Test Report", "Another Report"])

        stmt = select(Report).where(Report.user_id == user_id)
        filtered_stmt = apply_search_filter(stmt, search="Test", search_fields=["description"])

        results = list(db_session.scalars(filtered_stmt).all())
        assert len(results) == 1
        assert all("Test" in (report.description or "") for report in results)

    def test_apply_sorting(self, db_session: Session) -> None:
        """Test applying sorting to a query."""
        user_id = uuid7()
        _seed_reports(db_session, user_id, ["B Report", "A Report"])

        stmt = select(Report).where(Report.user_id == user_id)
        sorted_stmt = apply_sorting(stmt, sort_by="description", sort_order="asc", allowed_sort_fields=["description"])

        results = list(db_session.scalars(sorted_stmt).all())
        assert [report.description for report in results] == ["A Report", "B Report"]
