"""
Bug report service for handling bug reports.
"""

import logging
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.models.bug_report import BugReport as DBBugReport
from app.api.models.user import User as DBUser
from app.api.schemas.bug_report import (
    BugReportCreate,
    BugReportRead,
    BugReportUpdate,
    BugReportWithDetails,
)


class BugReportService:
    """
    Service for handling bug reports.
    """

    def __init__(self) -> None:
        """Initialize the bug report service."""
        pass

    def create_bug_report(
        self,
        db: Session,
        bug_report_data: BugReportCreate,
        user_id: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
    ) -> DBBugReport:
        """
        Create a new bug report.

        Args:
            db: Database session
            bug_report_data: Bug report data
            user_id: Optional user ID (for authenticated users)
            logger: Optional logger instance

        Returns:
            The created bug report
        """
        db_bug_report = DBBugReport(
            user_id=user_id,
            title=bug_report_data.title,
            description=bug_report_data.description,
            steps_to_reproduce=bug_report_data.steps_to_reproduce,
            expected_behavior=bug_report_data.expected_behavior,
            actual_behavior=bug_report_data.actual_behavior,
            browser_info=bug_report_data.browser_info,
            device_info=bug_report_data.device_info,
            screenshot_url=bug_report_data.screenshot_url,
        )
        db.add(db_bug_report)
        db.commit()
        db.refresh(db_bug_report)

        if logger:
            logger.info(f"Bug report created: {db_bug_report.id} by user {user_id or 'anonymous'}")
        return db_bug_report

    def get_bug_reports(
        self,
        db: Session,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[BugReportRead]:
        """
        Get bug reports with optional filtering.

        Args:
            db: Database session
            status: Optional status filter
            priority: Optional priority filter
            skip: Number of reports to skip
            limit: Maximum number of reports to return
            logger: Optional logger instance

        Returns:
            List of bug reports
        """
        query = db.query(DBBugReport)

        if status:
            query = query.filter(DBBugReport.status == status)

        if priority:
            query = query.filter(DBBugReport.priority == priority)

        bug_reports = query.order_by(desc(DBBugReport.created_at)).offset(skip).limit(limit).all()

        return [BugReportRead.model_validate(report) for report in bug_reports]

    def get_bug_reports_with_details(
        self,
        db: Session,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> tuple[List[BugReportWithDetails], int]:
        """
        Get bug reports with detailed information including reporter and assignee details.

        Args:
            db: Database session
            status: Optional status filter
            priority: Optional priority filter
            skip: Number of reports to skip
            limit: Maximum number of reports to return
            logger: Optional logger instance

        Returns:
            Tuple of (list of bug reports with details, total count)
        """
        query = db.query(DBBugReport)

        if status:
            query = query.filter(DBBugReport.status == status)

        if priority:
            query = query.filter(DBBugReport.priority == priority)

        # Get total count before pagination
        total_count = query.count()

        # Get bug reports with user details
        bug_reports_with_details: List[BugReportWithDetails] = []
        for bug_report in query.order_by(desc(DBBugReport.created_at)).offset(skip).limit(limit).all():
            # Get reporter username if exists
            reporter_username = None
            if bug_report.user_id:
                reporter = db.query(DBUser).filter(DBUser.id == bug_report.user_id).first()
                reporter_username = reporter.username if reporter else None

            # Get assignee username if exists
            assignee_username = None
            if bug_report.assigned_to:
                assignee = db.query(DBUser).filter(DBUser.id == bug_report.assigned_to).first()
                assignee_username = assignee.username if assignee else None

            bug_reports_with_details.append(
                BugReportWithDetails(
                    id=bug_report.id,
                    user_id=bug_report.user_id,
                    title=bug_report.title,
                    description=bug_report.description,
                    steps_to_reproduce=bug_report.steps_to_reproduce,
                    expected_behavior=bug_report.expected_behavior,
                    actual_behavior=bug_report.actual_behavior,
                    browser_info=bug_report.browser_info,
                    device_info=bug_report.device_info,
                    screenshot_url=bug_report.screenshot_url,
                    status=bug_report.status,
                    priority=bug_report.priority,
                    admin_notes=bug_report.admin_notes,
                    assigned_to=bug_report.assigned_to,
                    resolved_at=bug_report.resolved_at,
                    created_at=bug_report.created_at,
                    updated_at=bug_report.updated_at,
                    reporter_username=reporter_username,
                    assignee_username=assignee_username,
                )
            )

        return bug_reports_with_details, total_count

    def update_bug_report(
        self,
        db: Session,
        bug_report_id: int,
        bug_report_update: BugReportUpdate,
        logger: Optional[logging.Logger] = None,
    ) -> DBBugReport:
        """
        Update a bug report (typically for admin review).

        Args:
            db: Database session
            bug_report_id: ID of the bug report to update
            bug_report_update: Update data
            logger: Optional logger instance

        Returns:
            The updated bug report

        Raises:
            HTTPException: If bug report doesn't exist
        """
        bug_report = db.query(DBBugReport).filter(DBBugReport.id == bug_report_id).first()
        if not bug_report:
            raise HTTPException(status_code=404, detail="Bug report not found")

        if bug_report_update.status:
            bug_report.status = bug_report_update.status.value
            # Set resolved_at if status is resolved
            if bug_report_update.status.value == "resolved":
                bug_report.resolved_at = datetime.now(UTC)

        if bug_report_update.priority:
            bug_report.priority = bug_report_update.priority.value

        if bug_report_update.admin_notes is not None:
            bug_report.admin_notes = bug_report_update.admin_notes

        if bug_report_update.assigned_to is not None:
            bug_report.assigned_to = bug_report_update.assigned_to

        bug_report.updated_at = datetime.now(UTC)

        db.commit()
        db.refresh(bug_report)

        if logger:
            logger.info(f"Bug report updated: {bug_report_id}")

        return bug_report

    def delete_bug_report(
        self,
        db: Session,
        bug_report_id: int,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Delete a bug report (admin only).

        Args:
            db: Database session
            bug_report_id: ID of the bug report to delete
            logger: Optional logger instance

        Raises:
            HTTPException: If bug report doesn't exist
        """
        bug_report = db.query(DBBugReport).filter(DBBugReport.id == bug_report_id).first()
        if not bug_report:
            raise HTTPException(status_code=404, detail="Bug report not found")

        db.delete(bug_report)
        db.commit()

        if logger:
            logger.info(f"Bug report deleted: {bug_report_id}")

    def get_bug_report_by_id(
        self,
        db: Session,
        bug_report_id: int,
        logger: Optional[logging.Logger] = None,
    ) -> Optional[BugReportWithDetails]:
        """
        Get a specific bug report by ID.

        Args:
            db: Database session
            bug_report_id: ID of the bug report to retrieve
            logger: Optional logger instance

        Returns:
            Bug report with details if found, None otherwise
        """
        bug_report = db.query(DBBugReport).filter(DBBugReport.id == bug_report_id).first()

        if not bug_report:
            return None

        # Get reporter username if exists
        reporter_username = None
        if bug_report.user_id:
            reporter = db.query(DBUser).filter(DBUser.id == bug_report.user_id).first()
            reporter_username = reporter.username if reporter else None

        # Get assignee username if exists
        assignee_username = None
        if bug_report.assigned_to:
            assignee = db.query(DBUser).filter(DBUser.id == bug_report.assigned_to).first()
            assignee_username = assignee.username if assignee else None

        return BugReportWithDetails(
            id=bug_report.id,
            user_id=bug_report.user_id,
            title=bug_report.title,
            description=bug_report.description,
            steps_to_reproduce=bug_report.steps_to_reproduce,
            expected_behavior=bug_report.expected_behavior,
            actual_behavior=bug_report.actual_behavior,
            browser_info=bug_report.browser_info,
            device_info=bug_report.device_info,
            screenshot_url=bug_report.screenshot_url,
            status=bug_report.status,
            priority=bug_report.priority,
            admin_notes=bug_report.admin_notes,
            assigned_to=bug_report.assigned_to,
            resolved_at=bug_report.resolved_at,
            created_at=bug_report.created_at,
            updated_at=bug_report.updated_at,
            reporter_username=reporter_username,
            assignee_username=assignee_username,
        )
