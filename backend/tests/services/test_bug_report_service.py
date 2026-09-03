"""Tests for bug report service."""

import logging
import os

from sqlalchemy.orm import Session

from app.api.models.bug_report import BugReport
from app.api.schemas.bug_report import BugReportCreate, BugReportPriority, BugReportStatus, BugReportUpdate
from app.api.services.bug_report_service import BugReportService
from app.db.dynamo.users import User


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestBugReportService:
    """Test cases for bug report service."""

    def test_create_bug_report_authenticated(self, db_session: Session, test_user: User) -> None:
        """Test creating a bug report as an authenticated user."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        bug_report_data = BugReportCreate(
            title="Test Bug Report",
            description="This is a test bug report",
            steps_to_reproduce="1. Go to page\n2. Click button",
            expected_behavior="Should work",
            actual_behavior="Doesn't work",
            browser_info="Chrome 120",
            device_info="Windows 11",
        )

        bug_report = service.create_bug_report(
            db_session,
            bug_report_data,
            user_id=test_user.id,
            logger=logger,
        )

        assert bug_report.title == "Test Bug Report"
        assert bug_report.description == "This is a test bug report"
        assert bug_report.user_id == test_user.id
        assert bug_report.status == "pending"
        assert bug_report.priority == "medium"
        assert bug_report.steps_to_reproduce == "1. Go to page\n2. Click button"
        assert bug_report.expected_behavior == "Should work"
        assert bug_report.actual_behavior == "Doesn't work"
        assert bug_report.browser_info == "Chrome 120"
        assert bug_report.device_info == "Windows 11"

    def test_create_bug_report_anonymous(self, db_session: Session) -> None:
        """Test creating a bug report as an anonymous user."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        bug_report_data = BugReportCreate(
            title="Anonymous Bug Report",
            description="This is an anonymous bug report",
        )

        bug_report = service.create_bug_report(
            db_session,
            bug_report_data,
            user_id=None,
            logger=logger,
        )

        assert bug_report.title == "Anonymous Bug Report"
        assert bug_report.description == "This is an anonymous bug report"
        assert bug_report.user_id is None
        assert bug_report.status == "pending"
        assert bug_report.priority == "medium"

    def test_get_bug_reports_no_filters(self, db_session: Session, test_user: User) -> None:
        """Test getting bug reports with no filters."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        # Create multiple bug reports
        for i in range(3):
            bug_report_data = BugReportCreate(
                title=f"Test Bug Report {i}",
                description=f"This is test bug report {i}",
            )
            service.create_bug_report(
                db_session,
                bug_report_data,
                user_id=test_user.id if i % 2 == 0 else None,  # Mix of authenticated and anonymous
                logger=logger,
            )

        # Get all bug reports
        reports = service.get_bug_reports(db_session, logger=logger)

        assert isinstance(reports, list)
        assert len(reports) >= 3

    def test_get_bug_reports_with_status_filter(self, db_session: Session, test_user: User) -> None:
        """Test getting bug reports filtered by status."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        # Create bug reports
        bug_report_data1 = BugReportCreate(
            title="Pending Bug Report",
            description="This is a pending bug report",
        )
        bug_report1 = service.create_bug_report(
            db_session,
            bug_report_data1,
            user_id=test_user.id,
            logger=logger,
        )

        # Update one to resolved
        update_data = BugReportUpdate(status=BugReportStatus.RESOLVED)
        service.update_bug_report(
            db_session,
            bug_report1.id,
            update_data,
            logger=logger,
        )

        # Create another pending report
        bug_report_data2 = BugReportCreate(
            title="Another Pending Bug Report",
            description="This is another pending bug report",
        )
        service.create_bug_report(
            db_session,
            bug_report_data2,
            user_id=test_user.id,
            logger=logger,
        )

        # Get only pending reports
        reports = service.get_bug_reports(db_session, status="pending", logger=logger)

        assert isinstance(reports, list)
        assert all(report.status == "pending" for report in reports)
        assert len(reports) >= 1

    def test_get_bug_reports_with_priority_filter(self, db_session: Session, test_user: User) -> None:
        """Test getting bug reports filtered by priority."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        # Create bug reports with different priorities
        bug_report_data1 = BugReportCreate(
            title="High Priority Bug",
            description="This is a high priority bug",
        )
        bug_report1 = service.create_bug_report(
            db_session,
            bug_report_data1,
            user_id=test_user.id,
            logger=logger,
        )

        # Update priority
        update_data = BugReportUpdate(priority=BugReportPriority.HIGH)
        service.update_bug_report(
            db_session,
            bug_report1.id,
            update_data,
            logger=logger,
        )

        # Create another with default priority (medium)
        bug_report_data2 = BugReportCreate(
            title="Medium Priority Bug",
            description="This is a medium priority bug",
        )
        service.create_bug_report(
            db_session,
            bug_report_data2,
            user_id=test_user.id,
            logger=logger,
        )

        # Get only high priority reports
        reports = service.get_bug_reports(db_session, priority="high", logger=logger)

        assert isinstance(reports, list)
        assert all(report.priority == "high" for report in reports)
        assert len(reports) >= 1

    def test_get_bug_reports_with_details(self, db_session: Session, test_user: User) -> None:
        """Test getting bug reports with details."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        # Create a bug report
        bug_report_data = BugReportCreate(
            title="Test Bug Report",
            description="This is a test bug report",
        )
        service.create_bug_report(
            db_session,
            bug_report_data,
            user_id=test_user.id,
            logger=logger,
        )

        # Get reports with details
        reports, total_count = service.get_bug_reports_with_details(db_session, logger=logger)

        assert isinstance(reports, list)
        assert total_count >= 1
        assert len(reports) >= 1

        # Check that details are included
        report = next((r for r in reports if r.title == "Test Bug Report"), None)
        assert report is not None
        assert report.reporter_username == test_user.username

    def test_get_bug_reports_with_details_anonymous(self, db_session: Session) -> None:
        """Test getting bug reports with details for anonymous reports."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        # Create an anonymous bug report
        bug_report_data = BugReportCreate(
            title="Anonymous Bug Report",
            description="This is an anonymous bug report",
        )
        service.create_bug_report(
            db_session,
            bug_report_data,
            user_id=None,
            logger=logger,
        )

        # Get reports with details
        reports, total_count = service.get_bug_reports_with_details(db_session, logger=logger)

        assert isinstance(reports, list)
        assert total_count >= 1

        # Check that anonymous reports have None for reporter_username
        report = next((r for r in reports if r.title == "Anonymous Bug Report"), None)
        assert report is not None
        assert report.reporter_username is None

    def test_update_bug_report(self, db_session: Session, test_user: User) -> None:
        """Test updating a bug report."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        # Create a bug report
        bug_report_data = BugReportCreate(
            title="Test Bug Report",
            description="This is a test bug report",
        )
        bug_report = service.create_bug_report(
            db_session,
            bug_report_data,
            user_id=test_user.id,
            logger=logger,
        )

        # Update the bug report
        update_data = BugReportUpdate(
            status=BugReportStatus.IN_PROGRESS,
            priority=BugReportPriority.HIGH,
            admin_notes="Working on this bug",
        )
        updated_report = service.update_bug_report(
            db_session,
            bug_report.id,
            update_data,
            logger=logger,
        )

        assert updated_report.status == "in_progress"
        assert updated_report.priority == "high"
        assert updated_report.admin_notes == "Working on this bug"

    def test_update_bug_report_resolved_sets_resolved_at(self, db_session: Session, test_user: User) -> None:
        """Test that updating a bug report to resolved sets resolved_at."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        # Create a bug report
        bug_report_data = BugReportCreate(
            title="Test Bug Report",
            description="This is a test bug report",
        )
        bug_report = service.create_bug_report(
            db_session,
            bug_report_data,
            user_id=test_user.id,
            logger=logger,
        )

        assert bug_report.resolved_at is None

        # Update to resolved
        update_data = BugReportUpdate(status=BugReportStatus.RESOLVED)
        updated_report = service.update_bug_report(
            db_session,
            bug_report.id,
            update_data,
            logger=logger,
        )

        assert updated_report.status == "resolved"
        assert updated_report.resolved_at is not None

    def test_update_bug_report_not_found(self, db_session: Session) -> None:
        """Test updating a non-existent bug report."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        update_data = BugReportUpdate(status=BugReportStatus.RESOLVED)

        from fastapi import HTTPException

        try:
            service.update_bug_report(
                db_session,
                99999,
                update_data,
                logger=logger,
            )
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 404
            assert "not found" in e.detail.lower()

    def test_delete_bug_report(self, db_session: Session, test_user: User) -> None:
        """Test deleting a bug report."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        # Create a bug report
        bug_report_data = BugReportCreate(
            title="Test Bug Report",
            description="This is a test bug report",
        )
        bug_report = service.create_bug_report(
            db_session,
            bug_report_data,
            user_id=test_user.id,
            logger=logger,
        )

        # Delete the bug report
        service.delete_bug_report(
            db_session,
            bug_report.id,
            logger=logger,
        )

        # Verify bug report is deleted
        result = db_session.query(BugReport).filter(BugReport.id == bug_report.id).first()
        assert result is None

    def test_delete_bug_report_not_found(self, db_session: Session) -> None:
        """Test deleting a non-existent bug report."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        from fastapi import HTTPException

        try:
            service.delete_bug_report(
                db_session,
                99999,
                logger=logger,
            )
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 404
            assert "not found" in e.detail.lower()

    def test_get_bug_report_by_id(self, db_session: Session, test_user: User) -> None:
        """Test getting a bug report by ID."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        # Create a bug report
        bug_report_data = BugReportCreate(
            title="Test Bug Report",
            description="This is a test bug report",
        )
        bug_report = service.create_bug_report(
            db_session,
            bug_report_data,
            user_id=test_user.id,
            logger=logger,
        )

        # Get the bug report by ID
        result = service.get_bug_report_by_id(
            db_session,
            bug_report.id,
            logger=logger,
        )

        assert result is not None
        assert result.id == bug_report.id
        assert result.title == "Test Bug Report"
        assert result.reporter_username == test_user.username

    def test_get_bug_report_by_id_not_found(self, db_session: Session) -> None:
        """Test getting a non-existent bug report by ID."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        result = service.get_bug_report_by_id(
            db_session,
            99999,
            logger=logger,
        )

        assert result is None

    def test_get_bug_reports_with_details_pagination(self, db_session: Session, test_user: User) -> None:
        """Test pagination for bug reports with details."""
        service = BugReportService()
        logger = logging.getLogger(__name__)

        # Create multiple bug reports
        for i in range(5):
            bug_report_data = BugReportCreate(
                title=f"Test Bug Report {i}",
                description=f"This is test bug report {i}",
            )
            service.create_bug_report(
                db_session,
                bug_report_data,
                user_id=test_user.id,
                logger=logger,
            )

        # Get first page
        reports_page1, total_count = service.get_bug_reports_with_details(
            db_session,
            skip=0,
            limit=2,
            logger=logger,
        )

        assert len(reports_page1) == 2
        assert total_count >= 5

        # Get second page
        reports_page2, _ = service.get_bug_reports_with_details(
            db_session,
            skip=2,
            limit=2,
            logger=logger,
        )

        assert len(reports_page2) == 2

        # Verify different reports
        assert reports_page1[0].id != reports_page2[0].id
